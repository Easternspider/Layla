"""Тесты реестра MCP и проверки подключения (спец. §5.8)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

import app.services.mcp_client as mcp_client
from app.models.user import User


async def _register(client, email="mcp@example.com"):
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "hunter2hunter2"},
    )


async def _promote(db_sessionmaker, email: str) -> None:
    async with db_sessionmaker() as s:
        user = await s.scalar(select(User).where(User.email == email))
        user.is_admin = True
        await s.commit()


@pytest.mark.asyncio
async def test_register_and_list_mcp_server(client, db_sessionmaker):
    await _register(client)
    await _promote(db_sessionmaker, "mcp@example.com")
    r = await client.post(
        "/api/mcp/servers",
        json={
            "name": "filesystem",
            "transport": "stdio",
            "command": "npx -y @modelcontextprotocol/server-filesystem /tmp",
            "personas": ["p1"],
            "env": {"TOKEN": "secret-value"},
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "filesystem"
    # Значения env не возвращаются — только имена переменных.
    assert body["env_keys"] == ["TOKEN"]
    assert "secret-value" not in r.text

    lst = (await client.get("/api/mcp/servers")).json()
    assert len(lst) == 1


@pytest.mark.asyncio
async def test_stdio_forbidden_for_non_admin(client):
    await _register(client, "mcp-user@example.com")
    r = await client.post(
        "/api/mcp/servers",
        json={"name": "s", "transport": "stdio", "command": "run"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_toggle_and_delete(client):
    await _register(client, "mcp-http@example.com")
    srv = (
        await client.post(
            "/api/mcp/servers",
            json={"name": "s", "transport": "http", "url": "https://mcp.example/mcp"},
        )
    ).json()
    upd = (
        await client.patch(f"/api/mcp/servers/{srv['id']}", json={"enabled": False})
    ).json()
    assert upd["enabled"] is False
    r = await client.delete(f"/api/mcp/servers/{srv['id']}")
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_http_mcp_rejects_cleartext(client):
    await _register(client, "mcp-clear@example.com")
    r = await client.post(
        "/api/mcp/servers", json={"name": "s", "transport": "http", "url": "http://x/mcp"}
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_test_connection_uses_client(client, db_sessionmaker, monkeypatch):
    await _register(client, "mcp-test@example.com")
    await _promote(db_sessionmaker, "mcp-test@example.com")
    srv = (
        await client.post(
            "/api/mcp/servers",
            json={"name": "s", "transport": "stdio", "command": "run"},
        )
    ).json()

    async def fake_list_tools(**kw):
        assert kw.get("allow_stdio") is True
        return [{"name": "read_file", "description": "Read a file"}]

    monkeypatch.setattr(mcp_client, "list_tools", fake_list_tools)
    res = (await client.post(f"/api/mcp/servers/{srv['id']}/test")).json()
    assert res["ok"] is True
    assert res["tools"][0]["name"] == "read_file"


@pytest.mark.asyncio
async def test_test_connection_reports_error(client, db_sessionmaker, monkeypatch):
    await _register(client, "mcp-err@example.com")
    await _promote(db_sessionmaker, "mcp-err@example.com")
    srv = (
        await client.post(
            "/api/mcp/servers", json={"name": "s", "transport": "stdio", "command": "run"}
        )
    ).json()

    async def fake_list_tools(**kw):
        raise RuntimeError("SDK не установлен")

    monkeypatch.setattr(mcp_client, "list_tools", fake_list_tools)
    res = (await client.post(f"/api/mcp/servers/{srv['id']}/test")).json()
    assert res["ok"] is False
    assert "SDK" in res["error"]
