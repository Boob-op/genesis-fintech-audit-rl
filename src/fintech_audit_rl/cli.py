"""Development entry point; no audit environment is implemented yet."""

import argparse
import json
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
    demo = commands.add_parser("demo", help="Run the first KZT scenario in developer mode")
    demo.add_argument("--seed", type=int, default=101)
    demo.add_argument("--output", type=Path, default=Path("runs/demo/trajectories.jsonl"))
    demo.add_argument("--clean", action="store_true")
    demo.add_argument("--closed", action="store_true")
    demo.add_argument("--policy", choices=["reconciliation", "flag_all"], default="reconciliation")
    args = parser.parse_args(argv)
    if args.command == "demo":
        from fintech_audit_rl.reporting.trajectory import write_trajectory
        from fintech_audit_rl.runner.supervisor import run_first_episode

        result = run_first_episode(
            args.seed, duplicate=not args.clean, closed=args.closed, policy=args.policy
        )
        write_trajectory(args.output, result.trajectory)
        print(
            json.dumps(
                {
                    "mode": "developer_subprocess_not_os_isolated",
                    "steps": result.steps,
                    "f1": str(result.score.metrics.f1) if result.score.metrics else None,
                    "scored_reward": str(result.score.reward),
                    "worker_exit_code": result.worker_exit_code,
                    "trajectory": str(args.output),
                },
                ensure_ascii=False,
            )
        )
        return 0 if result.worker_exit_code == 0 else 1
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
