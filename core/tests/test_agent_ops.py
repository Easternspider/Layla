"""Operator tools stay on the account's own servers and reject shell in package names."""
import pytest

from app.models.enums import Domain
from app.services import agent_ops


def test_agent_is_a_domain_and_lists_server_tools():
    assert Domain.agent.value == "agent"
    assert {"list_servers", "server_command", "server_status", "server_install", "server_read",
            "host_command", "host_read",
            "lookup_cve", "search_cves", "create_inbox", "read_inbox", "tool_catalog"} <= set(agent_ops.SCHEMAS)
    assert "map_surface" not in agent_ops.SCHEMAS
    assert "web_search" in agent_ops.NOTE and "не бери из памяти" in agent_ops.NOTE
    assert "host_command" in agent_ops.NOTE and "песочниц" in agent_ops.NOTE
    assert "квот" in agent_ops.NOTE and "5–15" not in agent_ops.NOTE


def test_server_command_waits_long_enough_for_certbot():
    args = agent_ops.ServerCommand.model_validate({"server_id": "s", "command": "certbot renew --dry-run"})
    assert args.timeout == 600
    slow = agent_ops.ServerCommand.model_validate({"server_id": "s", "command": "certbot renew --dry-run", "timeout": 1800})
    assert slow.timeout == 1800
    with pytest.raises(ValueError):
        agent_ops.ServerCommand.model_validate({"server_id": "s", "command": "true", "timeout": 5})
    limited = agent_ops.Ops(None, "owner", ["alpha", "", "beta"])
    assert limited.allows("alpha") and limited.allows("beta")
    assert not limited.allows("gamma")
    assert "строго" in limited.scope_note()
    assert agent_ops.Ops(None, "owner", []).allows("gamma")
    assert agent_ops.Ops(None, "owner", None).scope_note() == ""
    command = agent_ops.install_command(["nginx", "curl"])
    assert "nginx" in command and "curl" in command
    with pytest.raises(ValueError):
        agent_ops.install_command(["nginx;id"])
    with pytest.raises(ValueError):
        agent_ops.guard_command("rm -rf /")
    read = agent_ops.read_command("/etc/hostname")
    assert "/etc/hostname" in read
    with pytest.raises(ValueError):
        agent_ops.read_command("/tmp/../etc/shadow")


@pytest.mark.asyncio
async def test_host_shell_is_only_for_a_machine_without_ssh():
    bound = agent_ops.Ops(None, "owner", ["alpha"])
    refused = await bound.execute("host_command", {"command": "echo hi"})
    assert "SSH" in refused["error"]
    from app.services import local_exec
    result = await local_exec.host_shell("echo layla-host")
    assert result["exit_code"] == 0 and "layla-host" in result["output"] and result["host"] == "this-machine"
