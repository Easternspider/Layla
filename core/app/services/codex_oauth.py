"""ChatGPT device login used by the Codex CLI. Not an OpenAI API key.

Protocol: openai/codex login device_code_auth.rs and auth/manager.rs.
Only auth.openai.com receives the device code and refresh token.
"""
import base64
import json
import os
import time
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select

from app.models.provider import Provider
from app.security import crypto
from app.services.provider_errors import ProviderError

ISSUER = "https://auth.openai.com"
BASE_URL = "https://chatgpt.com/backend-api/codex"
CLIENT_ID = os.getenv("LAYLA_CODEX_CLIENT_ID", "app_EMoamEEZ73f0CkXaXp7hrann")
# ChatGPT rejects GET /models without this. It is the Codex CLI release, not a secret.
CLIENT_VERSION = os.getenv("LAYLA_CODEX_CLIENT_VERSION", "0.165.0")
TOKEN_PREFIX = "codex-oauth:"
VERIFY = ISSUER + "/codex/device"
ORIGINATOR = "layla"
ACCOUNT_HEADER = "ChatGPT-Account-ID"


def _jwt(token: str) -> dict:
    try:
        raw = token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    except (ValueError, IndexError, TypeError, json.JSONDecodeError):
        return {}


def account_id(id_token: str) -> str:
    claims = _jwt(id_token)
    auth = claims.get("https://api.openai.com/auth")
    if isinstance(auth, dict) and auth.get("chatgpt_account_id"):
        return str(auth["chatgpt_account_id"])
    for key in ("chatgpt_account_id", "account_id"):
        if isinstance(claims.get(key), str) and claims[key]:
            return claims[key]
    return ""


def _check_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "auth.openai.com" or parsed.username or parsed.password:
        raise ValueError("Invalid verification URL")


async def request_device():
    _check_url(VERIFY)
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(ISSUER + "/api/accounts/deviceauth/usercode",
                                     json={"client_id": CLIENT_ID}, headers={"Content-Type": "application/json"})
    if response.status_code == 404:
        raise ValueError("В ChatGPT включите вход по коду устройства: Settings → Security.")
    response.raise_for_status()
    data = response.json()
    code = data.get("user_code") or data.get("usercode")
    if not isinstance(data.get("device_auth_id"), str) or not isinstance(code, str) or not code:
        raise ValueError("Invalid device response")
    interval = min(max(int(data.get("interval") or 5), 5), 60)
    return {"device_auth_id": data["device_auth_id"], "user_code": code,
            "verification_uri": VERIFY, "expires_in": 900, "interval": interval}


async def _token(form: dict):
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(ISSUER + "/oauth/token", data={"client_id": CLIENT_ID, **form})
    result = response.json()
    if not isinstance(result, dict):
        raise ValueError("Invalid token response")
    if response.is_error:
        if result.get("error"):
            return result
        response.raise_for_status()
    if not isinstance(result.get("access_token"), str) or not result["access_token"]:
        raise ValueError("Missing access token")
    return result


async def poll(device: dict):
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(ISSUER + "/api/accounts/deviceauth/token", json={
            "device_auth_id": device["device_auth_id"], "user_code": device["user_code"],
        }, headers={"Content-Type": "application/json"})
    if response.status_code in (403, 404):
        return {"error": "authorization_pending"}
    if response.status_code in (401, 410):
        return {"error": "access_denied"}
    if response.is_error:
        return {"error": "authorization_pending"}
    data = response.json()
    code, verifier = data.get("authorization_code"), data.get("code_verifier")
    if not isinstance(code, str) or not isinstance(verifier, str) or not code or not verifier:
        return {"error": "authorization_pending"}
    return await _token({"grant_type": "authorization_code", "code": code,
                         "redirect_uri": ISSUER + "/deviceauth/callback", "code_verifier": verifier})


def credentials(tokens, previous=None):
    previous = previous or {}
    return {"codex_oauth": True, "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token") or previous.get("refresh_token"),
            "id_token": tokens.get("id_token") or previous.get("id_token", ""),
            "account_id": account_id(tokens.get("id_token") or "") or previous.get("account_id", ""),
            "client_id": previous.get("client_id") or CLIENT_ID,
            "expires_at": time.time() + max(1, int(tokens.get("expires_in", 3600)))}


def wire_key(data):
    return TOKEN_PREFIX + json.dumps({"access_token": data["access_token"], "account_id": data.get("account_id", "")})


def wire_credentials(key):
    raw = key.removeprefix(TOKEN_PREFIX)
    return json.loads(raw) if raw.startswith("{") else {"access_token": raw}


def read_credentials(secret):
    if not secret:
        return None
    try:
        plain = crypto.decrypt(secret)
    except ValueError:
        return None
    if not plain.startswith("{"):
        return None
    data = json.loads(plain)
    return data if isinstance(data, dict) and data.get("codex_oauth") is True else None


async def access_key(session, provider):
    data = read_credentials(provider.secret_ref)
    if not data:
        return None
    if provider.base_url != BASE_URL:
        raise ProviderError("Некорректный адрес подключённого аккаунта Codex")
    if data["expires_at"] <= time.time() + 60:
        locked = await session.scalar(select(Provider).where(Provider.id == provider.id)
                                      .with_for_update().execution_options(populate_existing=True))
        data = read_credentials(locked.secret_ref)
        if data["expires_at"] <= time.time() + 60:
            if not data.get("refresh_token"):
                raise ProviderError("Вход Codex истёк. Подключите аккаунт снова.")
            try:
                tokens = await _token({"grant_type": "refresh_token", "refresh_token": data["refresh_token"],
                                       "client_id": data.get("client_id", CLIENT_ID)})
                if tokens.get("error"):
                    raise ValueError("Refresh rejected")
                data = credentials(tokens, data)
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                raise ProviderError("Не удалось обновить вход Codex. Подключите аккаунт снова.") from None
            locked.secret_ref = crypto.encrypt(json.dumps(data))
            await session.commit()
    return wire_key(data)
