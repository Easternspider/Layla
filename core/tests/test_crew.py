"""Orchestra domain: three specialists, isolated build folders, and a chat list."""
import asyncio
from pathlib import Path

import pytest

from app.models.chat import Chat
from app.models.crew import CrewMember
from app.models.enums import Domain, ProviderKind
from app.models.job import Job
from app.models.provider import Provider
from app.models.user import Project, User, Workspace
from app.services import crew
from app.services.crew import SpawnAgent
from app.services.crew_browser import check_navigation, image_mime, interpret_captcha, nth_hint, private_host, ref_number


async def _world(maker, tmp_path):
    async with maker() as session:
        user = User(email="crew@example.com", pw_hash="x")
        session.add(user)
        await session.flush()
        workspace = Workspace(owner_id=user.id, name="w", projects_dir=str(tmp_path))
        session.add(workspace)
        await session.flush()
        project = Project(workspace_id=workspace.id, name="Оркестр", path=str(tmp_path), kind="chat_workspace")
        session.add(project)
        await session.flush()
        chat = Chat(owner_id=user.id, domain=Domain.crew, title="Сбор", project_id=project.id, model="m")
        provider = Provider(owner_id=user.id, name="local", kind=ProviderKind.openai_compatible,
                            active=True, enabled=True, default_model="m")
        session.add(chat)
        session.add(provider)
        await session.commit()
        return user.id, chat.id, project.id, provider.id


@pytest.mark.asyncio
async def test_three_slots_and_isolated_build(db_sessionmaker, tmp_path):
    owner, chat_id, project_id, provider_id = await _world(db_sessionmaker, tmp_path)
    lead = crew.Manager(
        db_sessionmaker, owner, chat_id, project_id, str(tmp_path),
        provider_id=provider_id, model="m", caps={}, mode="auto", permissions=None,
    )
    gate = asyncio.Event()
    started = asyncio.Event()
    running = 0

    async def hang(member_id, handle):
        nonlocal running
        running += 1
        if running == 3:
            started.set()
        await gate.wait()

    lead._execute = hang
    for index in range(3):
        spawned = await lead.spawn(SpawnAgent(role="research", task=f"часть {index}"))
        assert spawned["agent"]["status"] == "queued"
        assert spawned["agent"]["id"] in lead.attached
    with pytest.raises(ValueError, match="3 субагента"):
        await lead.spawn(SpawnAgent(role="review", task="четвёртый"))
    await asyncio.wait_for(started.wait(), timeout=5)
    assert len(lead.attached) == 3
    gate.set()
    pending = [task for task in asyncio.all_tasks() if task.get_name().startswith("layla-job")]
    await asyncio.wait(pending, timeout=5)
    plan = crew.Manager(
        db_sessionmaker, owner, chat_id, project_id, str(tmp_path),
        provider_id=provider_id, model="m", caps={}, mode="plan", permissions=None,
    )
    with pytest.raises(ValueError, match="плана"):
        await plan.spawn(SpawnAgent(role="build", task="нельзя"))


@pytest.mark.asyncio
async def test_build_report_stays_in_its_folder(db_sessionmaker, tmp_path):
    owner, chat_id, project_id, provider_id = await _world(db_sessionmaker, tmp_path)
    lead = crew.Manager(
        db_sessionmaker, owner, chat_id, project_id, str(tmp_path),
        provider_id=provider_id, model="m", caps={}, mode="auto", permissions=None,
    )

    async def build(role, task, root, provider, key, model, caps):
        assert role == "build"
        assert Path(root).parent == tmp_path / "crew"
        Path(root, "out.txt").write_text(task, encoding="utf-8")
        return "собрал файл"

    lead.run_member = build
    spawned = await lead.spawn(SpawnAgent(role="build", task="сделай файл", detached=True))
    agent_id = spawned["agent"]["id"]
    assert agent_id not in lead.attached
    assert await lead.finish_attached() is None
    report = await asyncio.wait_for(lead.wait(agent_id, 10), timeout=15)
    assert report["agents"][0]["status"] == "done"
    assert report["agents"][0]["report"] == "собрал файл"
    read = await lead.read(agent_id)
    assert read["agent"]["files"] == ["out.txt"]
    assert (tmp_path / "crew" / agent_id / "out.txt").read_text(encoding="utf-8") == "сделай файл"
    assert "write_file" not in crew.ALLOW["review"]
    assert "spawn_agent" not in crew.ALLOW["build"]
    assert "run_command" in crew.ALLOW["build"]


@pytest.mark.asyncio
async def test_stop_frees_the_slot(db_sessionmaker, tmp_path):
    owner, chat_id, project_id, provider_id = await _world(db_sessionmaker, tmp_path)
    async with db_sessionmaker() as session:
        job = Job(owner_id=owner, domain="crew", kind="crew.member", title="review", status="done")
        session.add(job)
        await session.flush()
        member = CrewMember(
            owner_id=owner, chat_id=chat_id, project_id=project_id, job_id=job.id, slot=0,
            role="review", task="смотри", status="running", report="", detached=False,
        )
        session.add(member)
        await session.commit()
        member_id = member.id
    stopped = await crew.stop(db_sessionmaker, owner, chat_id, member_id)
    assert stopped["agent"]["status"] == "cancelled"
    lead = crew.Manager(
        db_sessionmaker, owner, chat_id, project_id, str(tmp_path),
        provider_id=provider_id, model="m", caps={}, mode="auto", permissions=None,
    )

    async def finished(member_id, handle):
        return None

    lead._execute = finished
    spawned = await lead.spawn(SpawnAgent(role="research", task="после остановки"))
    assert spawned["agent"]["id"] != member_id
    pending = [task for task in asyncio.all_tasks() if task.get_name().startswith("layla-job")]
    await asyncio.wait(pending, timeout=5)


@pytest.mark.asyncio
async def test_crew_chat_api(client):
    await client.post("/api/auth/register", json={"email": "crew-api@example.com", "password": "hunter2hunter2"})
    created = await client.post("/api/chats", json={"domain": "crew", "title": "Оркестр"})
    assert created.status_code == 201
    chat_id = created.json()["id"]
    assert created.json()["domain"] == "crew"
    listed = await client.get(f"/api/chats/{chat_id}/crew")
    assert listed.status_code == 200
    assert listed.json() == []
    missing = await client.post(f"/api/chats/{chat_id}/crew/missing/stop")
    assert missing.status_code == 404
    assert Domain.crew.value == "crew"
    assert "субагент" in crew.NOTE and "трёх" in crew.NOTE
    assert "browse_open" in crew.SCHEMAS and "browse_see" in crew.SCHEMAS and "browse_captcha" in crew.SCHEMAS
    assert interpret_captcha("CLICK")["kind"] == "click"
    assert interpret_captcha("TILES: 1, 3, 5")["tiles"] == [1, 3, 5]
    assert interpret_captcha("Ab7k") == {"kind": "type", "text": "Ab7k"}
    assert private_host("127.0.0.1") and private_host("localhost")
    assert not private_host("example.com")
    assert image_mime(b"\xff\xd8\xff\x00") == "image/jpeg"
    assert ref_number("3") == 3 and ref_number("n:12") == 12 and ref_number("Войти") is None
    assert nth_hint("css:a:nth-of-type(3)") == ("a", 3)
    assert nth_hint("button:nth-child(2)") == ("button", 2)
    assert nth_hint("Войти") is None
    with pytest.raises(ValueError):
        check_navigation("http://example.com/path")
    with pytest.raises(ValueError):
        check_navigation("https://127.0.0.1/secret")


@pytest.mark.asyncio
async def test_plan_can_look_but_not_type(db_sessionmaker, tmp_path):
    owner, chat_id, project_id, provider_id = await _world(db_sessionmaker, tmp_path)
    lead = crew.Manager(
        db_sessionmaker, owner, chat_id, project_id, str(tmp_path),
        provider_id=provider_id, model="m", caps={}, mode="plan", permissions=None,
    )
    calls = []

    class Fake:
        async def open(self, url):
            calls.append(url)
            return {"url": url, "title": "Пример", "text": "страница", "items": []}

        async def type_text(self, target, text, submit):
            calls.append(target)
            return {"url": "https://example.com", "title": "Пример", "text": text, "items": []}

    lead.browser = Fake()
    opened = await lead.execute("browse_open", {"url": "https://example.com/docs"})
    assert opened["title"] == "Пример"
    assert calls == ["https://example.com/docs"]
    with pytest.raises(ValueError, match="только смотреть"):
        await lead.execute("browse_type", {"target": "Email", "text": "a@b.c"})
    assert calls == ["https://example.com/docs"]
