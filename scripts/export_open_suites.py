"""Export the reproducible open train and dev episode suites."""

import argparse
from pathlib import Path

from fintech_audit_rl.benchmark.suites import DEV, TRAIN, export_suite


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("episodes"))
    args = parser.parse_args()
    index = export_suite((*TRAIN, *DEV), args.output)
    print(f"Exported {len(index)} open episodes to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
