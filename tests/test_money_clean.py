from datetime import datetime

import pytest

from fintech_audit_rl.domain.money import convert_minor
from fintech_audit_rl.domain.time import in_period, local_fx_date
from fintech_audit_rl.generator.company import clean_kzt_company


def test_exact_conversion_examples():
    assert convert_minor(10001, "500.25", 2, 2) == 5003000
    assert convert_minor(3, "2.5", 2, 2) == 8
    assert convert_minor(1, "2.5", 2, 2) == 2
    assert convert_minor(101, "150", 2, 0) == 152
    for invalid in (True, 1.0, "1"):
        with pytest.raises(ValueError):
            convert_minor(invalid, "1", 2, 2)


def test_period_and_fx_date_at_offset_boundary():
    start = datetime.fromisoformat("2026-11-01T00:00:00+05:00")
    end = datetime.fromisoformat("2026-12-01T00:00:00+05:00")
    assert in_period(start, start, end)
    assert not in_period(end, start, end)
    assert (
        local_fx_date(datetime.fromisoformat("2026-11-30T19:00:00+00:00"), "Asia/Qyzylorda")
        == "2026-12-01"
    )


def test_clean_history_has_documented_balanced_entries_and_partial_payment():
    company = clean_kzt_company()
    assert company.manifest.ledger_count == len(company.ledger) == 6
    assert company.manifest.invoice_count == len(company.invoices) == 1
    assert company.manifest.payment_count == len(company.payments) == 1
    assert company.manifest.fx_count == 0
    assert company.invoices[0].total_minor == 100000
    assert company.payments[0].amount_minor == 60000
    assert company.payments[0].invoice_refs[0].amount_minor == 60000
    assert sum(row.debit_minor for row in company.ledger) == 220000
    assert sum(row.credit_minor for row in company.ledger) == 220000
    assert (
        sum(
            row.debit_minor - row.credit_minor
            for row in company.ledger
            if row.account == "receivables"
        )
        == 40000
    )
    assert (
        sum(
            row.debit_minor - row.credit_minor
            for row in company.ledger
            if row.account == "unapplied_cash"
        )
        == 0
    )
