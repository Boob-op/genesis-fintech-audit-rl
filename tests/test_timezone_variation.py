from fintech_audit_rl.benchmark.transforms import change_timezone
from fintech_audit_rl.generator.company import seeded_clean_kzt
from fintech_audit_rl.runner.supervisor import run_first_episode
from fintech_audit_rl.validation.financial import clean_kzt_errors


def test_utc_transform_preserves_instants_and_clean_financial_history():
    company, _ = seeded_clean_kzt(401)
    moved = change_timezone(company, "UTC")

    assert moved.policy.timezone == moved.manifest.timezone == "UTC"
    assert moved.manifest.period_start == company.manifest.period_start
    assert all(row.timestamp.utcoffset().total_seconds() == 0 for row in moved.ledger)
    assert (
        clean_kzt_errors(moved.manifest, moved.policy, moved.invoices, moved.payments, moved.ledger)
        == []
    )


def test_worker_finds_same_issue_in_utc():
    original = run_first_episode(402)
    utc = run_first_episode(402, timezone="UTC")

    assert utc.score.metrics == original.score.metrics
    assert utc.score.reward == original.score.reward
    assert utc.steps == original.steps
