"""ChatGPT device login for Codex. Tokens stay on the server and off api.openai.com."""
import base64
import json

import httpx
import pytest

from app.models.codex_login import CodexLogin
from app.models.provider import Provider
from app.security import crypto
from app.services import codex_oauth, provider_client, tool_chat
from app.services.provider_errors import ProviderError


def _jwt(payload):
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return "h." + raw + ".s"


def test_account_id_and_verify_host():
    from urllib.parse import urlsplit
    token = _jwt({"https://api.openai.com/auth": {"chatgpt_account_id": "acct_1"}})
    assert codex_oauth.account_id(token) == "acct_1"
    assert codex_oauth.account_id(_jwt({"account_id": "acct_top"})) == "acct_top"
    assert urlsplit(codex_oauth.VERIFY).hostname == "auth.openai.com"
    assert urlsplit(codex_oauth.BASE_URL).hostname == "chatgpt.com"
    assert "api.openai.com" not in codex_oauth.BASE_URL
    with pytest.raises(ValueError):
        codex_oauth._check_url("https://evil.example/login")
    with pytest.raises(ValueError):
        codex_oauth._check_url("https://user:pass@auth.openai.com/codex/device")


@pytest.mark.asyncio
async def test_device_stays_on_auth_openai(monkeypatch):
    real = httpx.AsyncClient
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(404, json={"error": "disabled"})

    monkeypatch.setattr(codex_oauth.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handle), **kw))
    with pytest.raises(ValueError, match="Security"):
        await codex_oauth.request_device()
    assert str(seen[0].url) == "https://auth.openai.com/api/accounts/deviceauth/usercode"


def test_headers_are_not_applied_to_api_keys():
    key = codex_oauth.wire_key({"access_token": "tok", "account_id": "acct_1"})
    headers = provider_client._headers(Provider(name="Codex", base_url=codex_oauth.BASE_URL), key)
    assert headers["Authorization"] == "Bearer tok"
    assert headers["ChatGPT-Account-ID"] == "acct_1"
    assert headers["originator"] == "layla"
    plain = provider_client._headers(Provider(name="OpenAI", base_url="https://api.openai.com/v1"), "sk-test")
    assert plain["Authorization"] == "Bearer sk-test"
    assert "ChatGPT-Account-ID" not in plain
    assert "originator" not in plain


@pytest.mark.asyncio
async def test_models_use_slug(monkeypatch):
    real = httpx.AsyncClient

    def handle(request):
        assert str(request.url).startswith(codex_oauth.BASE_URL + "/models")
        assert request.url.params["client_version"] == codex_oauth.CLIENT_VERSION
        assert "api.openai.com" not in str(request.url)
        assert request.headers["chatgpt-account-id"] == "acct_1"
        return httpx.Response(200, json={"models": [
            {"slug": "gpt-5.4", "display_name": "GPT"},
            {"slug": "hidden-one", "hidden": True},
        ]})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handle), **kw))
    names = await provider_client.list_models(
        Provider(name="Codex", base_url=codex_oauth.BASE_URL),
        codex_oauth.wire_key({"access_token": "tok", "account_id": "acct_1"}),
    )
    assert names == ["gpt-5.4"]


@pytest.mark.asyncio
async def test_chat_posts_to_chatgpt_codex(monkeypatch):
    real = httpx.AsyncClient

    def handle(request):
        assert str(request.url) == codex_oauth.BASE_URL + "/responses"
        assert request.headers["authorization"] == "Bearer tok"
        assert request.headers["chatgpt-account-id"] == "acct_1"
        assert "x-grok-client-version" not in request.headers
        return httpx.Response(200, text='data: {"type":"response.output_text.delta","delta":"ok"}\n\n'
                              'data: {"type":"response.completed","response":{"status":"completed"}}\n\n')

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handle), **kw))
    provider = Provider(name="Codex", base_url=codex_oauth.BASE_URL)
    out = []
    async for item in tool_chat.stream_turn(
        provider, codex_oauth.wire_key({"access_token": "tok", "account_id": "acct_1"}),
        "gpt-5.4", [{"role": "user", "content": "hi"}], [],
    ):
        out.append(item)
    assert out == [("content", "ok")]


@pytest.mark.asyncio
async def test_final_message_is_kept_when_codex_does_not_stream_deltas(monkeypatch):
    real = httpx.AsyncClient
    message = {"type": "message", "role": "assistant", "content": [
        {"type": "output_text", "text": '{"action":"read_authorization"}'}]}

    def handle(request):
        body = json.loads(request.content)
        assert body["instructions"] == "protocol"
        assert [item["role"] for item in body["input"]] == ["user"]
        events = [
            {"type": "response.output_item.done", "output_index": 0, "item": {"type": "reasoning"}},
            {"type": "response.output_item.done", "output_index": 1, "item": message},
            {"type": "response.completed", "response": {"status": "completed", "output": [
                {"type": "reasoning"}, message]}},
        ]
        return httpx.Response(200, text="".join("data: " + json.dumps(event) + "\n\n" for event in events))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handle), **kw))
    text = await provider_client.complete(
        Provider(name="Codex", base_url=codex_oauth.BASE_URL),
        codex_oauth.wire_key({"access_token": "tok", "account_id": "acct_1"}),
        "gpt-6-luna",
        [{"role": "system", "content": "protocol"}, {"role": "user", "content": "go"}],
    )
    assert text == '{"action":"read_authorization"}'


@pytest.mark.asyncio
async def test_wrong_base_is_refused():
    provider = Provider(name="Codex", base_url="https://api.openai.com/v1")
    with pytest.raises(ProviderError):
        async for _item in tool_chat.stream_turn(
            provider, codex_oauth.wire_key({"access_token": "tok", "account_id": "acct_1"}),
            "gpt-5.4", [{"role": "user", "content": "hi"}], [],
        ):
            pass


async def register(client):
    await client.post("/api/auth/register", json={"email": "codex@example.com", "password": "hunter2hunter2"})


async def ready(db_sessionmaker, login_id):
    async with db_sessionmaker() as session:
        login = await session.get(CodexLogin, login_id)
        login.next_poll = 0
        await session.commit()


@pytest.fixture
def oauth(monkeypatch):
    async def device():
        return {"device_auth_id": "private-device", "user_code": "ABCD-EFGH",
                "verification_uri": codex_oauth.VERIFY, "expires_in": 600, "interval": 5}

    async def poll(device):
        assert device["device_auth_id"] == "private-device"
        return {"access_token": "private-access", "refresh_token": "private-refresh", "expires_in": 900,
                "id_token": _jwt({"https://api.openai.com/auth": {"chatgpt_account_id": "acct_9"}})}

    async def models(provider, key):
        assert provider.base_url == codex_oauth.BASE_URL
        assert codex_oauth.wire_credentials(key)["access_token"] == "private-access"
        assert codex_oauth.wire_credentials(key)["account_id"] == "acct_9"
        return ["gpt-5.4"]

    monkeypatch.setattr(codex_oauth, "request_device", device)
    monkeypatch.setattr(codex_oauth, "poll", poll)
    monkeypatch.setattr(provider_client, "list_models", models)


@pytest.mark.asyncio
async def test_account_connect_hides_secrets(client, oauth, db_sessionmaker):
    await register(client)
    started = await client.post("/api/providers/connect/codex/start")
    assert started.status_code == 200
    login = started.json()
    assert login["user_code"] == "ABCD-EFGH"
    assert login["verification_uri"] == "https://auth.openai.com/codex/device"
    assert "private-device" not in started.text
    early = await client.post(f"/api/providers/connect/codex/{login['login_id']}/poll")
    assert early.json()["status"] == "pending"
    await ready(db_sessionmaker, login["login_id"])
    done = await client.post(f"/api/providers/connect/codex/{login['login_id']}/poll")
    assert done.status_code == 200
    assert "private-access" not in done.text
    assert "private-refresh" not in done.text
    pid = done.json()["provider_id"]
    assert [m["name"] for m in (await client.get("/api/models")).json()] == ["gpt-5.4"]
    async with db_sessionmaker() as session:
        saved = await session.get(Provider, pid)
        assert saved.name == "Codex (аккаунт)"
        assert saved.base_url == codex_oauth.BASE_URL
        assert "private-access" not in saved.secret_ref
        creds = codex_oauth.read_credentials(saved.secret_ref)
        assert creds["refresh_token"] == "private-refresh"
        assert creds["account_id"] == "acct_9"
        assert (await session.get(CodexLogin, login["login_id"])).secret_ref != "private-device"


@pytest.mark.asyncio
async def test_denied_and_cancel(client, oauth, monkeypatch, db_sessionmaker):
    await register(client)
    login = (await client.post("/api/providers/connect/codex/start")).json()
    await ready(db_sessionmaker, login["login_id"])

    async def poll(device):
        return {"error": "access_denied"}

    monkeypatch.setattr(codex_oauth, "poll", poll)
    assert (await client.post(f"/api/providers/connect/codex/{login['login_id']}/poll")).json()["status"] == "denied"
    login = (await client.post("/api/providers/connect/codex/start")).json()
    assert (await client.delete(f"/api/providers/connect/codex/{login['login_id']}")).status_code == 204
    assert (await client.post(f"/api/providers/connect/codex/{login['login_id']}/poll")).status_code == 404


@pytest.mark.asyncio
async def test_refresh_is_persisted(client, oauth, monkeypatch, db_sessionmaker):
    await register(client)
    login = (await client.post("/api/providers/connect/codex/start")).json()
    await ready(db_sessionmaker, login["login_id"])
    pid = (await client.post(f"/api/providers/connect/codex/{login['login_id']}/poll")).json()["provider_id"]

    async def refresh(form):
        assert form["grant_type"] == "refresh_token"
        assert form["refresh_token"] == "private-refresh"
        assert "api.openai.com" not in codex_oauth.ISSUER
        return {"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 900,
                "id_token": _jwt({"https://api.openai.com/auth": {"chatgpt_account_id": "acct_9"}})}

    monkeypatch.setattr(codex_oauth, "_token", refresh)
    async with db_sessionmaker() as session:
        provider = await session.get(Provider, pid)
        data = codex_oauth.read_credentials(provider.secret_ref)
        data["expires_at"] = 0
        provider.secret_ref = crypto.encrypt(json.dumps(data))
        await session.commit()
        assert codex_oauth.wire_credentials(await provider_client.pick_key(session, provider))["access_token"] == "new-access"
    async with db_sessionmaker() as session:
        saved = await session.get(Provider, pid)
        assert codex_oauth.read_credentials(saved.secret_ref)["refresh_token"] == "new-refresh"
