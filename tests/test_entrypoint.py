"""Ensure the bootstrap cannot claim full audit acceptance."""

import subprocess
import sys


def test_full_verification_is_not_claimed() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "fintech_audit_rl", "verify", "--full"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "not complete" in result.stdout
