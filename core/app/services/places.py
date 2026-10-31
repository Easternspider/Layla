"""Private directories: one tree per chat and one tree per engagement.

Other sections do not read these paths. An old layout is used only when it
already exists and the new directory does not, so a running server keeps its files.
"""
from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.config import get_settings


def _hex(value: str) -> str:
    return UUID(str(value)).hex


def projects_root(base: str | None = None) -> Path:
    return Path(base or get_settings().projects_dir).resolve()


def chat_dir(owner_id: str, domain: str, chat_id: str, base: str | None = None) -> Path:
    name = "agent" if domain == "crew" else domain
    return projects_root(base) / "domains" / name / _hex(owner_id) / _hex(chat_id)


def engagement_home(owner_id: str, engagement_id: str, base: str | None = None) -> Path:
    return projects_root(base) / "engagements" / _hex(owner_id) / _hex(engagement_id)


def prefer(new: Path, old: Path) -> Path:
    if old.exists() and not new.exists():
        return old
    return new
