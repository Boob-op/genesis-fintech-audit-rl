"""Trusted first-scenario supervisor; developer subprocess is not OS isolation."""

import json
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass

from fintech_audit_rl.benchmark.transforms import rename_ids, shuffle_ledger
from fintech_audit_rl.env.core import AuditEnv
from fintech_audit_rl.errors.allocation import short_allocate
from fintech_audit_rl.errors.duplicate_invoice import duplicate_invoice_recognition
from fintech_audit_rl.errors.fx import wrong_receipt_fx
from fintech_audit_rl.errors.period import wrong_invoice_period
from fintech_audit_rl.evaluation.service import Evaluator, Score
from fintech_audit_rl.generator.company import (
    clean_distractor_company,
    clean_usd_company,
    seeded_clean_kzt,
)
from fintech_audit_rl.generator.truth import (
    allocation_truth,
    duplicate_truth,
    fx_truth,
    period_truth,
)
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
) -> RunResult:
    if policy not in {"reconciliation", "flag_all", "random_explorer"}:
        raise ValueError("unknown policy")
    if type(policy_seed) is not int:
        raise ValueError("policy seed must be integer")
    if transform not in {"none", "rename", "shuffle"}:
        raise ValueError("unknown transform")
    if not 0 <= timeout_seconds <= 60:
        raise ValueError("timeout outside developer contract")
    deadline = time.monotonic() + timeout_seconds
    if fx_case and duplicate:
        raise ValueError("FX case cannot contain duplicate invoice in v1")
    if fx_error and not fx_case:
        raise ValueError("FX mutation requires foreign case")
    if distractors and (
        fx_case or duplicate or allocation_actual_minor is not None or period_error
    ):
        raise ValueError("clean distractors cannot be combined with v1 mutations")
    clean, _private_generation = (
        clean_distractor_company(seed)
        if distractors
        else clean_usd_company(seed)
        if fx_case
        else seeded_clean_kzt(seed)
    )
    if transform == "rename":
        clean = rename_ids(clean)
    public = clean
    issues = ()
    if duplicate:
        public, event = duplicate_invoice_recognition(clean, clean.invoices[0].invoice_id)
        issues = (duplicate_truth(public, event),)
    if allocation_actual_minor is not None:
        public, event = short_allocate(
            public,
            public.payments[0].payment_id,
            public.invoices[0].invoice_id,
            allocation_actual_minor,
        )
        issues = (*issues, allocation_truth(public, event))
    if fx_error:
        public, event = wrong_receipt_fx(public, public.payments[0].payment_id, "2026-11-09")
        issues = (*issues, fx_truth(public, event))
    if period_error:
        if fx_case or duplicate:
            raise ValueError("period mutation is standalone in v1")
        public, event = wrong_invoice_period(public, public.invoices[0].invoice_id)
        issues = (*issues, period_truth(public, event))
    if transform == "shuffle":
        public = shuffle_ledger(public, seed)
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
