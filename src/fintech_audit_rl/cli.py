"""Development entry point; no audit environment is implemented yet."""

import argparse
import subprocess
import sys
from pathlib import Path

from fintech_audit_rl import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GENESIS FinTech development tools")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify", help="Check the development foundation only")
    verify.add_argument("--full", action="store_true", help="Require full hackathon verification")
    args = parser.parse_args(argv)
    if args.full:
        print("Full verification is unavailable: blocks B00–B09 are not complete.", flush=True)
        return 2
    root = Path(__file__).resolve().parents[2]
    if not (root / "pyproject.toml").is_file() or not (root / "tests").is_dir():
        print("Run verify from an editable development installation with tests present.")
        return 2
    print("Scope: development foundation only. Audit correctness is NOT verified.", flush=True)
    checks = [
        [sys.executable, "scripts/sync_plan.py", "--check"],
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        [sys.executable, "-m", "pytest"],
    ]
    for command in checks:
        result = subprocess.run(command, cwd=root, check=False)
        if result.returncode:
            return result.returncode
    print("Foundation checks passed; full hackathon acceptance remains pending.", flush=True)
    return 0
