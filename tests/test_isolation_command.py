from fintech_audit_rl.runner.isolation import isolated_worker_command


def test_isolated_worker_has_no_host_mount_or_network():
    command = isolated_worker_command("reconciliation", 3)
    assert "--network" in command
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command
    assert "--cap-drop" in command
    assert "--user" in command
    assert not any(item in command for item in ("-v", "--volume", "--mount"))
