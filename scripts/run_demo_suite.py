"""Run the fixed short demonstration requested by the submission plan."""

from __future__ import annotations

import json

from fintech_audit_rl.runner.supervisor import run_first_episode


def _case(name: str, seed: int, **options: object) -> dict[str, object]:
    result = run_first_episode(seed, **options)
    metrics = result.score.metrics
    if result.worker_exit_code != 0 or metrics is None:
        raise RuntimeError(f"demo case failed: {name}")
    return {
        "name": name,
        "steps": result.steps,
        "precision": str(metrics.precision),
        "recall": str(metrics.recall),
        "f1": str(metrics.f1),
        "reward": str(result.score.reward),
    }


def main() -> int:
    cases = [
        _case("clean", 901, duplicate=False),
        _case("duplicate", 902),
        _case("false_flag_all_on_clean", 903, duplicate=False, policy="flag_all"),
        _case(
            "allocation_fx_interaction",
            904,
            duplicate=False,
            fx_case=True,
            fx_error=True,
            allocation_actual_minor=6000,
        ),
    ]
    first = _case("repeatability_a", 905)
    second = _case("repeatability_b", 905)
    if {key: value for key, value in first.items() if key != "name"} != {
        key: value for key, value in second.items() if key != "name"
    }:
        raise RuntimeError("repeatability check failed")
    cases.extend((first, second))
    print(json.dumps(cases, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
