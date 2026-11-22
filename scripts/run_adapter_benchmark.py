"""Run all four adapters against the same open train/dev episodes."""

import argparse
from pathlib import Path

from fintech_audit_rl.benchmark.runner import run_benchmark, write_results
from fintech_audit_rl.benchmark.suites import DEV, TRAIN
from fintech_audit_rl.reporting.summary import write_failure_analysis, write_summary
from fintech_audit_rl.reporting.trajectory import write_trajectory


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("reports/adapter_runs.json"))
    parser.add_argument("--trajectories", type=Path, default=Path("reports/trajectories.jsonl"))
    parser.add_argument("--summary", type=Path, default=Path("reports/benchmark_summary.json"))
    parser.add_argument("--failures", type=Path, default=Path("reports/failure_analysis.md"))
    args = parser.parse_args()
    trajectories = []
    results = run_benchmark((*TRAIN, *DEV), trajectories)
    write_results(results, args.output)
    write_trajectory(args.trajectories, trajectories)
    write_summary(results, args.summary)
    write_failure_analysis(results, args.failures)
    print(f"Wrote {len(results)} adapter runs to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
