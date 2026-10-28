"""Operator tools stay on the account's own servers and reject shell in package names."""
import pytest

from app.models.enums import Domain
from app.services import agent_ops


def test_agent_is_a_domain_and_lists_server_tools():
    assert Domain.agent.value == "agent"
    assert {"list_servers", "server_command", "server_status", "server_install", "server_read",
            "lookup_cve", "search_cves", "create_inbox", "read_inbox", "tool_catalog"} <= set(agent_ops.SCHEMAS)
    assert "map_surface" not in agent_ops.SCHEMAS
    assert "web_search" in agent_ops.NOTE and "не бери из памяти" in agent_ops.NOTE


def test_a_task_can_be_limited_to_chosen_servers():
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
