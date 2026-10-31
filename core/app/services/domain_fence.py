"""Pentest engagement targets stay in the pentest section.

Other chats may search the public web, but they must not open, look up or
scan a host that belongs to one of the operator's engagements.
"""
from __future__ import annotations

import re
from contextvars import ContextVar

from sqlalchemy import select

from app.models.pentest import Engagement, Scope
from app.services import scope

REFUSAL = (
    "Это адрес из раздела Пентест. Откройте Пентест и работайте в engagement: "
    "в остальных разделах этот адрес не открывается, не ищется и не сканируется."
)

_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_HOST = re.compile(
    r"(?<![\w@])(?:(?:\d{1,3}\.){3}\d{1,3}|[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+)(?![\w-])",
    re.IGNORECASE,
)
_bound: ContextVar[tuple | None] = ContextVar("layla_domain_fence", default=None)


def bind(maker, owner_id: str):
    return _bound.set((maker, owner_id))


def reset(token) -> None:
    _bound.reset(token)


def hosts_of(*blobs: str) -> set[str]:
    found: set[str] = set()
    for blob in blobs:
        text = blob or ""
        for url in _URL.findall(text):
            host = scope.extract_host(url.rstrip(").,;"))
            if host:
                found.add(host)
        for match in _HOST.findall(text):
            host = scope.extract_host(match)
            if host:
                found.add(host)
    return found


async def refusal(*blobs: str, maker=None, owner_id: str | None = None) -> str | None:
    """Russian refusal when any blob names an engagement target, else None."""
    if maker is None or not owner_id:
        state = _bound.get()
        if not state:
            return None
        maker, owner_id = state
    hosts = hosts_of(*blobs)
    if not hosts:
        return None
    async with maker() as session:
        rows = (await session.execute(
            select(Engagement.target, Scope.allow)
            .outerjoin(Scope, Scope.engagement_id == Engagement.id)
            .where(Engagement.owner_id == owner_id)
        )).all()
    rules: list[str] = []
    for target, allow in rows:
        if target:
            rules.append(str(target))
        rules.extend(str(item) for item in (allow or []) if item)
    if not rules:
        return None
    for host in hosts:
        for rule in rules:
            if scope.check_target(host, [rule], []).allowed:
                return REFUSAL
    return None
