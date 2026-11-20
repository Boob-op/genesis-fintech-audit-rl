"""Run all four adapters against the same open train/dev episodes."""

import argparse
from pathlib import Path

from fintech_audit_rl.benchmark.runner import run_benchmark, write_results
from fintech_audit_rl.benchmark.suites import DEV, TRAIN


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("reports/adapter_runs.json"))
    args = parser.parse_args()
    results = run_benchmark((*TRAIN, *DEV))
    write_results(results, args.output)
    print(f"Wrote {len(results)} adapter runs to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
