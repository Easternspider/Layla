"""История чата для модели и её сжатие.

Сжатие слоями и заранее, не впритык к окну. На 75% заполнения сначала ужимаются
объёмные и быстро устаревающие результаты инструментов — остаются путь, команда
и идентификатор. Если этого мало, старая часть диалога сворачивается в сводку,
а последние ходы остаются дословно. Цель после сжатия — около 40% окна, чтобы
следующее сжатие не началось сразу. Сводка — системное сообщение чата
(meta.kind = "summary"). Всё, что раньше неё, модели больше не отправляется;
следующее сжатие дополняет предыдущую сводку.
"""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Chat, Message
from app.models.persona import Persona
from app.services import project_agent

SUMMARY = "summary"
KEEP_RECENT = 6  # последние сообщения всегда уходят модели целиком
DEFAULT_BUDGET = 80_000  # токенов истории, если размер контекста модели не задан
SUMMARY_MAX_OUTPUT = 4096
_ITEM_CHARS = 12_000  # одно сообщение в сводке длиннее не нужно
# Сжимать заранее: старт на 75% окна, цель — около 40%, не впритык к 100%.
FILL_TRIGGER = 0.75
FILL_TARGET = 0.40

SUMMARY_PROMPT = (
    "Ты сжимаешь историю рабочего разговора, чтобы продолжить работу без неё. Напиши сводку "
    "на языке разговора, по пунктам, и ничего не выдумывай:\n"
    "1. Исходная задача и ограничения.\n"
    "2. Принятые решения и почему они приняты (стек, стиль, договорённости).\n"
    "3. Текущий план и статус: что уже сделано, по путям файлов.\n"
    "4. Нерешённые ошибки и что из-за них заблокировано.\n"
    "5. Важные пути, команды и идентификаторы — дословно.\n"
    "6. Что нельзя забыть: предпочтения пользователя и явные запреты.\n"
    "7. Следующий шаг.\n"
    "Только сводка, без вступления."
)
CHECK_PROMPT = (
    "Проверь сводку рабочего разговора. Если по ней можно ответить, что делается, зачем и что уже "
    "сделано, ответь ровно: ДОСТАТОЧНО. Если нельзя — ответь НЕ ХВАТАЕТ: и перечисли, чего не хватает. "
    "Ничего больше не пиши."
)
SUMMARY_HEADER = "Сводка более ранней части разговора (старые сообщения свёрнуты, чтобы уместиться в контекст):\n"
PROGRESS_FILE = ".layla/progress.md"
PROGRESS_REMINDER = (
    "Контекст сжат. До следующей правки сверься с .layla/progress.md: что делается, зачем и что уже "
    "сделано. Не начинай задачу заново."
)


def is_summary(message: Message) -> bool:
    return (message.role == "system" and (message.meta or {}).get("kind") == SUMMARY
            and not (message.meta or {}).get("disabled"))


def entry(message: Message) -> dict | None:
    """Сообщение чата в том виде, в каком его видит модель."""
    if message.role not in ("user", "assistant", "system") or is_summary(message) or (message.meta or {}).get("disabled"):
        return None
    meta = message.meta or {}
    content = message.content or ""
    changes = [t["change"] for t in meta.get("tools", []) if t.get("change") and t.get("status") == "done"]
    if changes:
        listed = ", ".join(f"{c['operation']} {c['path']}" for c in changes)
        if meta.get("rolled_back"):
            content += f"\n[These project changes were later rolled back by the user: {listed}]"
        else:
            content += f"\n[Applied project changes: {listed}]"
    if message.role == "assistant" and meta.get("error"):
        # Ход прерван (ошибка, остановка, перезапуск сервера): модели нужно знать, что уже
        # сделано, чтобы «Продолжить» подхватило работу, а не начало её заново.
        steps = [f"{t.get('name')} {t.get('path') or ''} — {t.get('status')}".strip()
                 for t in meta.get("tools", [])[-30:]]
        done = ("; ".join(steps)) if steps else "ничего"
        content += (f"\n[This turn was interrupted: {meta['error']} Steps done before that: {done}. "
                    "Files already reflect the completed steps. When asked to continue, pick up from "
                    "here without repeating completed steps.]")
    runs = [t for t in meta.get("tools", []) if t.get("name") in ("run_command", "run_code")
            and t.get("status") in ("done", "error")]
    if runs:
        listed = "; ".join(
            f"`{(t.get('command') or '')[:200]}` → "
            + (f"exit {t.get('exit_code')}" if t.get("status") == "done" else f"error: {str(t.get('error'))[:120]}")
            for t in runs[-10:])
        content += f"\n[Commands run in the sandbox: {listed}]"
    todos = meta.get("todos") if message.role == "assistant" else None
    if todos:
        marks = {"done": "✓", "in_progress": "→", "pending": "☐"}
        listed = "; ".join(f"{marks.get(t.get('status'), '☐')} {t.get('content')}" for t in todos)
        content += f"\n[Task list at the end of this turn: {listed}]"
    attached = meta.get("files") if message.role == "user" else None
    if attached:
        from app.services.uploads import chat_note
        content += "\n\n" + chat_note(attached)
    if not content:
        return None
    # Размышления прошлых ответов модели не отправляются: это черновик мысли, часто с
    # кодом целиком, — он раздувал бы каждый следующий запрос. Внутри текущего хода
    # (между вызовами инструментов) их по-прежнему передаёт project_agent.
    return {"role": message.role, "content": content}


async def messages(session: AsyncSession, chat_id: str) -> list[Message]:
    return list(await session.scalars(
        select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at)))


def _after_summary(rows: list[Message]) -> tuple[Message | None, list[Message]]:
    """Последняя сводка и сообщения после неё."""
    summary, tail = None, []
    for row in rows:
        if is_summary(row):
            summary, tail = row, []
        else:
            tail.append(row)
    return summary, tail


async def build(session: AsyncSession, chat: Chat) -> list[dict]:
    """Payload для модели: инструкции роли, сводка (если была), история после неё."""
    out: list[dict] = []
    if chat.persona_id:
        persona = await session.get(Persona, chat.persona_id)
        if persona and persona.instructions:
            out.append({"role": "system", "content": persona.instructions})
    summary, tail = _after_summary(await messages(session, chat.id))
    if summary is not None:
        out.append({"role": "system", "content": SUMMARY_HEADER + summary.content})
    out.extend(item for item in map(entry, tail) if item)
    return out


def budget(caps: dict) -> int:
    """Порог, с которого пора сжимать: 75% окна, либо запас по умолчанию."""
    context = caps.get("context")
    return max(2048, int(context * FILL_TRIGGER)) if context else DEFAULT_BUDGET


def target(caps: dict) -> int:
    """Куда сжимать: около 40% окна, чтобы следующий ход не упёрся сразу."""
    context = caps.get("context")
    goal = max(2048, int(context * FILL_TARGET)) if context else DEFAULT_BUDGET
    return min(goal, budget(caps))


def tokens(payload: list[dict]) -> int:
    return sum(project_agent._tokens(m) for m in payload)


def needed(payload: list[dict], caps: dict) -> bool:
    return tokens(payload) > budget(caps)


def _transcript(items: list[dict]) -> list[str]:
    names = {"user": "Пользователь", "assistant": "Ассистент", "system": "Система"}
    out = []
    for item in items:
        text = item["content"]
        if len(text) > _ITEM_CHARS:
            text = text[: _ITEM_CHARS // 2] + "\n…[середина опущена]…\n" + text[-_ITEM_CHARS // 2:]
        out.append(f"### {names.get(item['role'], item['role'])}\n{text}")
    return out


async def _complete(provider, key, model, caps, conversation, on_event=None) -> str:
    text = ""
    async for kind, value in project_agent._turn(provider, key, model, conversation, [], caps):
        if kind == "done":
            text = "".join(value[0])
        elif on_event is not None and kind in ("retry", "key"):
            await on_event(kind, value)
    return text.replace(project_agent.LENGTH_NOTE, "").strip()


async def _summarize_body(provider, key, model: str, caps: dict, previous: str | None, items: list[dict],
                          on_event=None) -> str:
    """Свернуть сообщения в сводку. Очень длинную историю — по частям, дополняя сводку."""
    turn_caps = {k: v for k, v in caps.items() if k not in ("temperature",)}
    limit = caps.get("max_output_cap") or caps.get("max_output") or SUMMARY_MAX_OUTPUT
    turn_caps["max_output"] = min(SUMMARY_MAX_OUTPUT, limit)
    chunk_budget = max(2000, budget(caps) // 2)
    parts, chunk, size = [], [], 0
    for text in _transcript(items):
        cost = len(text) // 3 + 4
        if chunk and size + cost > chunk_budget:
            parts.append(chunk)
            chunk, size = [], 0
        chunk.append(text)
        size += cost
    if chunk:
        parts.append(chunk)
    summary = previous or ""
    for chunk in parts:
        request = ("Предыдущая сводка:\n" + summary + "\n\n" if summary else "") + \
            "Сообщения, которые нужно добавить в сводку:\n\n" + "\n\n".join(chunk)
        conversation = [{"role": "system", "content": SUMMARY_PROMPT}, {"role": "user", "content": request}]
        text = await _complete(provider, key, model, turn_caps, conversation, on_event)
        if text:
            summary = text
    return summary.strip()


async def summarize(provider, key, model: str, caps: dict, previous: str | None, items: list[dict],
                    on_event=None) -> str:
    """Сводка и одна проверка: если по ней неясно, что делается, сводка переписывается один раз."""
    summary = await _summarize_body(provider, key, model, caps, previous, items, on_event)
    if not summary:
        return ""
    turn_caps = {k: v for k, v in caps.items() if k not in ("temperature",)}
    limit = caps.get("max_output_cap") or caps.get("max_output") or SUMMARY_MAX_OUTPUT
    turn_caps["max_output"] = min(1024, limit)
    try:
        verdict = await _complete(provider, key, model, turn_caps, [
            {"role": "system", "content": CHECK_PROMPT}, {"role": "user", "content": summary}], on_event)
    except Exception:  # noqa: BLE001 — проверка не должна срывать уже готовую сводку
        return summary
    if "НЕ ХВАТАЕТ" not in verdict.upper():
        return summary
    repaired = await _summarize_body(
        provider, key, model, caps, summary,
        [{"role": "user", "content": "Проверка сводки: " + verdict + "\nДополни сводку, не теряя уже записанные факты."}],
        on_event)
    return repaired or summary


async def compact(session: AsyncSession, chat: Chat, provider, key, model: str, caps: dict, *,
                  keep: int = KEEP_RECENT, on_event=None) -> Message | None:
    """Свернуть всё, кроме последних keep сообщений, в сводку. None — сворачивать нечего."""
    rows = await messages(session, chat.id)
    previous, tail = _after_summary(rows)
    candidates = [row for row in tail if entry(row)]
    older = candidates[:-keep] if keep else candidates
    if not older:
        return None
    from app.models.enums import Domain
    if chat.domain == Domain.code:
        from app.services.code_sessions import compact_items
        items = await compact_items(session, older)
    else:
        items = [entry(row) for row in older]
    text = await summarize(provider, key, model, caps, previous.content if previous else None,
                           items, on_event=on_event)
    if not text:
        return None
    count = len(older) + int(((previous.meta or {}).get("count") or 0) if previous else 0)
    last = older[-1]
    # Сразу за последним свёрнутым сообщением: всё до сводки модели больше не отправляется.
    summary = Message(chat_id=chat.id, role="system", content=text,
                      meta={"kind": SUMMARY, "count": count, "until": last.id},
                      created_at=last.created_at + timedelta(microseconds=1))
    session.add(summary)
    await session.commit()
    return summary


# --- Ужатие внутри длинного хода агента ---------------------------------------

RUN_BUDGET = 100_000  # токенов на ход, если контекст модели не задан
KEEP_ROUNDS = 2  # последние шаги агента не трогаем
_HIDDEN = "содержимое скрыто — источник указан выше, прочитайте его заново, только если оно ещё нужно"
_BIG_ARGS = ("content", "new_string", "old_string")
_REF_KEYS = ("path", "sha256", "command", "exit_code", "query", "url", "id", "name", "pattern", "error")


def _clip(value, limit: int = 200):
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + "…"
    return value


def _reference(data: dict) -> dict:
    slim = {key: _clip(data[key]) for key in _REF_KEYS
            if key in data and not isinstance(data[key], (dict, list))}
    slim["note"] = _HIDDEN
    return slim


def _shrink_tool(message: dict) -> dict | None:
    try:
        data = json.loads(message.get("content") or "")
    except ValueError:
        data = None
    bulky = len(message.get("content") or "") > 800
    if isinstance(data, dict) and "content" in data and "sha256" in data and len(str(data.get("content") or "")) > 800:
        slim = {"path": data.get("path"), "sha256": data["sha256"], "note": _HIDDEN}
    elif isinstance(data, dict) and "exit_code" in data and len(str(data.get("output") or "")) > 400:
        slim = _reference(data)
        slim.pop("output", None)
    elif isinstance(data, dict) and bulky and any(key in data for key in ("query", "pattern", "url", "matches", "results")):
        slim = _reference(data)
    elif isinstance(data, dict) and isinstance(data.get("files"), list) and len(data["files"]) > 40:
        slim = {"files": data["files"][:40], "note": f"ещё {len(data['files']) - 40} — список сокращён"}
    elif bulky:
        return {**message, "content": (message["content"] or "")[:240] + "…[сокращено]"}
    else:
        return None
    return {**message, "content": json.dumps(slim, ensure_ascii=False)}


def _shrink_call(message: dict) -> dict | None:
    changed, calls = False, []
    for call in message.get("tool_calls") or []:
        try:
            args = json.loads(call["function"]["arguments"])
        except (ValueError, KeyError, TypeError):
            calls.append(call)
            continue
        for field in _BIG_ARGS:
            value = args.get(field) if isinstance(args, dict) else None
            if isinstance(value, str) and len(value) > 300:
                args[field] = f"[{len(value)} символов — уже применено]"
                changed = True
        calls.append({**call, "function": {**call["function"], "arguments": json.dumps(args, ensure_ascii=False)}})
    return {**message, "tool_calls": calls} if changed else None


def shrink_run(conversation: list[dict], anchor: dict, caps: dict, *, include_previous=False) -> int:
    """Первый слой: старые результаты инструментов заменить ссылками, пока ход не уложится в цель.

    Срабатывает на 75% окна. Последние два шага не трогаются — ими модель пользуется сейчас.
    """
    context = caps.get("context")
    trigger = budget(caps) if context else RUN_BUDGET
    goal = target(caps) if context else RUN_BUDGET
    total = tokens(conversation)
    if total <= trigger:
        return 0
    start = 1 if include_previous else next(i for i, m in enumerate(conversation) if m is anchor) + 1
    rounds = [i for i in range(start, len(conversation))
              if conversation[i]["role"] == "assistant" and conversation[i].get("tool_calls")]
    stop = rounds[-KEEP_ROUNDS] if len(rounds) >= KEEP_ROUNDS else start
    shrunk = 0
    for index in range(start, stop):
        if conversation[index] is anchor:
            continue
        if total <= goal:
            break
        message = conversation[index]
        slim = _shrink_tool(message) if message["role"] == "tool" else _shrink_call(message)
        if slim is not None:
            total += project_agent._tokens(slim) - project_agent._tokens(message)
            conversation[index] = slim
            shrunk += 1
    return shrunk


def _fold_span(conversation: list[dict], anchor: dict) -> tuple[int, int] | None:
    """Старые сообщения до текущего вопроса, кроме последних KEEP_RECENT и системных."""
    try:
        anchor_at = next(i for i, message in enumerate(conversation) if message is anchor)
    except StopIteration:
        return None
    start = 0
    while start < anchor_at and conversation[start].get("role") == "system":
        start += 1
    before = [i for i in range(start, anchor_at) if conversation[i].get("role") != "system"]
    if len(before) <= KEEP_RECENT:
        return None
    drop = before[:-KEEP_RECENT]
    lo, hi = drop[0], drop[-1] + 1
    while lo > start and conversation[lo].get("role") == "tool":
        lo -= 1
    protected = before[-KEEP_RECENT]
    if hi > protected:
        hi = protected
    while hi > lo and conversation[hi - 1].get("role") == "tool":
        hi -= 1
    if hi > lo and conversation[hi - 1].get("role") == "assistant" and conversation[hi - 1].get("tool_calls"):
        hi -= 1
    if hi <= lo:
        return None
    return lo, hi


def _protocol_items(messages: list[dict]) -> list[dict]:
    items = []
    for item in messages:
        content = item.get("content") or ""
        if item.get("tool_calls"):
            content += "\nTool calls: " + json.dumps(item["tool_calls"], ensure_ascii=False)[:_ITEM_CHARS]
        if content:
            items.append({"role": item.get("role") or "user", "content": content})
    return items


async def fold_old(provider, key, model, conversation: list[dict], anchor: dict, caps: dict, *,
                   on_event=None) -> int:
    """Второй слой: если после ссылок всё ещё тесно, свернуть старый префикс в одну сводку."""
    if tokens(conversation) <= budget(caps):
        return 0
    span = _fold_span(conversation, anchor)
    if span is None:
        return 0
    lo, hi = span
    chunk = conversation[lo:hi]
    # Сводка чата уже сделана до хода. Здесь сворачивается только журнал инструментов,
    # который в короткую историю не попал. Обычный диалог без инструментов не трогаем.
    if not any(message.get("role") == "tool" or message.get("tool_calls") for message in chunk):
        return 0
    if tokens(chunk) < max(400, int((caps.get("context") or DEFAULT_BUDGET) * 0.1)):
        return 0
    items = _protocol_items(chunk)
    if not items:
        return 0
    previous = next((message.get("content", "").removeprefix(SUMMARY_HEADER)
                     for message in conversation[:lo]
                     if message.get("role") == "system" and str(message.get("content") or "").startswith(SUMMARY_HEADER)),
                    None)
    text = await summarize(provider, key, model, caps, previous, items, on_event=on_event)
    if not text:
        return 0
    removed = hi - lo
    conversation[lo:hi] = [{"role": "system", "content": SUMMARY_HEADER + text}]
    return removed


def memory_note(root: str) -> str:
    """Заметки прогресса, которые переживают сжатие. Файл ведёт сам агент."""
    path = Path(root) / ".layla" / "progress.md"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return PROGRESS_REMINDER + " Заметок ещё нет — запиши их в .layla/progress.md, когда статус ясен."
    if len(text) > 6000:
        text = text[:3000] + "\n…\n" + text[-2000:]
    return PROGRESS_REMINDER + "\n\n.layla/progress.md:\n" + text


def attach_memory(conversation: list[dict], root: str) -> None:
    """После сжатия подложить внешние заметки к сводке, один раз."""
    note = memory_note(root)
    for message in conversation:
        if message.get("role") == "system" and str(message.get("content") or "").startswith(SUMMARY_HEADER):
            if note not in (message.get("content") or ""):
                message["content"] += "\n\n" + note
            return
