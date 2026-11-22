"""CI-only regression for expanded scenarios through the isolated worker."""

import json

from fintech_audit_rl.runner.supervisor import run_first_episode

CASES = (
    ("duplicate", {}, 1),
    (
        "foreign-interaction",
        {
            "duplicate": False,
            "fx_case": True,
            "fx_error": True,
            "allocation_actual_minor": 6000,
        },
        2,
    ),
    ("clean-distractors", {"duplicate": False, "distractors": True}, 0),
    ("scaled-duplicate", {"duplicate": True, "scale_pairs": 34}, 1),
)


def main() -> int:
    reports = []
    for offset, (name, options, expected_tp) in enumerate(CASES):
        result = run_first_episode(301 + offset, isolated=True, **options)
        metrics = result.score.metrics
        if (
            result.worker_exit_code != 0
            or result.truncated
            or metrics is None
            or metrics.tp != expected_tp
            or metrics.fp
            or metrics.fn
            or metrics.f1 != 1
        ):
            raise RuntimeError(f"isolated scenario failed: {name}")
        reports.append({"name": name, "steps": result.steps, "f1": str(metrics.f1)})
    print(json.dumps(reports, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
