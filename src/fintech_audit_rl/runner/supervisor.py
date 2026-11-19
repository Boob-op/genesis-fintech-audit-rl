"""Trusted first-scenario supervisor; developer subprocess is not OS isolation."""

import json
import subprocess
import sys
from dataclasses import dataclass

from fintech_audit_rl.env.core import AuditEnv
from fintech_audit_rl.errors.duplicate_invoice import duplicate_invoice_recognition
from fintech_audit_rl.evaluation.service import Evaluator, Score
from fintech_audit_rl.generator.company import seeded_clean_kzt
from fintech_audit_rl.generator.truth import duplicate_truth
from fintech_audit_rl.storage.public_store import PublicStore


@dataclass(frozen=True)
class RunResult:
    score: Score
    steps: int
    trajectory: tuple[dict, ...]
    worker_exit_code: int


def run_first_episode(
    seed: int, duplicate: bool = True, closed: bool = False, policy: str = "reconciliation"
) -> RunResult:
    if policy not in {"reconciliation", "flag_all"}:
        raise ValueError("unknown policy")
    clean, _private_generation = seeded_clean_kzt(seed)
    public = clean
    issues = ()
    if duplicate:
        public, event = duplicate_invoice_recognition(clean, clean.invoices[0].invoice_id)
        issues = (duplicate_truth(public, event),)
    store = PublicStore(public)
    evaluator = Evaluator(public.manifest.episode_id, issues, store.public_ids)
    env = AuditEnv(store, evaluator.score, evaluator.empty_score, closed=closed)
    initial, info = env.reset()
    trajectory = []
    # This is a developer-mode process boundary. B04 must add actual file/network rights.
    process = subprocess.Popen(
        [sys.executable, "-m", "fintech_audit_rl.runner.worker", policy],
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
    while True:
        line = process.stdout.readline()
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
    process.stdin.close()
    exit_code = process.wait(timeout=10)
    if final_score is None:
        final_score = evaluator.empty_score(len(trajectory))
    return RunResult(final_score, len(trajectory), tuple(trajectory), exit_code)
