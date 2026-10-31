"""Команды пентеста на этой машине.

Direct запускает команду как есть, без прокси. Tor и Proxy идут через
proxychains4 (strict_chain, DNS тоже через SOCKS). Если обёртки или маршрута
нет, такая команда не стартует и на direct не откатывается.
Секреты процесса Лейлы в окружение команды не попадают.
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import signal
import uuid
from pathlib import Path

from app.services.ssh_exec import COMMAND_TIMEOUT, MAX_OUTPUT

_HOST = re.compile(r"[A-Za-z0-9._-]{1,253}")
_live: dict[str, asyncio.subprocess.Process] = {}
_stopped: set[str] = set()


class LocalExecError(RuntimeError):
    """Команда на этой машине не выполнена."""


def available() -> bool:
    return shutil.which("proxychains4") is not None


def interrupt(step_ids) -> None:
    for key in step_ids:
        _stopped.add(key)
        proc = _live.get(key)
        if proc is not None and proc.returncode is None:
            _kill(proc)


def socks(via: tuple[str, int] | None) -> tuple[str, int]:
    if not via:
        raise LocalExecError("Прямой выход запрещён: нужен Tor или прокси")
    host, port = via
    if not isinstance(port, int) or not 1 <= port <= 65535 or not _HOST.fullmatch(host or ""):
        raise LocalExecError("Некорректный адрес Tor или прокси")
    return host, port


def child_env(work: Path, host: str | None = None, port: int | None = None,
              user: str | None = None, password: str | None = None) -> dict[str, str]:
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": str(work),
        "LANG": "C.UTF-8",
        "TMPDIR": str(work),
        "GIT_TERMINAL_PROMPT": "0",
    }
    if host is None:
        return env
    auth = f"{user}:{password}@" if user and password else ""
    proxy = f"socks5h://{auth}{host}:{port}"
    env.update({
        "ALL_PROXY": proxy,
        "all_proxy": proxy,
        "HTTP_PROXY": proxy,
        "HTTPS_PROXY": proxy,
        "http_proxy": proxy,
        "https_proxy": proxy,
        "NO_PROXY": "",
        "no_proxy": "",
    })
    return env


def write_config(path: Path, host: str, port: int, user: str | None = None, password: str | None = None) -> None:
    login = f" {user} {password}" if user and password else ""
    path.write_text(
        "strict_chain\n"
        "proxy_dns\n"
        "remote_dns_subnet 224\n"
        "tcp_read_time_out 600000\n"
        "tcp_connect_time_out 60000\n"
        "[ProxyList]\n"
        f"socks5 {host} {port}{login}\n",
        encoding="utf-8",
    )
    path.chmod(0o600)


def make_runner(work: Path, interrupt_key: str | None, via: tuple[str, int] | None,
                auth: tuple[str, str] | None = None):
    async def runner(command: str) -> str:
        return await run(command, work, via, interrupt_key=interrupt_key, auth=auth)

    return runner


async def run(command: str, work: Path, via: tuple[str, int] | None, *,
              interrupt_key: str | None = None, timeout: int = COMMAND_TIMEOUT,
              auth: tuple[str, str] | None = None) -> str:
    argv = ["bash", "-lc", command]
    env = child_env(work)
    config = None
    if via is not None:
        host, port = socks(via)
        binary = shutil.which("proxychains4")
        if not binary:
            raise LocalExecError("proxychains4 не установлен — команда не запущена, прямой выход запрещён")
        user, password = auth if auth else (None, None)
        config = work / f".proxychains-{uuid.uuid4().hex}.conf"
        argv = [binary, "-q", "-f", str(config), *argv]
        env = child_env(work, host, port, user, password)
    if interrupt_key and interrupt_key in _stopped:
        _stopped.discard(interrupt_key)
        raise LocalExecError("Команда остановлена оператором")
    work.mkdir(parents=True, exist_ok=True, mode=0o700)
    proc = None
    try:
        if config is not None:
            write_config(config, host, port, user, password)
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(work),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        if interrupt_key:
            _live[interrupt_key] = proc
        if interrupt_key and interrupt_key in _stopped:
            _kill(proc)
            raise LocalExecError("Команда остановлена оператором")
        try:
            raw, _ = await asyncio.wait_for(proc.communicate(), timeout)
        except TimeoutError as exc:
            _kill(proc)
            await proc.wait()
            raise LocalExecError(f"Команда не завершилась за {timeout} c.") from exc
        if interrupt_key and interrupt_key in _stopped:
            raise LocalExecError("Команда остановлена оператором")
        text = (raw or b"").decode("utf-8", errors="replace")
        truncated = len(text) > MAX_OUTPUT
        text = text[:MAX_OUTPUT]
        if proc.returncode not in (0, None):
            detail = text[:1500] if text.strip() else "stdout и stderr пусты"
            raise LocalExecError(f"Команда завершилась с кодом {proc.returncode}: {detail}")
        if not text.strip():
            text = ("[Команда завершилась успешно, но ничего не вывела. "
                    "Если ожидался результат — прочитай файл отдельной командой.]")
        elif truncated:
            text += "\n[…вывод обрезан на пределе.]"
        return text
    finally:
        if proc is not None and interrupt_key:
            _live.pop(interrupt_key, None)
            _stopped.discard(interrupt_key)
        if config is not None:
            config.unlink(missing_ok=True)


def _kill(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        proc.kill()
