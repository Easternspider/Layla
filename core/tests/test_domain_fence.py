"""Engagement targets stay in pentest and do not run in other sections."""
import pytest

from app.services import code_research, domain_fence, project_agent, web_research
from tests.test_jobs import _wait_job

pytestmark = pytest.mark.asyncio


async def test_agent_chat_refuses_engagement_target_and_leaves_other_work(client, monkeypatch):
    await client.post("/api/auth/register", json={"email": "fence@example.com", "password": "hunter2hunter2"})
    await client.post("/api/providers", json={
        "name": "M", "kind": "openai_compatible", "base_url": "http://p/v1", "default_model": "m", "active": True,
    })
    assert (await client.post("/api/engagements", json={"target": "example.com"})).status_code == 201
    calls = []

    async def fake_run(*args, **kwargs):
        calls.append(True)
        yield {"delta": "Комиссия указана на странице."}

    monkeypatch.setattr(project_agent, "run", fake_run)
    chat = (await client.post("/api/chats", json={"domain": "agent", "title": "Новая задача", "model": "m"})).json()
    blocked = await client.post(
        f"/api/chats/{chat['id']}/run", json={"content": "найди ip example.com", "model": "m"})
    assert blocked.status_code == 202, blocked.text
    body = await _wait_job(client, blocked.json()["id"])
    assert body["status"] == "done", body
    assert calls == []
    detail = (await client.get(f"/api/chats/{chat['id']}")).json()
    assert any("Пентест" in m["content"] for m in detail["messages"] if m["role"] == "assistant")
    allowed = await client.post(
        f"/api/chats/{chat['id']}/run", json={"content": "какая комиссия upwork", "model": "m"})
    assert allowed.status_code == 202, allowed.text
    followed = await _wait_job(client, allowed.json()["id"])
    assert followed["status"] == "done", followed
    assert calls == [True]


async def test_web_fetch_of_engagement_host_does_not_leave_the_section(client, db_sessionmaker, monkeypatch):
    await client.post("/api/auth/register", json={"email": "fetch-fence@example.com", "password": "hunter2hunter2"})
    me = (await client.get("/api/auth/me")).json()
    assert (await client.post("/api/engagements", json={"target": "example.com"})).status_code == 201
    called = []

    async def page(url, blocked=()):
        called.append(url)
        return {"url": url, "text": "Example Domain"}

    monkeypatch.setattr(web_research, "read_web_page", page)
    token = domain_fence.bind(db_sessionmaker, me["id"])
    try:
        denied = await code_research.execute("web_fetch", {"url": "https://example.com"})
        assert "Пентест" in denied["error"]
        assert called == []
        opened = await code_research.execute("web_fetch", {"url": "https://www.upwork.com/fees"})
        assert opened["url"].endswith("/fees")
        assert called == ["https://www.upwork.com/fees"]
    finally:
        domain_fence.reset(token)


async def test_pentest_run_does_not_create_an_agent_chat(client, monkeypatch):
    from tests.test_agent_api import _setup
    eid = await _setup(client, monkeypatch)
    before = (await client.get("/api/chats?domain=agent")).json()
    run = await client.post(f"/api/engagements/{eid}/agent/runs", json={"task": "найди ip example.com"})
    assert run.status_code == 201, run.text
    after = (await client.get("/api/chats?domain=agent")).json()
    assert [item["id"] for item in after] == [item["id"] for item in before]
    listed = (await client.get(f"/api/engagements/{eid}/agent/runs")).json()
    assert listed and listed[0]["task"] == "найди ip example.com"
