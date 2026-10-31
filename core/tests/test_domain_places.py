"""Each section keeps its own chats, tasks and folders."""
import json
from pathlib import Path
from uuid import UUID

import pytest

from app.models.user import Project
from app.services import project_agent, provider_client
from tests.test_jobs import _wait_job
from tests.test_pentest_workers import until


def test_old_tree_is_kept_until_the_new_one_exists(tmp_path):
    from app.services.places import prefer

    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir()
    assert prefer(new, old) == old
    new.mkdir()
    assert prefer(new, old) == new


@pytest.mark.asyncio
async def test_agent_chats_have_private_folders_and_do_not_open_other_sections(client, db_sessionmaker, monkeypatch):
    await client.post("/api/auth/register", json={"email": "places@example.com", "password": "hunter2hunter2"})
    await client.post("/api/providers", json={
        "name": "M", "kind": "openai_compatible", "base_url": "http://p/v1", "default_model": "m", "active": True,
    })
    owner = (await client.get("/api/auth/me")).json()["id"]
    repo = (await client.post("/api/projects", json={"name": "Repo"})).json()
    code = (await client.post("/api/chats", json={"domain": "code", "project_id": repo["id"], "model": "m"})).json()
    assert code["project_id"] == repo["id"]

    async def fake_run(*args, **kwargs):
        yield {"delta": "ok"}

    monkeypatch.setattr(project_agent, "run", fake_run)
    first = (await client.post("/api/agent/chats", json={"title": "Одна", "project_id": repo["id"]})).json()
    second = (await client.post("/api/agent/chats", json={"title": "Другая"})).json()
    assert first["domain"] == "agent" and second["domain"] == "agent"
    assert first["project_id"] and first["project_id"] not in (repo["id"], second["project_id"])

    async def folder(project_id: str) -> Path:
        async with db_sessionmaker() as session:
            return Path((await session.get(Project, project_id)).path)

    one, two = await folder(first["project_id"]), await folder(second["project_id"])
    assert one.is_dir() and two.is_dir() and one != two
    for chat, path in ((first, one), (second, two)):
        assert path.parts[-3:] == ("agent", UUID(owner).hex, UUID(chat["id"]).hex)

    osint = (await client.post("/api/chats", json={"domain": "osint", "model": "m"})).json()
    assert (await client.post(f"/api/agent/chats/{code['id']}/run", json={"content": "привет", "model": "m"})).status_code == 404
    assert (await client.post(f"/api/agent/chats/{osint['id']}/run", json={"content": "привет", "model": "m"})).status_code == 404
    assert (await client.get(f"/api/chats/{code['id']}", params={"domain": "agent"})).status_code == 404
    assert (await client.get(f"/api/chats/{osint['id']}", params={"domain": "agent"})).status_code == 404
    assert (await client.get(f"/api/chats/{osint['id']}")).status_code == 200
    listed = (await client.get("/api/chats", params={"domain": "agent"})).json()
    assert {item["id"] for item in listed} == {first["id"], second["id"]}

    started = await client.post(f"/api/agent/chats/{first['id']}/run", json={"content": "какая комиссия upwork", "model": "m"})
    assert started.status_code == 202, started.text
    assert (await _wait_job(client, started.json()["id"]))["status"] == "done"

    engagement = (await client.post("/api/engagements", json={"target": "example.com"})).json()
    from app.services.places import engagement_home
    assert engagement_home(owner, engagement["id"]).is_dir()

    async def complete(*args, **kwargs):
        return json.dumps({"action": "finish", "text": "готово"})

    monkeypatch.setattr(provider_client, "complete", complete)
    run = await client.post(f"/api/engagements/{engagement['id']}/chat", json={"content": "найди ip", "mode": "plan"})
    assert run.status_code == 202, run.text
    await until(client, run.json()["workers"][0]["id"], lambda worker: worker["status"] not in ("queued", "running"))

    agent_jobs = (await client.get("/api/jobs", params={"domain": "agent"})).json()
    assert agent_jobs and all(job["domain"] in ("agent", "crew") for job in agent_jobs)
    assert all(job["result"].get("engagement_id") != engagement["id"] for job in agent_jobs)
    pentest_jobs = (await client.get("/api/jobs", params={"domain": "pentest"})).json()
    assert pentest_jobs and all(job["domain"] == "pentest" for job in pentest_jobs)
    assert not any(job["chat_id"] == first["id"] for job in pentest_jobs)
    everything = (await client.get("/api/jobs")).json()
    assert {job["domain"] for job in everything} >= {"agent", "pentest"}
