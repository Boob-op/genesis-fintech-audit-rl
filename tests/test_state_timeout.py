from decimal import Decimal

from fintech_audit_rl.env.core import AuditEnv
from fintech_audit_rl.evaluation.service import Evaluator
from fintech_audit_rl.generator.company import seeded_clean_kzt
from fintech_audit_rl.runner.supervisor import run_first_episode
from fintech_audit_rl.storage.public_store import PublicStore


def clean_env():
    company, _ = seeded_clean_kzt(81)
    store = PublicStore(company)
    evaluator = Evaluator(company.manifest.episode_id, (), store.public_ids)
    return AuditEnv(store, evaluator.score, evaluator.empty_score), company


def test_submit_on_hundredth_action_and_repeat_after_close():
    env, company = clean_env()
    env.reset()
    for _ in range(99):
        env.step({"type": "unknown"})
    _, reward, terminated, truncated, _ = env.step(
        {
            "type": "submit",
            "submission": {"episode_id": company.manifest.episode_id, "findings": []},
        }
    )
    assert (reward, terminated, truncated) == (Decimal("0.802"), True, False)
    _, reward, terminated, truncated, _ = env.step({"type": "unknown"})
    assert (reward, terminated, truncated) == (0, True, False)
    observation, info = env.reset()
    assert observation["remaining_steps"] == 100
    assert env.scored_result is None
    assert info["api_version"] == "1.0.0"


def test_timeout_forms_empty_answer_and_stops_worker():
    run = run_first_episode(82, timeout_seconds=0)
    assert run.truncated
    assert run.score.metrics.fn == 1
    assert run.score.reward == -1
    assert run.steps == 0
    assert run.worker_exit_code != 0
