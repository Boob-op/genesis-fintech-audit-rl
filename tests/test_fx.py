from fintech_audit_rl.errors.fx import wrong_receipt_fx
from fintech_audit_rl.generator.company import clean_usd_company
from fintech_audit_rl.generator.truth import fx_truth
from fintech_audit_rl.storage.public_store import PublicStore
from fintech_audit_rl.validation.evidence import receipt_fx_issues
from fintech_audit_rl.validation.financial import clean_foreign_errors


def test_foreign_clean_and_wrong_date_rate_are_independently_reconstructed():
    clean, _ = clean_usd_company(121)
    store = PublicStore(clean)
    fx_records = tuple(store.list_records("fx", None, 50)["records"])
    assert len(fx_records) == clean.manifest.fx_count == 4
    assert (
        receipt_fx_issues(clean.manifest, clean.policy, clean.payments, clean.ledger, fx_records)
        == []
    )
    assert (
        clean_foreign_errors(
            clean.manifest, clean.policy, clean.invoices, clean.payments, clean.ledger, fx_records
        )
        == []
    )
    changed, event = wrong_receipt_fx(clean, clean.payments[0].payment_id, "2026-11-09")
    truth = fx_truth(changed, event)
    public = receipt_fx_issues(
        changed.manifest, changed.policy, changed.payments, changed.ledger, fx_records
    )
    assert len(public) == 1
    assert truth.expected_amount_minor == public[0].expected_amount_minor == 10001
    assert truth.currency == public[0].currency == "KZT"
    assert set(truth.affected_ids) == public[0].affected_ids
    assert set(truth.evidence_sets[0]) == public[0].evidence_ids
    assert len(public[0].evidence_ids) == 5
    assert sum(row.debit_minor for row in changed.ledger) == sum(
        row.credit_minor for row in changed.ledger
    )
    assert changed.payments == clean.payments
    assert clean_foreign_errors(
        changed.manifest,
        changed.policy,
        changed.invoices,
        changed.payments,
        changed.ledger,
        fx_records,
    )


def test_wrong_date_with_same_rounded_amount_is_still_an_issue():
    clean, _ = clean_usd_company(123)
    changed, event = wrong_receipt_fx(clean, clean.payments[0].payment_id, "2026-11-08")
    store = PublicStore(changed)
    fx_records = tuple(store.list_records("fx", None, 50)["records"])
    truth = fx_truth(changed, event)
    public = receipt_fx_issues(
        changed.manifest, changed.policy, changed.payments, changed.ledger, fx_records
    )
    assert truth.expected_amount_minor == public[0].expected_amount_minor == 0
    assert public[0].type == "fx_date_or_rate"
