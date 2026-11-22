from fintech_audit_rl.errors.duplicate_invoice import duplicate_invoice_recognition
from fintech_audit_rl.generator.company import seeded_clean_kzt
from fintech_audit_rl.validation.financial import clean_kzt_errors


def test_duplicate_mutates_invoice_recognition_not_payment():
    clean, _ = seeded_clean_kzt(7)
    invoice_id = clean.invoices[0].invoice_id
    changed, event = duplicate_invoice_recognition(clean, invoice_id)
    assert len(clean.ledger) == 6
    assert len(changed.ledger) == changed.manifest.ledger_count == 8
    assert changed.invoices == clean.invoices
    assert changed.payments == clean.payments
    assert [row for row in changed.ledger if row.role == "payment_receipt"] == [
        row for row in clean.ledger if row.role == "payment_receipt"
    ]
    assert event.type == "duplicate_invoice"
    assert len(event.public_ids) == 2
    assert set(event.public_ids) == {row.row_id for row in changed.ledger[-2:]}
    assert not clean_kzt_errors(
        clean.manifest, clean.policy, clean.invoices, clean.payments, clean.ledger
    )
    errors = clean_kzt_errors(
        changed.manifest, changed.policy, changed.invoices, changed.payments, changed.ledger
    )
    assert any("duplicate document entry" in error for error in errors)
    assert sum(row.debit_minor for row in changed.ledger) == sum(
        row.credit_minor for row in changed.ledger
    )
