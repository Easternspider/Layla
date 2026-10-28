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
async def test_read_requires_the_created_password():
    with pytest.raises(ValueError):
        await inbox.read_inbox("person@example.test", "")
