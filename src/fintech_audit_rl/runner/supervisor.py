"""Trusted first-scenario supervisor; developer subprocess is not OS isolation."""

import json
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass

from fintech_audit_rl.benchmark.suites import EpisodeConfig, build_episode
from fintech_audit_rl.env.core import AuditEnv
from fintech_audit_rl.evaluation.service import Evaluator, Score
from fintech_audit_rl.runner.isolation import isolated_worker_command
from fintech_audit_rl.storage.public_store import PublicStore


@dataclass(frozen=True)
class RunResult:
    score: Score
    steps: int
    trajectory: tuple[dict, ...]
    worker_exit_code: int
    truncated: bool = False


def _readline_until(process: subprocess.Popen, deadline: float) -> str:
    result: queue.Queue[str] = queue.Queue(maxsize=1)
    thread = threading.Thread(target=lambda: result.put(process.stdout.readline()), daemon=True)
    thread.start()
    try:
        return result.get(timeout=max(0, deadline - time.monotonic()))
    except queue.Empty as error:
        raise TimeoutError("worker deadline reached") from error


def run_first_episode(
    seed: int,
    duplicate: bool = True,
    closed: bool = False,
    policy: str = "reconciliation",
    transform: str = "none",
    timeout_seconds: float = 60.0,
    policy_seed: int = 0,
    isolated: bool = False,
    allocation_actual_minor: int | None = None,
    fx_case: bool = False,
    fx_error: bool = False,
    period_error: bool = False,
    distractors: bool = False,
    scale_pairs: int | None = None,
) -> RunResult:
    if policy not in {"reconciliation", "flag_all", "random_explorer"}:
        raise ValueError("unknown policy")
    if type(policy_seed) is not int:
        raise ValueError("policy seed must be integer")
    if not 0 <= timeout_seconds <= 60:
        raise ValueError("timeout outside developer contract")
    deadline = time.monotonic() + timeout_seconds
    bundle = build_episode(
        EpisodeConfig(
            name="runtime",
            split="runtime",
            seed=seed,
            duplicate=duplicate,
            allocation_actual_minor=allocation_actual_minor,
            fx_case=fx_case,
            fx_error=fx_error,
            period_error=period_error,
            distractors=distractors,
            scale_pairs=scale_pairs,
            transform=transform,
        )
    )
    public = bundle.public
    issues = tuple(bundle.private.truth)
    store = PublicStore(public)
    evaluator = Evaluator(public.manifest.episode_id, issues, store.public_ids)
    env = AuditEnv(store, evaluator.score, evaluator.empty_score, closed=closed)
    initial, info = env.reset()
    trajectory = []
    command = (
        isolated_worker_command(policy, policy_seed)
        if isolated
        else [sys.executable, "-m", "fintech_audit_rl.runner.worker", policy, str(policy_seed)]
    )
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert process.stdin is not None and process.stdout is not None
    process.stdin.write(json.dumps({"observation": initial, "info": info}) + "\n")
    process.stdin.flush()
    final_score = None
    timed_out = False
    try:
        while True:
            line = _readline_until(process, deadline)
            if time.monotonic() >= deadline:
                raise TimeoutError("worker deadline reached")
            if not line:
                break
            message = json.loads(line)
            if set(message) != {"action"}:
                raise ValueError("invalid worker protocol message")
            action = message["action"]
            observation, visible_reward, terminated, truncated, info = env.step(action)
            trajectory.append(
                {
                    "episode_id": public.manifest.episode_id,
                    "step": len(trajectory) + 1,
                    "action": action,
                    "observation": observation,
                    "reward": float(visible_reward),
                    "terminated": terminated,
                    "truncated": truncated,
                }
            )
            process.stdin.write(
                json.dumps(
                    {
                        "observation": observation,
                        "reward": float(visible_reward),
                        "terminated": terminated,
                        "truncated": truncated,
                        "info": info,
                    }
                )
                + "\n"
            )
            process.stdin.flush()
            if terminated or truncated:
                final_score = env.scored_result
                break
    except TimeoutError:
        timed_out = True
    finally:
        if timed_out or final_score is None:
            process.kill()
        process.stdin.close()
        try:
            exit_code = process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            exit_code = process.wait(timeout=10)
    if final_score is None:
        final_score = evaluator.empty_score(len(trajectory))
    return RunResult(final_score, len(trajectory), tuple(trajectory), exit_code, timed_out)
