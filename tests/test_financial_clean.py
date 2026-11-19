"""Independent checks use only public models and manually changed records."""

import pytest

from fintech_audit_rl.domain.spec import load_error_spec
from fintech_audit_rl.generator.company import clean_kzt_company, seeded_clean_kzt
from fintech_audit_rl.schemas.public import Invoice, LedgerRow, Payment
from fintech_audit_rl.storage.codec import (
    csv_records,
    json_record,
    jsonl_records,
    parse_csv,
    parse_jsonl,
)
from fintech_audit_rl.validation.financial import clean_kzt_errors


def inspect(company):
    return clean_kzt_errors(
        company.manifest, company.policy, company.invoices, company.payments, company.ledger
    )


def test_clean_company_passes_public_financial_check():
    assert inspect(clean_kzt_company()) == []


def test_seeded_clean_company_replays_and_keeps_seed_private():
    company, metadata = seeded_clean_kzt(41)
    replay, replay_metadata = seeded_clean_kzt(41)
    different, _ = seeded_clean_kzt(42)
    assert company == replay
    assert metadata == replay_metadata
    assert company.manifest.episode_id != different.manifest.episode_id
    assert inspect(company) == []
    public = json_record(company.manifest) + json_record(company.policy)
    public += jsonl_records(company.invoices) + jsonl_records(company.payments)
    public += csv_records(company.ledger, LedgerRow)
    assert '"seed"' not in public
    assert '"truth"' not in public
    assert '"provenance"' not in public
    assert parse_jsonl(jsonl_records(company.invoices), Invoice) == list(company.invoices)
    assert parse_jsonl(jsonl_records(company.payments), Payment) == list(company.payments)
    assert parse_csv(csv_records(company.ledger, LedgerRow), LedgerRow) == list(company.ledger)


def test_single_versioned_error_spec_loads():
    spec = load_error_spec()
    assert spec["spec_version"] == "1.0.0"
    assert len(spec["errors"]) == 4


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ("omit_allocation", "missing entry"),
        ("duplicate_invoice", "duplicate document entry"),
        ("unbalanced", "unbalanced entry"),
        ("wrong_account", "wrong credit account"),
        ("wrong_amount", "wrong debit amount"),
        ("wrong_allocation", "wrong allocated source amount"),
        ("wrong_manifest", "ledger count differs"),
        ("wrong_time", "wrong document time"),
    ],
)
def test_public_changes_are_detected(change, expected):
    clean = clean_kzt_company()
    ledger = list(clean.ledger)
    manifest = clean.manifest
    if change == "omit_allocation":
        ledger = ledger[:-2]
    elif change == "duplicate_invoice":
        ledger += [
            ledger[0].model_copy(update={"row_id": "other-1", "entry_id": "other"}),
            ledger[1].model_copy(update={"row_id": "other-2", "entry_id": "other"}),
        ]
    elif change == "unbalanced":
        ledger[1] = ledger[1].model_copy(update={"credit_minor": 99999})
    elif change == "wrong_account":
        ledger[1] = ledger[1].model_copy(update={"account": "bank"})
    elif change == "wrong_amount":
        ledger[0] = ledger[0].model_copy(update={"debit_minor": 99999})
    elif change == "wrong_allocation":
        ledger[5] = ledger[5].model_copy(update={"allocated_source_minor": 40000})
    elif change == "wrong_manifest":
        manifest = manifest.model_copy(update={"ledger_count": 5})
    elif change == "wrong_time":
        ledger[0] = ledger[0].model_copy(update={"timestamp": clean.payments[0].timestamp})
        ledger[1] = ledger[1].model_copy(update={"timestamp": clean.payments[0].timestamp})
    errors = clean_kzt_errors(manifest, clean.policy, clean.invoices, clean.payments, ledger)
    assert any(expected in error for error in errors), errors
