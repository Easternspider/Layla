"""Official MCP SDK client for stdio, Streamable HTTP and legacy SSE."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import shlex
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

# Имена, которые нельзя протащить из окружения ядра в дочерний процесс.
_CORE_SECRETS = {
    "LAYLA_SECRET_KEY", "LAYLA_JWT_SECRET", "DATABASE_URL", "POSTGRES_PASSWORD",
    "LITELLM_MASTER_KEY", "REDIS_URL",
}


def validate_mcp_url(url: str) -> str:
    """HTTP MCP — только публичный https:443, без логина и без локального адреса."""
    parsed = urlsplit((url or "").strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("MCP по сети доступен только по https без логина и пароля")
    if parsed.port not in (None, 443):
        raise ValueError("MCP по сети доступен только на порту 443")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost"} or host.endswith(".local") or host.endswith(".internal"):
        raise ValueError("Локальные адреса MCP недоступны")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return url.strip()
    if not address.is_global or address.is_multicast:
        raise ValueError("Локальные и служебные адреса MCP недоступны")
    return url.strip()


async def assert_public_mcp_url(url: str) -> str:
    target = validate_mcp_url(url)
    from app.services import web_research

    await web_research.public_addresses(urlsplit(target).hostname or "")
    return target


def _stdio_env(extra: dict | None) -> dict[str, str]:
    """Окружение дочернего MCP без секретов процесса API."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "HOME": os.environ.get("HOME", "/tmp"),
    }
    pythonpath = os.environ.get("PYTHONPATH")
    if pythonpath:
        env["PYTHONPATH"] = pythonpath
    for key, value in (extra or {}).items():
        if key in _CORE_SECRETS:
            continue
        env[str(key)] = str(value)
    return env


@asynccontextmanager
async def _session(
    *, transport: str, command: str | None, url: str | None, env: dict | None = None,
    allow_stdio: bool = False, trusted_url: bool = False,
):
    if transport == "stdio":
        if not allow_stdio:
            raise ValueError("Произвольный stdio MCP запрещён")
        parts = shlex.split(command or "")
        if not parts:
            raise ValueError("Missing stdio command")
        params = StdioServerParameters(command=parts[0], args=parts[1:], env=_stdio_env(env))
        # External workers may print environment secrets. Do not forward their
        # raw stderr to the API's log sink.
        with open(os.devnull, "w") as errlog:  # noqa: ASYNC230 - local null device, no disk I/O
            async with (
                stdio_client(params, errlog=errlog) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                yield session
    elif transport == "http" and url:
        if not trusted_url:
            await assert_public_mcp_url(url)
        # Preserve old /sse registrations without retrying with another transport.
        if urlsplit(url).path.rstrip("/").endswith("/sse"):
            async with sse_client(url) as (read, write), ClientSession(read, write) as session:
                await session.initialize()
                yield session
        else:
            async with (
                streamable_http_client(url) as (read, write, _),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                yield session
    else:
        raise ValueError("Invalid MCP transport configuration")


async def list_tools(
    *,
    transport: str,
    command: str | None,
    url: str | None,
    env: dict | None = None,
    timeout: float = 20.0,
    allow_stdio: bool = False,
    trusted_url: bool = False,
) -> list[dict]:
    try:
        async with asyncio.timeout(timeout):
            async with _session(transport=transport, command=command, url=url, env=env,
                                allow_stdio=allow_stdio, trusted_url=trusted_url) as session:
                tools, seen, cursor = [], set(), None
                while True:
                    result = await session.list_tools(cursor=cursor)
                    tools.extend({"name": tool.name, "description": tool.description,
                                  "input_schema": getattr(tool, "inputSchema", None) or
                                                  {"type": "object", "additionalProperties": True}}
                                 for tool in result.tools)
                    if len(tools) >= 1000:
                        return tools[:1000]
                    cursor = result.nextCursor
                    if not cursor or cursor in seen:
                        return tools
                    seen.add(cursor)
    except TimeoutError as exc:
        raise RuntimeError("Таймаут подключения к MCP-серверу") from exc
    except Exception as exc:
        raise RuntimeError("Не удалось подключиться к MCP-серверу. Проверьте настройки.") from exc


async def call_tool(
    *,
    name: str,
    arguments: dict,
    transport: str,
    command: str | None = None,
    url: str | None = None,
    env: dict | None = None,
    timeout: float = 35.0,
    allow_text: bool = False,
    allow_stdio: bool = False,
    trusted_url: bool = False,
) -> dict:
    try:
        async with asyncio.timeout(timeout):
            async with _session(transport=transport, command=command, url=url, env=env,
                                allow_stdio=allow_stdio, trusted_url=trusted_url) as session:
                result = await session.call_tool(name, arguments=arguments)
                if result.isError:
                    raise ValueError("MCP tool failed")
                data = result.structuredContent
                if data is None:
                    text = "".join(c.text for c in result.content if c.type == "text")
                    try:
                        data = json.loads(text)
                    except json.JSONDecodeError:
                        if not allow_text:
                            raise
                        data = {"text": text[:60000], "truncated": len(text) > 60000}
                if not isinstance(data, dict):
                    if allow_text:
                        return {"result": data}
                    raise TypeError("Invalid tool result")
                return data
    except TimeoutError as exc:
        raise RuntimeError("Таймаут выполнения MCP-инструмента") from exc
    except Exception as exc:
        # Neither tool responses nor SDK errors may echo secrets to users.
        raise RuntimeError("Не удалось выполнить MCP-инструмент") from exc


async def list_resources(*, transport: str, command: str | None, url: str | None,
                         env: dict | None = None, cursor: str | None = None,
                         timeout: float = 20.0, allow_stdio: bool = False,
                         trusted_url: bool = False) -> dict:
    try:
        async with asyncio.timeout(timeout), _session(
            transport=transport, command=command, url=url, env=env,
            allow_stdio=allow_stdio, trusted_url=trusted_url,
        ) as session:
            result = await session.list_resources(cursor=cursor)
            return {"resources": [item.model_dump(mode="json", exclude_none=True)
                                  for item in result.resources[:100]],
                    "next_cursor": result.nextCursor}
    except Exception as exc:
        raise RuntimeError("Не удалось получить ресурсы MCP-сервера") from exc


async def read_resource(*, uri: str, transport: str, command: str | None, url: str | None,
                        env: dict | None = None, timeout: float = 20.0,
                        allow_stdio: bool = False, trusted_url: bool = False) -> dict:
    from pydantic import AnyUrl

    try:
        async with asyncio.timeout(timeout), _session(
            transport=transport, command=command, url=url, env=env,
            allow_stdio=allow_stdio, trusted_url=trusted_url,
        ) as session:
            result = await session.read_resource(AnyUrl(uri))
            contents, remaining = [], 60000
            for item in result.contents[:50]:
                text = getattr(item, "text", None)
                if text is None:
                    contents.append({"uri": str(item.uri), "mime_type": item.mimeType,
                                     "note": "Binary resource; use the server's file tools."})
                else:
                    contents.append({"uri": str(item.uri), "mime_type": item.mimeType,
                                     "text": text[:remaining], "truncated": len(text) > remaining})
                    remaining -= min(len(text), remaining)
                if remaining <= 0:
                    break
            return {"contents": contents}
    except Exception as exc:
        raise RuntimeError("Не удалось прочитать ресурс MCP-сервера") from exc


async def list_resource_templates(*, transport: str, command: str | None, url: str | None,
                                  env: dict | None = None, cursor: str | None = None,
                                  timeout: float = 20.0, allow_stdio: bool = False,
                                  trusted_url: bool = False) -> dict:
    try:
        async with asyncio.timeout(timeout), _session(
            transport=transport, command=command, url=url, env=env,
            allow_stdio=allow_stdio, trusted_url=trusted_url,
        ) as session:
            result = await session.list_resource_templates(cursor=cursor)
            return {"templates": [item.model_dump(mode="json", exclude_none=True)
                                  for item in result.resourceTemplates[:100]],
                    "next_cursor": result.nextCursor}
    except Exception as exc:
        raise RuntimeError("Не удалось получить шаблоны ресурсов MCP-сервера") from exc
