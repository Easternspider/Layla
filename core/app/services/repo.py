"""Импорт git-репозиториев (спец. §5.7).

Клонирование выполняется на сервере оператора. Только публичный https,
без логина в URL, без локальных и служебных адресов. Процесс git не
наследует секреты Layla, хуки и protocol.file отключены.
"""
from __future__ import annotations

import asyncio
import ipaddress
import re
from pathlib import Path
from urllib.parse import urlparse

from app.services import gitops, web_research

_NAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def validate_repo_url(url: str) -> str:
    """Проверить URL репозитория; вернуть его или бросить ValueError."""
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Репозиторий доступен только по https без логина и пароля")
    host = parsed.hostname.rstrip(".").lower()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if host == "localhost" or host.endswith(".local") or host.endswith(".internal"):
            raise ValueError("Локальные адреса репозитория недоступны")
    else:
        if not address.is_global or address.is_multicast:
            raise ValueError("Локальные и служебные адреса недоступны")
    return url


def safe_dir_name(url: str) -> str:
    """Извлечь безопасное имя каталога из URL репозитория."""
    tail = urlparse(url).path.rstrip("/").split("/")[-1] or "repo"
    tail = tail[:-4] if tail.endswith(".git") else tail
    name = _NAME_RE.sub("-", tail).strip("-.")
    return name or "repo"


async def clone(url: str, dest: str | Path, *, timeout: float = 300.0) -> None:
    """Поверхностно клонировать репозиторий в dest. Бросает RuntimeError при ошибке."""
    url = validate_repo_url(url)
    host = urlparse(url).hostname or ""
    try:
        await web_research.public_addresses(host)
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "clone", "--depth", "1", url, str(dest),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=gitops._env(),
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "git не установлен на сервере — импорт из репозитория недоступен"
        ) from exc
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        proc.kill()
        raise RuntimeError("Таймаут клонирования репозитория") from exc
    if proc.returncode != 0:
        raise RuntimeError(f"git clone завершился с ошибкой: {stderr.decode(errors='replace')[:500]}")