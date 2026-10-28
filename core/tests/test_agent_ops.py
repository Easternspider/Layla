"""Operator tools stay on the account's own servers and reject shell in package names."""
import pytest

from app.models.enums import Domain
from app.services import agent_ops


def test_agent_is_a_domain_and_lists_server_tools():
    assert Domain.agent.value == "agent"
    assert {"list_servers", "server_command", "server_status", "server_install", "server_read",
            "lookup_cve", "search_cves", "create_inbox", "read_inbox", "tool_catalog"} <= set(agent_ops.SCHEMAS)
    assert "map_surface" not in agent_ops.SCHEMAS


def test_install_and_read_do_not_accept_shell():
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
