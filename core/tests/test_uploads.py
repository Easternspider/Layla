"""Вложения любого формата в чаты всех доменов и в пентест."""
from __future__ import annotations

import asyncio

import pytest

from app.services import files, pentest_workers, project_agent, uploads


async def _user(client, email="files@example.com"):
    await client.post("/api/auth/register", json={"email": email, "password": "hunter2hunter2"})
    await client.post("/api/providers", json={"name": "M", "kind": "openai_compatible",
                                              "base_url": "http://p/v1", "default_model": "m", "active": True})


def test_clean_name_strips_a_path():
    assert uploads.clean_name(r"..\report.zip") == "report.zip"
    with pytest.raises(ValueError):
        uploads.clean_name("   ")


@pytest.mark.asyncio
async def test_chat_accepts_a_zip_and_tells_the_model(client, monkeypatch):
    await _user(client)
    seen = []

    async def stream_turn(provider, key, model, conversation, available, **kw):
        seen.append([{**item} for item in conversation])
        yield ("content", "Готово")

    monkeypatch.setattr(project_agent.tool_chat, "stream_turn", stream_turn)
    chat = (await client.post("/api/chats", json={"domain": "osint", "model": "m"})).json()
    saved = await client.put(f"/api/chats/{chat['id']}/uploads?name=../notes.zip", content=b"PK\x03\x04fake-zip")
    assert saved.status_code == 200, saved.text
    item = saved.json()
    assert item["path"] == "inbox/notes.zip"
    assert item["size"] == len(b"PK\x03\x04fake-zip")
    started = await client.post(f"/api/chats/{chat['id']}/run", json={"content": "разбери архив", "files": [item["path"]]})
    assert started.status_code == 202, started.text
    for _ in range(150):
        await asyncio.sleep(0.02)
        job = (await client.get(f"/api/jobs/{started.json()['id']}")).json()
        if job["status"] in ("done", "error"):
            break
    user = next(item["content"] for item in seen[0] if item["role"] == "user")
    assert "inbox/notes.zip" in user
    assert "pip" in user
    detail = (await client.get(f"/api/chats/{chat['id']}")).json()
    assert detail["messages"][0]["meta"]["files"][0]["name"] == "notes.zip"
    rejected = await client.post(f"/api/chats/{chat['id']}/run", json={"content": "ещё", "files": ["../secret"]})
    assert rejected.status_code == 400, rejected.text


@pytest.mark.asyncio
async def test_pentest_keeps_the_file_when_no_attackbox(client, monkeypatch):
    await _user(client, "box@example.com")
    monkeypatch.setattr(pentest_workers, "launch", lambda *args, **kwargs: None)
    eid = (await client.post("/api/engagements", json={"target": "example.com"})).json()["id"]
    saved = await client.put(f"/api/engagements/{eid}/inbox?name=dump.zip", content=b"zip-bytes")
    assert saved.status_code == 200, saved.text
    run = await client.post(f"/api/engagements/{eid}/agent/chat", json={
        "content": "посмотри дамп", "mode": "plan", "model": "m", "files": [saved.json()["name"]]})
    assert run.status_code == 202, run.text
    body = run.json()
    assert "inbox/dump.zip" in body["task"]
    assert "attackbox не выбран" in body["task"]
    monkeypatch.setattr(files, "MAX_UPLOAD_BYTES", 4)
    assert (await client.put(f"/api/engagements/{eid}/inbox?name=dump.zip", content=b"0123456789")).status_code == 413
