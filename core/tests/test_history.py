"""Сжатие контекста: ужатие длинного хода и ручная сводка истории."""
from __future__ import annotations

import asyncio
import json

import pytest

from app.services import history
from tests.test_provider_resilience import _chat_with_history, _http, _setup, _wire


def _round(name, args, result, call_id):
    call = {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}
    return [{"role": "assistant", "content": None, "tool_calls": [call]},
            {"role": "tool", "tool_call_id": call_id, "content": json.dumps(result)}]


def test_long_run_shrinks_old_tool_results_but_keeps_recent_rounds():
    anchor = {"role": "user", "content": "сделай сайт"}
    big = "x" * 30_000
    conversation = [{"role": "system", "content": "sys"}, anchor]
    conversation += _round("write_file", {"path": "a.html", "content": big, "expected_sha256": None},
                           {"change": {"path": "a.html"}}, "c1")
    conversation += _round("read_file", {"path": "a.html"}, {"path": "a.html", "content": big, "sha256": "s1"}, "c2")
    conversation += _round("read_file", {"path": "b.html"}, {"path": "b.html", "content": big, "sha256": "s2"}, "c3")
    conversation += _round("read_file", {"path": "c.html"}, {"path": "c.html", "content": big, "sha256": "s3"}, "c4")
    shrunk = history.shrink_run(conversation, anchor, {"context": 32_000, "max_output": 4096})
    assert shrunk >= 2
    written = json.loads(conversation[2]["tool_calls"][0]["function"]["arguments"])
    assert written["content"] == "[30000 символов — уже применено]" and written["path"] == "a.html"
    assert json.loads(conversation[5]["content"]) == {"path": "a.html", "sha256": "s1", "note": history._HIDDEN}
    # Последние два шага — целиком: модель работает с ними прямо сейчас.
    assert json.loads(conversation[-1]["content"])["content"] == big
    assert json.loads(conversation[-3]["content"])["content"] == big
    assert conversation[1] is anchor


def test_old_command_log_becomes_a_reference():
    anchor = {"role": "user", "content": "проверь"}
    log = "e" * 5000
    conversation = [{"role": "system", "content": "sys"}, anchor]
    for i in range(3):
        conversation += _round("run_command", {"command": f"pytest {i}"},
                               {"command": f"pytest {i}", "exit_code": 1, "output": log}, f"c{i}")
    assert history.shrink_run(conversation, anchor, {"context": 4000, "max_output": 200}) >= 1
    first = json.loads(conversation[3]["content"])
    assert first["command"] == "pytest 0" and first["exit_code"] == 1
    assert "output" not in first and first["note"] == history._HIDDEN
    assert json.loads(conversation[-1]["content"])["output"] == log


def test_shrink_waits_until_the_window_is_three_quarters_full():
    anchor = {"role": "user", "content": "привет"}
    conversation = [{"role": "system", "content": "sys"}, anchor,
                    *_round("read_file", {"path": "a"}, {"path": "a", "content": "x" * 3000, "sha256": "s"}, "c1")]
    before = json.dumps(conversation)
    # 3000 символов — это далеко не 75% окна в 40_000 токенов.
    assert history.shrink_run(conversation, anchor, {"context": 40_000, "max_output": 1024}) == 0
    assert json.dumps(conversation) == before


@pytest.mark.asyncio
async def test_fold_summarizes_the_old_prefix_and_keeps_recent_turns(monkeypatch):
    anchor = {"role": "user", "content": "текущий вопрос"}
    conversation = [{"role": "system", "content": "sys"}]
    for i in range(8):
        conversation.append({"role": "user" if i % 2 == 0 else "assistant", "content": f"#{i} " + "y" * 800})
    conversation.append(anchor)
    conversation.insert(2, {"role": "tool", "tool_call_id": "old", "content": "x" * 2000})

    async def fake_summarize(_provider, _key, _model, _caps, _previous, items, on_event=None):
        assert any("#0" in item["content"] for item in items)
        assert all("#7" not in item["content"] for item in items)
        return "задача жива, сделано начало"

    monkeypatch.setattr(history, "summarize", fake_summarize)
    removed = await history.fold_old(None, None, "m", conversation, anchor, {"context": 2000, "max_output": 200})
    assert removed > 0
    summary = next(m["content"] for m in conversation if m.get("role") == "system" and m["content"].startswith(history.SUMMARY_HEADER))
    assert "задача жива" in summary
    assert conversation[-1] is anchor
    assert any("#7" in m.get("content", "") for m in conversation)


def test_memory_note_is_attached_to_the_summary_once(tmp_path):
    notes = tmp_path / ".layla"
    notes.mkdir()
    (notes / "progress.md").write_text("задача: сайт\nсделано: каркас", encoding="utf-8")
    conversation = [{"role": "system", "content": history.SUMMARY_HEADER + "кратко"}]
    history.attach_memory(conversation, str(tmp_path))
    history.attach_memory(conversation, str(tmp_path))
    assert conversation[0]["content"].count("задача: сайт") == 1
    assert "что делается" in conversation[0]["content"]


@pytest.mark.asyncio
async def test_thin_summary_is_rewritten_once(monkeypatch):
    replies = ["коротко", "НЕ ХВАТАЕТ: нет задачи", "задача: сайт. делается вёрстка. сделан каркас."]

    async def fake_complete(_provider, _key, _model, _caps, conversation, on_event=None):
        return replies.pop(0)

    monkeypatch.setattr(history, "_complete", fake_complete)
    text = await history.summarize(None, None, "m", {"context": 8000}, None,
                                   [{"role": "user", "content": "сделай сайт"}])
    assert "каркас" in text and replies == []


def test_short_run_is_untouched():
    anchor = {"role": "user", "content": "привет"}
    conversation = [anchor, *_round("read_file", {"path": "a"}, {"path": "a", "content": "hi", "sha256": "s"}, "c1")]
    before = json.dumps(conversation)
    assert history.shrink_run(conversation, anchor, {}) == 0
    assert json.dumps(conversation) == before


async def _wait(client, job_id):
    for _ in range(300):
        await asyncio.sleep(0.02)
        state = (await client.get(f"/api/jobs/{job_id}")).json()
        if state["status"] not in ("queued", "running"):
            return state
    return state


@pytest.mark.asyncio
async def test_manual_compaction_keeps_recent_messages(client, monkeypatch, db_sessionmaker):
    await _setup(client)
    chat = await _chat_with_history(client, db_sessionmaker, turns=10, size=80)
    await client.patch(f"/api/chats/{chat['id']}", json={"title": "Сайт"})
    sent: list = []
    _http(monkeypatch, [_wire(text="- пользователь делает сайт")], sent)
    job = (await client.post(f"/api/chats/{chat['id']}/compact")).json()
    state = await _wait(client, job["id"])
    assert state["status"] == "done", state
    assert state["result"]["count"] == 6
    messages = (await client.get(f"/api/chats/{chat['id']}")).json()["messages"]
    assert [m["role"] for m in messages].count("system") == 1
    assert messages[6]["meta"]["kind"] == "summary" and messages[6]["content"] == "- пользователь делает сайт"
    assert "#0" in sent[0]["messages"][1]["content"] and "#6" not in sent[0]["messages"][1]["content"]


@pytest.mark.asyncio
async def test_nothing_to_compact_in_short_chat(client, monkeypatch, db_sessionmaker):
    await _setup(client)
    chat = await _chat_with_history(client, db_sessionmaker, turns=3, size=40)
    sent: list = []
    _http(monkeypatch, [_wire(text="сводка")], sent)
    state = await _wait(client, (await client.post(f"/api/chats/{chat['id']}/compact")).json()["id"])
    assert state["status"] == "done" and sent == []
    assert "Сжимать нечего" in state["steps"][-1]["text"]
