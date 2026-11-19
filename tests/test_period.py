from datetime import datetime

from fintech_audit_rl.errors.period import wrong_invoice_period
from fintech_audit_rl.generator.company import seeded_clean_kzt
from fintech_audit_rl.generator.truth import period_truth
from fintech_audit_rl.validation.evidence import period_issues


def test_wrong_period_truth_and_independent_public_reconstruction():
    clean, _ = seeded_clean_kzt(131)
    assert period_issues(clean.manifest, clean.policy, clean.invoices, clean.ledger) == []
    changed, event = wrong_invoice_period(clean, clean.invoices[0].invoice_id)
    truth = period_truth(changed, event)
    public = period_issues(changed.manifest, changed.policy, changed.invoices, changed.ledger)
    assert len(public) == 1
    assert truth.expected_amount_minor == public[0].expected_amount_minor == 100000
    assert truth.currency == public[0].currency == "KZT"
    assert set(truth.affected_ids) == public[0].affected_ids
    assert set(truth.evidence_sets[0]) == public[0].evidence_ids
    assert changed.invoices == clean.invoices
    assert sum(row.debit_minor for row in changed.ledger) == sum(
        row.credit_minor for row in changed.ledger
    )


def test_exact_end_belongs_to_next_period_and_is_clean_when_recorded_there():
    clean, _ = seeded_clean_kzt(132)
    end = clean.policy.period_end
    next_end = datetime(2027, 1, 1, tzinfo=end.tzinfo)
    invoice = clean.invoices[0].model_copy(update={"issued_at": end, "due_at": next_end})
    ledger = tuple(
        row.model_copy(
            update={
                "timestamp": end,
                "effective_at": end,
                "reporting_period_start": end,
                "reporting_period_end": next_end,
            }
        )
        if row.role == "invoice_recognition"
        else row
        for row in clean.ledger
    )
    assert period_issues(clean.manifest, clean.policy, (invoice,), ledger) == []
    wrongly_included = tuple(
        row.model_copy(
            update={
                "reporting_period_start": clean.policy.period_start,
                "reporting_period_end": clean.policy.period_end,
            }
        )
        if row.role == "invoice_recognition"
        else row
        for row in ledger
    )
    issue = period_issues(clean.manifest, clean.policy, (invoice,), wrongly_included)
    assert len(issue) == 1
    assert issue[0].expected_amount_minor == 100000
