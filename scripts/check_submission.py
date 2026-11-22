"""Validate the checked-in submission artifact set without network access."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "README.md",
    "SUBMISSION.md",
    "LICENSE",
    "DESIGN.md",
    "Dockerfile",
    "pyproject.toml",
    "uv.lock",
    "docs/error_spec.json",
    "episodes/index.json",
    "reports/adapter_runs.json",
    "reports/benchmark_summary.json",
    "reports/failure_analysis.md",
    "reports/trajectories.jsonl",
)
MAX_SOLUTION_BYTES = 1_000_000_000


def checked_in_size() -> int:
    excluded = {
        ".git",
        ".venv",
        ".tools",
        ".uv-cache",
        ".pytest_cache",
        ".ruff_cache",
        "runs",
        "tmp",
    }
    return sum(
        path.stat().st_size
        for path in ROOT.rglob("*")
        if path.is_file() and not any(part in excluded for part in path.relative_to(ROOT).parts)
    )


def validate() -> dict[str, int]:
    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        raise RuntimeError(f"missing submission files: {', '.join(missing)}")

    index = json.loads((ROOT / "episodes/index.json").read_text(encoding="utf-8"))
    runs = json.loads((ROOT / "reports/adapter_runs.json").read_text(encoding="utf-8"))
    trajectory_lines = [
        line
        for line in (ROOT / "reports/trajectories.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    trajectories = len(trajectory_lines)
    size = checked_in_size()
    if len(index) != 20 or len(runs) != 80 or trajectories != 114:
        raise RuntimeError(
            "submission counts must be 20 episodes, 80 runs and 114 trajectory steps"
        )
    episode_ids = [entry["episode_id"] for entry in index]
    if (
        len(set(episode_ids)) != 20
        or sorted(entry["split"] for entry in index) != ["dev"] * 10 + ["train"] * 10
    ):
        raise RuntimeError("submission must contain ten distinct train and dev episodes")
    required_episode_files = (
        "public/manifest.json",
        "public/ledger.csv",
        "public/invoices.jsonl",
        "public/payments.jsonl",
        "public/fx.csv",
        "public/policy.json",
        "private/truth.json",
        "private/provenance.json",
        "private/generation.json",
    )
    for entry in index:
        episode_dir = ROOT / "episodes" / entry["split"] / entry["episode_id"]
        if any(not (episode_dir / name).is_file() for name in required_episode_files):
            raise RuntimeError(f"incomplete episode: {entry['episode_id']}")
    expected_pairs = {
        (episode_id, adapter)
        for episode_id in episode_ids
        for adapter in ("reconciliation", "flag_all", "random_explorer", "oracle")
    }
    actual_pairs = [(run["episode_id"], run["adapter"]) for run in runs]
    if len(set(actual_pairs)) != len(actual_pairs) or set(actual_pairs) != expected_pairs:
        raise RuntimeError("adapter runs do not cover every episode exactly once")
    for line in trajectory_lines:
        json.loads(line)
    if size > MAX_SOLUTION_BYTES:
        raise RuntimeError(f"solution size {size} exceeds {MAX_SOLUTION_BYTES} bytes")
    return {
        "episodes": len(index),
        "runs": len(runs),
        "trajectory_steps": trajectories,
        "bytes": size,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), sort_keys=True))
