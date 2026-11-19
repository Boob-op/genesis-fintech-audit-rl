from decimal import Decimal

from fintech_audit_rl.env.core import AuditEnv
from fintech_audit_rl.errors.duplicate_invoice import duplicate_invoice_recognition
from fintech_audit_rl.evaluation.oracle import oracle_submit
from fintech_audit_rl.evaluation.service import Evaluator
from fintech_audit_rl.generator.company import seeded_clean_kzt
from fintech_audit_rl.generator.truth import duplicate_truth
from fintech_audit_rl.storage.public_store import PublicStore


def episode(seed=29, duplicate=True, closed=False):
    clean, metadata = seeded_clean_kzt(seed)
    issues = ()
    public = clean
    if duplicate:
        public, event = duplicate_invoice_recognition(clean, clean.invoices[0].invoice_id)
        issues = (duplicate_truth(public, event),)
    store = PublicStore(public)
    evaluator = Evaluator(public.manifest.episode_id, issues, store.public_ids)
    env = AuditEnv(store, evaluator.score, evaluator.empty_score, closed=closed)
    return env, public, issues, metadata


def test_reset_inspect_submit_scores_oracle():
    env, public, issues, metadata = episode()
    observation, info = env.reset()
    assert observation["remaining_steps"] == 100
    assert info == {"api_version": "1.0.0"}
    assert "seed" not in observation and "truth" not in observation
    assert metadata.seed not in observation.values()
    seen, reward, terminated, truncated, info = env.step(
        {
            "type": "list_records",
            "table": "ledger",
            "cursor": None,
            "limit": 10,
        }
    )
    assert len(seen["records"]) == 8
    assert (reward, terminated, truncated) == (0, False, False)
    submission = oracle_submit(public.manifest, list(issues)).model_dump(mode="json")
    observed, reward, terminated, truncated, info = env.step(
        {
            "type": "submit",
            "submission": submission,
        }
    )
    assert (terminated, truncated) == (True, False)
    assert env.scored_result.metrics.f1 == 1
    assert reward == Decimal("0.998")
    assert observed["status"] == "submitted"


def test_closed_reward_hidden_and_clean_empty_answer():
    env, public, issues, _ = episode(30, duplicate=False, closed=True)
    env.reset()
    answer = oracle_submit(public.manifest, list(issues)).model_dump(mode="json")
    _, reward, terminated, truncated, _ = env.step({"type": "submit", "submission": answer})
    assert (reward, terminated, truncated) == (0, True, False)
    assert env.scored_result.metrics.f1 == 1
    assert env.scored_result.reward == 1


def test_invalid_submit_and_bounded_query_error():
    env, _, _, _ = episode(31)
    env.reset()
    observation, reward, terminated, truncated, _ = env.step(
        {"type": "get_document", "doc_id": "missing"}
    )
    assert observation == {"error": "invalid_query", "remaining_steps": 99}
    assert (reward, terminated, truncated) == (0, False, False)
    observation, reward, terminated, truncated, _ = env.step(
        {
            "type": "submit",
            "submission": {"episode_id": "wrong", "findings": []},
        }
    )
    assert observation["status"] == "invalid_submit"
    assert (reward, terminated, truncated) == (-1, True, False)
    assert env.scored_result.invalid_submit


def test_hundredth_inspection_truncates_with_empty_answer():
    env, _, _, _ = episode(32)
    env.reset()
    for _ in range(99):
        _, reward, terminated, truncated, _ = env.step({"type": "unknown"})
        assert not terminated and not truncated and reward == 0
    _, reward, terminated, truncated, _ = env.step({"type": "unknown"})
    assert (reward, terminated, truncated) == (-1, False, True)
    assert env.scored_result.metrics.fn == 1
    _, reward, terminated, truncated, _ = env.step({"type": "unknown"})
    assert (reward, terminated, truncated) == (0, False, True)
