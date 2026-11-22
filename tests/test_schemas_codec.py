"""B02.1 public/private boundary and strict round trips."""

import json

import pytest
from pydantic import ValidationError

from fintech_audit_rl.schemas.actions import Submit
from fintech_audit_rl.schemas.private import PrivateBundle
from fintech_audit_rl.schemas.public import FxRow, LedgerRow, Payment
from fintech_audit_rl.storage.codec import csv_records, jsonl_records, parse_csv, parse_jsonl


def payment_data():
    return {
        "doc_id": "d1",
        "payment_id": "p1",
        "timestamp": "2026-11-20T10:00:00+05:00",
        "currency": "KZT",
        "amount_minor": 100,
        "invoice_refs": [],
    }


def test_payment_json_roundtrip_and_strict_money():
    item = Payment.model_validate_json(json.dumps(payment_data()))
    assert parse_jsonl(jsonl_records([item]), Payment) == [item]
    for value in (True, 100.0, "100", -1):
        data = payment_data() | {"amount_minor": value}
        with pytest.raises(ValidationError):
            Payment.model_validate_json(json.dumps(data))


def test_offset_and_unknown_fields_rejected():
    for data in (
        payment_data() | {"timestamp": "2026-11-20T10:00:00"},
        payment_data() | {"seed": 4},
    ):
        with pytest.raises(ValidationError):
            Payment.model_validate_json(json.dumps(data))


def test_fx_csv_roundtrip_and_invalid_rate():
    fx = FxRow(date="2026-11-20", source_currency="USD", target_currency="KZT", rate="500.25")
    assert parse_csv(csv_records([fx], FxRow), FxRow) == [fx]
    for rate in ("NaN", "Infinity", "0", "-1", "abc"):
        with pytest.raises(ValidationError):
            FxRow(date="2026-11-20", source_currency="USD", target_currency="KZT", rate=rate)


def test_ledger_csv_roundtrip_and_explicit_null():
    row = LedgerRow.model_validate_json(
        json.dumps(
            {
                "row_id": "r1",
                "entry_id": "e1",
                "timestamp": "2026-11-20T10:00:00+05:00",
                "effective_at": "2026-11-20T10:00:00+05:00",
                "account": "receivables",
                "debit_minor": 100,
                "credit_minor": 0,
                "currency": "KZT",
                "entity_id": "entity1",
                "invoice_id": "i1",
                "payment_id": None,
                "role": "invoice_recognition",
                "reporting_period_start": "2026-11-01T00:00:00+05:00",
                "reporting_period_end": "2026-12-01T00:00:00+05:00",
                "fx_date": None,
                "fx_rate": None,
                "allocated_source_minor": None,
            }
        )
    )
    assert parse_csv(csv_records([row], LedgerRow), LedgerRow) == [row]
    with pytest.raises(ValueError):
        parse_csv(csv_records([row], LedgerRow).replace("100", "True"), LedgerRow)


def test_submit_limits_before_normalization():
    finding = {
        "type": "duplicate_invoice",
        "affected_ids": ["r1"],
        "claimed_amount_minor": 1,
        "currency": "KZT",
        "evidence_ids": ["i1"] * 11,
        "explanation": "x",
    }
    with pytest.raises(ValidationError):
        Submit.model_validate({"episode_id": "ep", "findings": [finding]})


def test_private_bundle_has_no_public_document_shape():
    private = PrivateBundle.model_validate(
        {
            "truth": [],
            "provenance": [],
            "generation": {"seed": 42, "config_version": "1", "spec_version": "1"},
        }
    )
    assert "seed" in private.model_dump_json()
    with pytest.raises(ValidationError):
        Payment.model_validate(private.model_dump())
