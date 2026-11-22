from fintech_audit_rl.generator.company import scaled_clean_kzt_company
from fintech_audit_rl.runner.supervisor import run_first_episode
from fintech_audit_rl.validation.financial import clean_kzt_errors


def test_recommended_lower_size_is_clean_and_meaningful():
    company, _ = scaled_clean_kzt_company(81)

    assert company.manifest.ledger_count == 204
    assert company.manifest.invoice_count + company.manifest.payment_count == 68
    assert (
        clean_kzt_errors(
            company.manifest,
            company.policy,
            company.invoices,
            company.payments,
            company.ledger,
        )
        == []
    )


def test_scaled_error_is_reachable_with_small_evidence_and_action_budget():
    result = run_first_episode(82, scale_pairs=34)

    assert result.score.metrics.f1 == 1
    assert result.score.metrics.tp == 1
    assert result.steps <= 100
    submission = result.trajectory[-1]["action"]["submission"]
    assert len(submission["findings"]) == 1
    assert len(submission["findings"][0]["evidence_ids"]) <= 10


def test_scaled_clean_case_has_no_false_positive():
    result = run_first_episode(83, duplicate=False, scale_pairs=34)

    assert result.score.metrics.f1 == 1
    assert result.score.metrics.fp == result.score.metrics.fn == 0
    assert result.steps <= 100
