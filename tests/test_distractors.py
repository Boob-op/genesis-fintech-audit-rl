from fintech_audit_rl.benchmark.transforms import rename_ids, shuffle_ledger
from fintech_audit_rl.generator.company import clean_distractor_company
from fintech_audit_rl.runner.supervisor import run_first_episode
from fintech_audit_rl.validation.financial import clean_kzt_errors


def _validate(company):
    return clean_kzt_errors(
        company.manifest,
        company.policy,
        company.invoices,
        company.payments,
        company.ledger,
    )


def test_clean_distractors_are_explicit_and_financially_valid():
    company, _ = clean_distractor_company(73)

    assert _validate(company) == []
    assert sorted(invoice.total_minor for invoice in company.invoices) == [100000, 100000]
    split = [
        payment
        for payment in company.payments
        if payment.invoice_refs
        and payment.invoice_refs[0].invoice_id == company.invoices[0].invoice_id
    ]
    assert sorted(payment.amount_minor for payment in split) == [40000, 60000]
    refund = next(payment for payment in company.payments if payment.kind == "refund")
    advance = next(
        payment for payment in company.payments if payment.payment_id == refund.reverses_payment_id
    )
    assert advance.invoice_refs == []
    assert refund.amount_minor == advance.amount_minor == 15000
    assert any(row.role == "payment_refund" for row in company.ledger)


def test_clean_distractors_survive_rename_and_shuffle():
    company, _ = clean_distractor_company(74)
    renamed = rename_ids(company)
    shuffled = shuffle_ledger(company, 74)

    assert _validate(renamed) == []
    assert _validate(shuffled) == []
    refund = next(payment for payment in renamed.payments if payment.kind == "refund")
    assert refund.reverses_payment_id in {payment.payment_id for payment in renamed.payments}


def test_reconciliation_policy_has_no_false_positive_on_distractors():
    for transform in ("none", "rename", "shuffle"):
        result = run_first_episode(
            75,
            duplicate=False,
            distractors=True,
            transform=transform,
        )
        assert result.score.metrics.f1 == 1
        assert result.score.metrics.tp == result.score.metrics.fp == result.score.metrics.fn == 0
