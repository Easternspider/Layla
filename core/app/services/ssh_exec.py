"""SSH-исполнитель attack box: подключение к серверу пользователя и запуск команд.

Это транспорт «последнего метра» для активных действий пентеста. Он НЕ решает,
что запускать, и не обходит проверки: команды приходят уже после гейтов
(scope/venue/egress) и HITL-подтверждения оператора — см. venue_executor.execute.
Сервер (host/port/user, ключ или пароль) добавляет и выбирает сам оператор для
своей авторизованной инфраструктуры.

Защита от MITM: ключ хоста закрепляется при первом успешном подключении (TOFU) и
проверяется при последующих. Смена ключа хоста → отказ (возможна подмена).
"""
from __future__ import annotations

import asyncio
import socket
from dataclasses import dataclass

import asyncssh

CONNECT_TIMEOUT = 15
COMMAND_TIMEOUT = 3600  # c: потолок на одну команду (долгие сканы/эксплойты); вывод буферизуется, не стримится
MAX_OUTPUT = 200_000  # байт вывода команды, дальше обрезается

# step id -> live SSH sessions. Stop closes them; a detached remote process may survive.
_live: dict[str, list] = {}
_stopped: set[str] = set()


class _Live:
    def __init__(self) -> None:
        self.conn = None
        self.stopped = False


def interrupt(step_ids) -> None:
    """Close SSH sessions for these command steps. Safe if none are running."""
    for key in step_ids:
        _stopped.add(key)
        for session in list(_live.get(key, ())):
            session.stopped = True
            if session.conn is not None:
                session.conn.close()


def _stopped_error() -> SSHError:
    return SSHError("Команда остановлена оператором. Если процесс был отвязан от SSH, он мог продолжиться на сервере.")


class SSHError(RuntimeError):
    """Не удалось подключиться или выполнить команду — текст для оператора."""


class HostKeyChanged(SSHError):
    """Ключ хоста не совпал с закреплённым — подключение отклонено (возможен MITM)."""


@dataclass
class SSHConfig:
    host: str
    port: int
    user: str
    auth: str            # "key" | "password"
    secret: str | None   # приватный ключ или пароль (расшифрованные)
    host_key: str | None  # закреплённый публичный ключ хоста (export_public_key) или None
    via: tuple[str, int] | None = None  # SOCKS5 (Tor или Proxy); None — прямое соединение


@dataclass
class SSHResult:
    exit_code: int | None
    output: str
    truncated: bool
    host_key: str        # актуальный публичный ключ хоста (для закрепления)


def _client_keys(cfg: SSHConfig) -> list:
    if cfg.auth != "key" or not cfg.secret:
        return []
    try:
        return [asyncssh.import_private_key(cfg.secret)]
    except (asyncssh.KeyImportError, ValueError) as exc:
        raise SSHError(f"Не удалось прочитать приватный ключ: {exc}") from exc


def _verify_host_key(cfg: SSHConfig, presented: asyncssh.SSHKey) -> None:
    """Сверить предъявленный ключ хоста с закреплённым (если он есть)."""
    if not cfg.host_key:
        return
    try:
        pinned = asyncssh.import_public_key(cfg.host_key)
    except (asyncssh.KeyImportError, ValueError) as exc:
        raise HostKeyChanged("Сохранённый ключ хоста повреждён. Проверьте сервер и добавьте его заново.") from exc
    if pinned.export_public_key() != presented.export_public_key():
        raise HostKeyChanged(
            "Ключ хоста изменился с прошлого подключения — соединение отклонено "
            "(возможна подмена сервера). Проверьте сервер и при необходимости "
            "удалите и добавьте его заново."
        )


class _PinnedClient(asyncssh.SSHClient):
    """Check the server during key exchange, before credentials are offered."""
    def __init__(self, cfg: SSHConfig) -> None:
        self.cfg = cfg
        self.error: HostKeyChanged | None = None

    def validate_host_public_key(self, host: str, addr: str, port: int, key) -> bool:
        try:
            _verify_host_key(self.cfg, key)
            return True
        except HostKeyChanged as exc:
            self.error = exc
            return False


def _socks5_socket(proxy_host: str, proxy_port: int, dest_host: str, dest_port: int) -> socket.socket:
    """Соединение до цели через SOCKS5 без аутентификации (Tor и обычный Proxy)."""
    sock = socket.create_connection((proxy_host, proxy_port), timeout=CONNECT_TIMEOUT)
    try:
        sock.settimeout(CONNECT_TIMEOUT)

        def recvn(n: int) -> bytes:
            buf = b""
            while len(buf) < n:
                chunk = sock.recv(n - len(buf))
                if not chunk:
                    raise OSError("SOCKS5 оборвал соединение")
                buf += chunk
            return buf

        sock.sendall(b"\x05\x01\x00")
        if recvn(2) != b"\x05\x00":
            raise OSError("SOCKS5 не принял подключение без пароля")
        host = dest_host.encode("idna")
        if not host or len(host) > 255:
            raise OSError("Имя хоста не помещается в SOCKS5")
        sock.sendall(b"\x05\x01\x00\x03" + bytes([len(host)]) + host + dest_port.to_bytes(2, "big"))
        head = recvn(4)
        if head[0] != 5 or head[1] != 0:
            raise OSError("SOCKS5 не смог подключиться к серверу")
        if head[3] == 1:
            recvn(6)
        elif head[3] == 4:
            recvn(18)
        elif head[3] == 3:
            recvn(recvn(1)[0] + 2)
        else:
            raise OSError("SOCKS5 вернул неизвестный адрес")
        sock.settimeout(None)
        return sock
    except Exception:
        sock.close()
        raise


async def _connect(cfg: SSHConfig):
    """Открыть соединение, не доверяя known_hosts ОС; проверку делаем сами (TOFU/pin)."""
    validator = _PinnedClient(cfg)
    sock = None
    try:
        if cfg.via:
            sock = await asyncio.to_thread(_socks5_socket, cfg.via[0], cfg.via[1], cfg.host, cfg.port)
        conn = await asyncio.wait_for(
            asyncssh.connect(
                cfg.host, port=cfg.port, username=cfg.user,
                client_keys=_client_keys(cfg),
                password=cfg.secret if cfg.auth == "password" else None,
                known_hosts=asyncssh.import_known_hosts(""),
                client_factory=lambda: validator,
                agent_path=None,           # не трогаем ssh-agent оператора
                config=None,               # игнорируем ~/.ssh/config
                sock=sock,
            ),
            timeout=CONNECT_TIMEOUT,
        )
    except asyncssh.HostKeyNotVerifiable as exc:
        raise validator.error or HostKeyChanged("Не удалось проверить ключ хоста") from exc
    except asyncssh.PermissionDenied as exc:
        raise SSHError("Отказано в доступе: проверьте пользователя, ключ или пароль") from exc
    except (TimeoutError, OSError, asyncssh.Error) as exc:
        where = f" через {cfg.via[0]}:{cfg.via[1]}" if cfg.via else ""
        raise SSHError(f"Не удалось подключиться к {cfg.host}:{cfg.port}{where}: {type(exc).__name__}") from exc
    presented = conn.get_server_host_key()
    try:
        _verify_host_key(cfg, presented)
    except HostKeyChanged:
        conn.close()
        await conn.wait_closed()
        raise
    return conn, presented.export_public_key().decode().strip()


async def probe(cfg: SSHConfig) -> SSHResult:
    """Проверить, что до сервера есть SSH-доступ (для кнопки «Проверить подключение»)."""
    conn, host_key = await _connect(cfg)
    try:
        result = await conn.run("echo layla-ok", timeout=CONNECT_TIMEOUT)
        out = (result.stdout or "").strip()
        return SSHResult(exit_code=result.exit_status, output=out, truncated=False, host_key=host_key)
    finally:
        conn.close()
        await conn.wait_closed()


async def run(cfg: SSHConfig, command: str, timeout: int = COMMAND_TIMEOUT, interrupt_key: str | None = None) -> SSHResult:
    """Выполнить команду на attack box и вернуть объединённый вывод (stdout+stderr)."""
    if interrupt_key and interrupt_key in _stopped:
        _stopped.discard(interrupt_key)
        raise _stopped_error()
    session = _Live()
    if interrupt_key:
        _live.setdefault(interrupt_key, []).append(session)
    conn = None
    try:
        if session.stopped:
            raise _stopped_error()
        conn, host_key = await _connect(cfg)
        session.conn = conn
        if session.stopped or (interrupt_key and interrupt_key in _stopped):
            raise _stopped_error()
        try:
            result = await conn.run(command, timeout=timeout, check=False)
        except asyncssh.TimeoutError as exc:
            # Отдаём частичный вывод, собранный до убийства по таймауту, чтобы долгая
            # экстракция не теряла весь прогресс (asyncssh.TimeoutError несёт stdout/stderr).
            out = str(getattr(exc, "stdout", "") or "")
            err = str(getattr(exc, "stderr", "") or "")
            partial = out if not err else (f"{out}\n{err}" if out else err)
            tail = partial[-8000:]
            suffix = f" Частичный вывод до остановки:\n{tail}" if tail.strip() else " Частичного вывода не получено."
            raise SSHError(f"Команда не завершилась за {timeout} c.{suffix}") from exc
        except (asyncssh.Error, OSError) as exc:
            if session.stopped or (interrupt_key and interrupt_key in _stopped):
                raise _stopped_error() from exc
            raise
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        combined = stdout if not stderr else f"{stdout}\n{stderr}" if stdout else stderr
        truncated = len(combined) > MAX_OUTPUT
        return SSHResult(
            exit_code=result.exit_status,
            output=combined[:MAX_OUTPUT],
            truncated=truncated,
            host_key=host_key,
        )
    finally:
        if interrupt_key:
            sessions = _live.get(interrupt_key, [])
            if session in sessions:
                sessions.remove(session)
            if not sessions:
                _live.pop(interrupt_key, None)
            _stopped.discard(interrupt_key)
        if conn is not None:
            conn.close()
            await conn.wait_closed()
