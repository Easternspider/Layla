"""Тесты пикера моделей и управления моделями провайдера (спец. §5.1, §5.2)."""
from __future__ import annotations

import pytest

import app.services.provider_client as pc


async def _setup(client):
    await client.post(
        "/api/auth/register",
        json={"email": "mdl@example.com", "password": "hunter2hunter2"},
    )
    p = await client.post(
        "/api/providers",
        json={
            "name": "abyss",
            "kind": "openai_compatible",
            "base_url": "http://prov.local/v1",
            "default_model": "abyss/kimi-k3",
            "active": True,
        },
    )
    return p.json()["id"]


@pytest.mark.asyncio
async def test_models_fallback_to_default(client):
    await _setup(client)
    models = (await client.get("/api/models")).json()
    assert any(m["name"] == "abyss/kimi-k3" for m in models)


@pytest.mark.asyncio
async def test_same_model_name_stays_on_the_selected_provider(client, db_sessionmaker):
    from sqlalchemy import select
    from app.models.user import User
    await client.post("/api/auth/register", json={"email": "route@example.com", "password": "hunter2hunter2"})
    other = (await client.post("/api/providers", json={
        "name": "Other", "kind": "openai_compatible", "base_url": "https://api.openai.com/v1", "active": True})).json()
    codex = (await client.post("/api/providers", json={
        "name": "Codex (аккаунт)", "kind": "openai_compatible",
        "base_url": "https://chatgpt.com/backend-api/codex", "active": True})).json()
    for pid in (other["id"], codex["id"]):
        saved = await client.put(f"/api/providers/{pid}/models", json={"models": [{"name": "gpt-6-luna", "enabled": True}]})
        assert saved.status_code == 200
    async with db_sessionmaker() as session:
        user = await session.scalar(select(User).where(User.email == "route@example.com"))
        chosen = await pc.resolve_provider(session, user.id, "gpt-6-luna", codex["id"])
    assert chosen is not None and chosen.id == codex["id"]
    assert chosen.base_url == "https://chatgpt.com/backend-api/codex"


@pytest.mark.asyncio
async def test_fetch_and_toggle_models(client, monkeypatch):
    pid = await _setup(client)

    async def fake_list_models(provider, key):
        return ["abyss/kimi-k3", "abyss/gpt-5", "abyss/claude-5"]

    monkeypatch.setattr(pc, "list_models", fake_list_models)

    # Загрузить список у провайдера — сохраняется, все включены.
    fetched = (await client.post(f"/api/providers/{pid}/fetch-models")).json()
    assert {m["name"] for m in fetched} == {"abyss/kimi-k3", "abyss/gpt-5", "abyss/claude-5"}
    assert all(m["enabled"] for m in fetched)

    # В пикере видны все включённые.
    models = (await client.get("/api/models")).json()
    assert len(models) == 3

    # Выключаем две модели → в пикере остаётся одна.
    await client.put(f"/api/providers/{pid}/models", json={"models": [
        {"name": "abyss/kimi-k3", "enabled": True},
        {"name": "abyss/gpt-5", "enabled": False},
        {"name": "abyss/claude-5", "enabled": False},
    ]})
    models2 = (await client.get("/api/models")).json()
    assert [m["name"] for m in models2] == ["abyss/kimi-k3"]


@pytest.mark.asyncio
async def test_fetch_preserves_enabled_flags(client, monkeypatch):
    pid = await _setup(client)

    async def fake_list_models(provider, key):
        return ["m1", "m2"]

    monkeypatch.setattr(pc, "list_models", fake_list_models)
    await client.post(f"/api/providers/{pid}/fetch-models")
    await client.put(f"/api/providers/{pid}/models", json={"models": [
        {"name": "m1", "enabled": False},
        {"name": "m2", "enabled": True},
    ]})
    # Повторный fetch (тот же список) сохраняет ранее выставленные флаги.
    refetched = (await client.post(f"/api/providers/{pid}/fetch-models")).json()
    flags = {m["name"]: m["enabled"] for m in refetched}
    assert flags == {"m1": False, "m2": True}
