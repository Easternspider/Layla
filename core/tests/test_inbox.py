"""mail.tm inbox used only to receive a registration letter."""
import httpx
import pytest

from app.services import inbox
from app.services.pentest_workers import Action


@pytest.mark.asyncio
async def test_create_and_read_mailbox(monkeypatch):
    assert Action.model_validate({"action": "create_inbox"}).action == "create_inbox"

    def serve(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/domains":
            return httpx.Response(200, json={"hydra:member": [{"domain": "example.test", "isActive": True}]})
        if request.url.path == "/accounts":
            return httpx.Response(201, json={"address": "layla@example.test"})
        if request.url.path == "/token":
            return httpx.Response(200, json={"token": "fixture-token"})
        if request.url.path == "/messages":
            return httpx.Response(200, json={"hydra:member": [{"id": "m1", "from": {"address": "noreply@target.test"},
                                                              "subject": "Confirm", "intro": "code 1234", "seen": False}]})
        if request.url.path == "/messages/m1":
            return httpx.Response(200, json={"id": "m1", "from": {"address": "noreply@target.test"},
                                             "subject": "Confirm", "text": "Open https://target.test/verify?code=1234"})
        return httpx.Response(404)

    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real(transport=httpx.MockTransport(serve), **kwargs))
    created = await inbox.create_inbox()
    assert created["address"].endswith("@example.test")
    assert created["password"]
    listed = await inbox.read_inbox(created["address"], created["password"])
    assert listed["messages"][0]["subject"] == "Confirm"
    letter = await inbox.read_inbox(created["address"], created["password"], "m1")
    assert "verify?code=1234" in letter["text"]


@pytest.mark.asyncio
async def test_create_inbox_skips_a_rejected_domain(monkeypatch):
    def serve(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/domains":
            return httpx.Response(200, json={"hydra:member": [
                {"domain": "blocked.test", "isActive": True},
                {"domain": "fresh.test", "isActive": True},
            ]})
        if request.url.path == "/accounts":
            return httpx.Response(201, json={})
        if request.url.path == "/token":
            return httpx.Response(200, json={"token": "fixture-token"})
        return httpx.Response(404)

    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real(transport=httpx.MockTransport(serve), **kwargs))
    created = await inbox.create_inbox("blocked.test")
    assert created["domain"] == "fresh.test"
    again = await inbox.create_inbox()
    assert again["domain"] == "blocked.test"


@pytest.mark.asyncio
async def test_mailbox_providers_are_tried_in_turn(monkeypatch):
    inbox._cursor = 0
    inbox._issued.clear()
    seen = []

    def serve(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        if request.url.host == "www.1secmail.com" and request.url.params.get("action") == "genRandomMailbox":
            return httpx.Response(200, json=["layla@sec.test"])
        if request.url.host == "www.1secmail.com" and request.url.params.get("action") == "getMessages":
            return httpx.Response(200, json=[{"id": 7, "from": "noreply@target.test", "subject": "Confirm"}])
        if request.url.host == "www.1secmail.com":
            return httpx.Response(200, json={"id": 7, "from": "noreply@target.test", "subject": "Confirm", "textBody": "code 55"})
        if request.url.host == "api.guerrillamail.com" and request.url.params.get("f") == "get_email_address":
            return httpx.Response(200, json={"email_addr": "layla@guer.test", "sid_token": "sid"})
        return httpx.Response(503)

    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real(transport=httpx.MockTransport(serve), **kwargs))
    first = await inbox.create_inbox()
    assert first["provider"] == "1secmail" and first["password"] == "1secmail"
    letter = await inbox.read_inbox(first["address"], first["password"], "7")
    assert "code 55" in letter["text"]
    second = await inbox.create_inbox()
    assert second["provider"] == "guerrilla" and second["password"] == "guerrilla:sid"
    assert "api.mail.tm" not in seen


@pytest.mark.asyncio
async def test_read_requires_the_created_password():
    with pytest.raises(ValueError):
        await inbox.read_inbox("person@example.test", "")
