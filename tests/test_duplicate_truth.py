from fintech_audit_rl.errors.duplicate_invoice import duplicate_invoice_recognition
from fintech_audit_rl.generator.company import seeded_clean_kzt
from fintech_audit_rl.generator.truth import duplicate_truth
from fintech_audit_rl.validation.evidence import duplicate_invoice_issues


def test_truth_agrees_with_independent_public_reconstruction():
    clean, _ = seeded_clean_kzt(11)
    changed, event = duplicate_invoice_recognition(clean, clean.invoices[0].invoice_id)
    truth = duplicate_truth(changed, event)
    reconstructed = duplicate_invoice_issues(
        changed.manifest, changed.policy, changed.invoices, changed.ledger
    )
    assert len(reconstructed) == 1
    public = reconstructed[0]
    assert truth.type == public.type
    assert truth.expected_amount_minor == public.expected_amount_minor == 100000
    assert truth.currency == public.currency == "KZT"
    assert set(truth.affected_ids) == public.affected_ids
    assert set(truth.evidence_sets[0]) == public.evidence_ids
    assert len(public.evidence_ids) == 6
    assert (
        duplicate_invoice_issues(clean.manifest, clean.policy, clean.invoices, clean.ledger) == []
    )


def test_independent_reconstruction_is_order_invariant():
    clean, _ = seeded_clean_kzt(12)
    changed, event = duplicate_invoice_recognition(clean, clean.invoices[0].invoice_id)
    original = duplicate_invoice_issues(
        changed.manifest, changed.policy, changed.invoices, changed.ledger
    )
    shuffled = duplicate_invoice_issues(
        changed.manifest, changed.policy, changed.invoices, tuple(reversed(changed.ledger))
    )
    assert shuffled == original
    assert set(duplicate_truth(changed, event).affected_ids) == original[0].affected_ids
