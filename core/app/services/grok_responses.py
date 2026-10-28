"""Responses streaming adapter for subscription-token Grok calls."""
import json

import httpx

from app.services.grok_oauth import BASE_URL
from app.services.provider_errors import OutputLimitError, ProviderError, http_error


def payload(model, messages, tools, caps, *, system_as_instructions=False):
    items = []
    instructions = []
    for message in messages:
        role = message["role"]
        if system_as_instructions and role == "system" and isinstance(message.get("content"), str):
            instructions.append(message["content"])
            continue
        if role == "tool":
            items.append({"type": "function_call_output", "call_id": message["tool_call_id"],
                          "output": message["content"]})
            continue
        if message.get("content"):
            content = message["content"]
            if isinstance(content, list):
                converted = []
                for part in content:
                    if part.get("type") == "text":
                        converted.append({"type": "output_text" if role == "assistant" else "input_text", "text": part["text"]})
                    elif part.get("type") == "image_url":
                        converted.append({"type": "input_image", "image_url": part["image_url"]["url"]})
                    else:
                        raise ProviderError("Этот тип вложения не поддерживается")
                content = converted
            items.append({"role": role, "content": content})
        for call in message.get("tool_calls", []):
            items.append({"type": "function_call", "call_id": call["id"],
                          "name": call["function"]["name"], "arguments": call["function"]["arguments"]})
    result = {"model": model, "input": items, "stream": True, "store": False,
              "max_output_tokens": caps.get("max_output") or 8192}
    if instructions:
        result["instructions"] = "\n\n".join(instructions)
    if tools:
        result["tools"] = [{"type": "function", **t["function"]} for t in tools]
        result["tool_choice"] = "auto"
    drop = caps.get("drop") or []
    if caps.get("temperature") is not None and "temperature" not in drop:
        result["temperature"] = caps["temperature"]
    if caps.get("reasoning_effort") and "reasoning_effort" not in drop:
        result["reasoning"] = {"effort": caps["reasoning_effort"]}
    return result


def _message_text(item) -> str:
    if not isinstance(item, dict) or item.get("type") != "message":
        return ""
    content = item.get("content")
    if isinstance(content, str):
        return content
    parts = []
    for part in content or []:
        if isinstance(part, dict) and part.get("type") in ("output_text", "text") and isinstance(part.get("text"), str):
            parts.append(part["text"])
    return "".join(parts)


def _response_text(result) -> str:
    if not isinstance(result, dict):
        return ""
    if isinstance(result.get("output_text"), str) and result["output_text"]:
        return result["output_text"]
    return "".join(_message_text(item) for item in result.get("output") or [])


async def stream_turn(provider, key, model, messages, tools, caps=None, *, base_url=None, label="Grok"):
    from app.services.provider_client import _headers

    base = base_url or BASE_URL
    if provider.base_url != base:
        raise ProviderError(f"Некорректный адрес {label}")
    body = payload(model, messages, tools, caps or {}, system_as_instructions=label == "Codex")
    calls = {}
    completed = False
    saw_text = False
    size = 0
    headers = _headers(provider, key)
    secret = headers.get("Authorization", "").removeprefix("Bearer ").strip()
    async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=15)) as client:
        async with client.stream("POST", base + "/responses", headers=headers, json=body) as response:
            if response.is_error:
                text = (await response.aread())[:4000].decode("utf-8", "replace")
                raise http_error(response.status_code, text, response.headers, tools=bool(tools), secret=secret)
            async for line in response.aiter_lines():
                size += len(line.encode())
                if size > 4_000_000:
                    raise ProviderError(f"Ответ {label} превышает лимит")
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    break
                try:
                    event = json.loads(raw)
                except ValueError:
                    raise ProviderError(f"Некорректный поток {label}") from None
                kind = event.get("type")
                if kind == "response.output_text.delta":
                    delta = event.get("delta") or ""
                    if delta:
                        saw_text = True
                        yield "content", delta
                elif kind == "response.output_text.done" and not saw_text and isinstance(event.get("text"), str) and event["text"]:
                    saw_text = True
                    yield "content", event["text"]
                elif kind in ("response.reasoning_text.delta", "response.reasoning_summary_text.delta"):
                    yield "reasoning", event.get("delta", "")
                elif kind == "response.output_item.added":
                    item = event.get("item", {})
                    if item.get("type") == "function_call":
                        calls[event["output_index"]] = dict(item)
                elif kind == "response.function_call_arguments.delta":
                    call = calls.get(event["output_index"])
                    if not call:
                        raise ProviderError(f"{label} прислал аргументы неизвестного инструмента")
                    call["arguments"] = call.get("arguments", "") + event.get("delta", "")
                elif kind == "response.output_item.done":
                    item = event.get("item", {})
                    if item.get("type") == "function_call":
                        calls[event["output_index"]] = dict(item)
                    elif not saw_text:
                        text = _message_text(item)
                        if text:
                            saw_text = True
                            yield "content", text
                elif kind == "response.completed":
                    result = event.get("response", {})
                    if result.get("status", "completed") != "completed":
                        raise ProviderError(f"{label} не завершил ответ")
                    # Final output is authoritative, including gateways without argument deltas.
                    output = result.get("output")
                    if output is not None:
                        calls = {i: dict(item) for i, item in enumerate(output) if item.get("type") == "function_call"}
                    if not saw_text:
                        text = _response_text(result)
                        if text:
                            saw_text = True
                            yield "content", text
                    completed = True
                    break
                elif kind == "response.incomplete":
                    reason = (event.get("response", {}).get("incomplete_details") or {}).get("reason")
                    if reason in (None, "max_output_tokens"):
                        raise OutputLimitError(f"Ответ {label} не поместился в лимит длины", has_calls=bool(calls))
                    raise ProviderError(f"{label} не завершил ответ")
                elif kind in ("error", "response.failed") or event.get("error"):
                    detail = event.get("error") or (event.get("response") or {}).get("error") or {}
                    message = detail.get("message") if isinstance(detail, dict) else str(detail or "")
                    message = " ".join(str(message).split())[:300]
                    text = f"{label} прервал ответ: {message}" if message else f"{label} прервал ответ ошибкой"
                    raise ProviderError(text, retryable=True)
                if len(calls) > 48:
                    raise ProviderError(f"{label} запросил слишком много инструментов")
    if not completed:
        # Codex can deliver the whole answer in one item and then close the stream
        # without response.completed. A partial tool call is still a dropped turn.
        if saw_text and not calls:
            completed = True
        else:
            raise ProviderError(f"Связь с {label} оборвалась посреди ответа", retryable=True)
    batch = []
    for item in calls.values():
        arguments = item.get("arguments") or "{}"
        try:
            parsed = json.loads(arguments)
        except ValueError:
            raise ProviderError(f"{label} не завершил JSON инструмента") from None
        if not isinstance(parsed, dict) or not item.get("name") or not item.get("call_id"):
            raise ProviderError(f"Некорректный вызов инструмента {label}")
        batch.append({"id": item["call_id"], "type": "function",
                      "function": {"name": item["name"], "arguments": arguments}})
    ids = [c["id"] for c in batch]
    if len(batch) > 48 or len(set(ids)) != len(ids) or any(len(i) > 200 for i in ids):
        raise ProviderError(f"Некорректные идентификаторы инструментов {label}")
    if batch:
        yield "tool_calls", batch
