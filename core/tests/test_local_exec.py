"""Эта машина: direct идёт напрямую, Tor и прокси только через proxychains."""
import os
import stat

import pytest

from app.services import local_exec


def test_missing_proxy_endpoint_is_not_treated_as_direct():
    with pytest.raises(local_exec.LocalExecError, match="Прямой выход"):
        local_exec.socks(None)


def test_child_env_drops_layla_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("LAYLA_SECRET_KEY", "secret")
    monkeypatch.setenv("DATABASE_URL", "postgres://layla")
    env = local_exec.child_env(tmp_path, "tor", 9050)
    assert "LAYLA_SECRET_KEY" not in env and "DATABASE_URL" not in env
    assert env["ALL_PROXY"] == "socks5h://tor:9050"
    assert env["HOME"] == str(tmp_path)
    assert os.environ["LAYLA_SECRET_KEY"] == "secret"
    direct = local_exec.child_env(tmp_path)
    assert "ALL_PROXY" not in direct and "HTTP_PROXY" not in direct


def test_proxychains_config_is_strict(tmp_path):
    path = tmp_path / "pc.conf"
    local_exec.write_config(path, "tor", 9050)
    text = path.read_text()
    assert "strict_chain" in text and "proxy_dns" in text
    assert "socks5 tor 9050" in text
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_bad_proxy_host_is_rejected():
    with pytest.raises(local_exec.LocalExecError):
        local_exec.socks(("bad host", 9050))
    with pytest.raises(local_exec.LocalExecError):
        local_exec.socks(("tor", 0))


@pytest.mark.asyncio
async def test_direct_command_runs_without_proxychains(tmp_path, monkeypatch):
    def missing(name):
        raise AssertionError(name)
    monkeypatch.setattr(local_exec.shutil, "which", missing)
    text = await local_exec.run("printf direct-ok", tmp_path, None)
    assert "direct-ok" in text


@pytest.mark.asyncio
async def test_proxy_route_still_refuses_without_wrapper(tmp_path, monkeypatch):
    monkeypatch.setattr(local_exec.shutil, "which", lambda name: None)
    with pytest.raises(local_exec.LocalExecError, match="proxychains4"):
        await local_exec.run("printf no", tmp_path, ("tor", 9050))
