import pytest

from fintech_audit_rl.errors.allocation import short_allocate
from fintech_audit_rl.generator.company import seeded_clean_kzt
from fintech_audit_rl.generator.truth import allocation_truth
from fintech_audit_rl.validation.evidence import allocation_issues


@pytest.mark.parametrize(("actual", "expected"), [(40000, 20000), (0, 60000)])
def test_short_allocation_independent_amount_evidence_and_clean_analogue(actual, expected):
    clean, _ = seeded_clean_kzt(111)
    payment = clean.payments[0]
    invoice = clean.invoices[0]
    assert allocation_issues(clean.policy, clean.invoices, clean.payments, clean.ledger) == []
    changed, event = short_allocate(clean, payment.payment_id, invoice.invoice_id, actual)
    truth = allocation_truth(changed, event)
    reconstructed = allocation_issues(
        changed.policy, changed.invoices, changed.payments, changed.ledger
    )
    assert len(reconstructed) == 1
    public = reconstructed[0]
    assert truth.expected_amount_minor == public.expected_amount_minor == expected
    assert truth.currency == public.currency == "KZT"
    assert set(truth.affected_ids) == public.affected_ids == {payment.doc_id, invoice.doc_id}
    assert set(truth.evidence_sets[0]) == public.evidence_ids
    assert len(public.evidence_ids) == (4 if actual else 3)
    assert changed.payments == clean.payments
    assert changed.invoices == clean.invoices
    assert sum(row.debit_minor for row in changed.ledger) == sum(
        row.credit_minor for row in changed.ledger
    )
    assert clean.payments[0].amount_minor == 60000  # legal partial invoice payment
    assert clean.invoices[0].total_minor == 100000
