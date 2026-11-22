"""Comparable execution envelope for the four required adapters."""

import json
import time
import tracemalloc
from dataclasses import asdict, dataclass, field
from pathlib import Path

from fintech_audit_rl.benchmark.suites import EpisodeConfig, build_episode
from fintech_audit_rl.evaluation.oracle import oracle_submit
from fintech_audit_rl.evaluation.service import Evaluator
from fintech_audit_rl.runner.supervisor import run_first_episode
from fintech_audit_rl.storage.public_store import PublicStore

ADAPTERS = ("reconciliation", "flag_all", "random_explorer", "oracle")


@dataclass(frozen=True)
class AdapterResult:
    adapter: str
    privileged: bool
    config_name: str
    split: str
    episode_id: str
    expected_issues: int
    tp: int
    fp: int
    fn: int
    precision: str
    recall: str
    f1: str
    reward: str
    steps: int
    worker_exit_code: int | None
    truncated: bool
    elapsed_seconds: float = field(compare=False)
    peak_traced_bytes: int = field(compare=False)


def run_adapter(
    config: EpisodeConfig,
    adapter: str,
    policy_seed: int = 0,
    trajectory_output: list[dict] | None = None,
) -> AdapterResult:
    if adapter not in ADAPTERS:
        raise ValueError("unknown adapter")
    tracemalloc.start()
    started = time.perf_counter()
    try:
        bundle = build_episode(config)
        expected = len(bundle.private.truth)
        if adapter == "oracle":
            store = PublicStore(bundle.public)
            evaluator = Evaluator(
                bundle.public.manifest.episode_id, tuple(bundle.private.truth), store.public_ids
            )
            submission = oracle_submit(bundle.public.manifest, bundle.private.truth).model_dump(
                mode="json"
            )
            score = evaluator.score(submission, 0)
            steps = 1
            exit_code = None
            truncated = False
        else:
            run = run_first_episode(
                config.seed,
                duplicate=config.duplicate,
                policy=adapter,
                transform=config.transform,
                policy_seed=policy_seed,
                allocation_actual_minor=config.allocation_actual_minor,
                fx_case=config.fx_case,
                fx_error=config.fx_error,
                period_error=config.period_error,
                distractors=config.distractors,
                scale_pairs=config.scale_pairs,
                timezone=config.timezone,
            )
            if run.score.metrics is None:
                raise RuntimeError("adapter returned structurally invalid submission")
            if run.trajectory[-1]["episode_id"] != bundle.public.manifest.episode_id:
                raise RuntimeError("adapter ran a different episode")
            if trajectory_output is not None:
                trajectory_output.extend(run.trajectory)
            score = run.score
            steps = run.steps
            exit_code = run.worker_exit_code
            truncated = run.truncated
    finally:
        elapsed = time.perf_counter() - started
        _, peak_traced = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    metrics = score.metrics
    assert metrics is not None
    return AdapterResult(
        adapter=adapter,
        privileged=adapter == "oracle",
        config_name=config.name,
        split=config.split,
        episode_id=bundle.public.manifest.episode_id,
        expected_issues=expected,
        tp=metrics.tp,
        fp=metrics.fp,
        fn=metrics.fn,
        precision=str(metrics.precision),
        recall=str(metrics.recall),
        f1=str(metrics.f1),
        reward=str(score.reward),
        steps=steps,
        worker_exit_code=exit_code,
        truncated=truncated,
        elapsed_seconds=elapsed,
        peak_traced_bytes=peak_traced,
    )


def run_benchmark(
    configs: tuple[EpisodeConfig, ...], trajectory_output: list[dict] | None = None
) -> tuple[AdapterResult, ...]:
    return tuple(
        run_adapter(
            config,
            adapter,
            policy_seed=7000 + index,
            trajectory_output=trajectory_output if adapter == "reconciliation" else None,
        )
        for index, config in enumerate(configs)
        for adapter in ADAPTERS
    )


def write_results(results: tuple[AdapterResult, ...], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([asdict(result) for result in results], indent=2, sort_keys=True) + "\n",
        "utf-8",
    )
