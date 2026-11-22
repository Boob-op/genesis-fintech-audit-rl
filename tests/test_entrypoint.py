"""Verify the final repository entry point."""

import subprocess
import sys


def test_submission_manifest_is_complete() -> None:
    from scripts.check_submission import validate

    result = validate()
    assert result["episodes"] == 20
    assert result["runs"] == 80
    assert result["trajectory_steps"] == 114
    assert result["bytes"] < 1_000_000_000


def test_full_verification_command_is_wired(monkeypatch) -> None:
    from fintech_audit_rl import cli

    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    assert cli.main(["verify", "--full"]) == 0
    assert [sys.executable, "scripts/check_submission.py"] in commands


def test_full_verification_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_submission.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert '"episodes": 20' in result.stdout
