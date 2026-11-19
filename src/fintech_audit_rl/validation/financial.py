"""Public-data financial checks for the clean KZT receivables history."""

from collections import defaultdict
from collections.abc import Sequence

from fintech_audit_rl.schemas.public import Invoice, LedgerRow, Manifest, Payment, Policy


def clean_kzt_errors(
    manifest: Manifest,
    policy: Policy,
    invoices: Sequence[Invoice],
    payments: Sequence[Payment],
    ledger: Sequence[LedgerRow],
) -> list[str]:
    """Return independently reconstructed discrepancies, without generation imports.

    This baseline requires complete, error-free KZT history. A separate issue
    detector will later analyze intentionally mutated records.
    """
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(manifest.base_currency == "KZT", "base currency is not KZT")
    require(manifest.ledger_count == len(ledger), "ledger count differs from manifest")
    require(manifest.invoice_count == len(invoices), "invoice count differs from manifest")
    require(manifest.payment_count == len(payments), "payment count differs from manifest")
    require(manifest.fx_count == 0, "KZT baseline must have no FX rows")
    require(manifest.policy_doc_id == policy.doc_id, "policy ID differs from manifest")
    require(manifest.period_start == policy.period_start, "period start differs from policy")
    require(manifest.period_end == policy.period_end, "period end differs from policy")
    require(manifest.timezone == policy.timezone, "timezone differs from policy")
    require(manifest.rounding == policy.rounding, "rounding differs from policy")

    invoice_by_id = {invoice.invoice_id: invoice for invoice in invoices}
    payment_by_id = {payment.payment_id: payment for payment in payments}
    require(len(invoice_by_id) == len(invoices), "duplicate invoice document ID")
    require(len(payment_by_id) == len(payments), "duplicate payment document ID")
    public_ids = [policy.doc_id] + [doc.doc_id for doc in (*invoices, *payments)]
    public_ids += [row.row_id for row in ledger]
    require(len(public_ids) == len(set(public_ids)), "duplicate public evidence ID")
    require(
        all(invoice.currency == "KZT" for invoice in invoices), "foreign invoice in KZT baseline"
    )
    require(
        all(payment.currency == "KZT" for payment in payments), "foreign payment in KZT baseline"
    )

    entries: dict[str, list[LedgerRow]] = defaultdict(list)
    for row in ledger:
        entries[row.entry_id].append(row)
        require(row.currency == "KZT", "ledger currency differs from base")
        require(row.fx_date is None and row.fx_rate is None, "unexpected FX on KZT row")
        require(
            row.reporting_period_start == policy.period_start
            and row.reporting_period_end == policy.period_end,
            "entry assigned to wrong period",
        )
        require(row.effective_at == row.timestamp, "effective time differs from entry time")
        require(
            (row.invoice_id is None or row.invoice_id in invoice_by_id)
            and (row.payment_id is None or row.payment_id in payment_by_id),
            "ledger has unknown document link",
        )

    expected_entries: dict[tuple[str, str, str | None], tuple[str, str, int, object, str]] = {}
    for invoice in invoices:
        key = ("invoice_recognition", invoice.invoice_id, None)
        expected_entries[key] = (
            "receivables",
            "revenue",
            invoice.total_minor,
            invoice.issued_at,
            invoice.entity_id,
        )
    for payment in payments:
        key = ("payment_receipt", payment.payment_id, None)
        expected_entries[key] = (
            "bank",
            "unapplied_cash",
            payment.amount_minor,
            payment.timestamp,
            "",
        )
        for ref in payment.invoice_refs:
            invoice = invoice_by_id.get(ref.invoice_id)
            require(invoice is not None, "payment references unknown invoice")
            if invoice is None:
                continue
            require(invoice.currency == payment.currency, "payment/invoice currency differs")
            key = ("payment_allocation", payment.payment_id, ref.invoice_id)
            expected_entries[key] = (
                "unapplied_cash",
                "receivables",
                ref.amount_minor,
                payment.timestamp,
                invoice.entity_id,
            )

    seen: set[tuple[str, str, str | None]] = set()
    for entry_id, rows in entries.items():
        if len(rows) != 2:
            errors.append(f"{entry_id}: entry must have exactly two rows")
            continue
        first, second = rows
        require(first.role == second.role, f"{entry_id}: mixed roles")
        require(first.invoice_id == second.invoice_id, f"{entry_id}: mixed invoice links")
        require(first.payment_id == second.payment_id, f"{entry_id}: mixed payment links")
        require(first.entity_id == second.entity_id, f"{entry_id}: mixed entities")
        require(first.timestamp == second.timestamp, f"{entry_id}: mixed timestamps")
        require(
            first.debit_minor + second.debit_minor == first.credit_minor + second.credit_minor,
            f"{entry_id}: unbalanced entry",
        )
        debits = [row for row in rows if row.debit_minor > 0]
        credits = [row for row in rows if row.credit_minor > 0]
        if len(debits) != 1 or len(credits) != 1:
            errors.append(f"{entry_id}: requires one debit and one credit")
            continue
        debit, credit = debits[0], credits[0]
        if first.role == "invoice_recognition":
            key = (first.role, first.invoice_id or "", None)
            require(first.payment_id is None, f"{entry_id}: invoice entry links payment")
        elif first.role == "payment_receipt":
            key = (first.role, first.payment_id or "", None)
            require(first.invoice_id is None, f"{entry_id}: receipt links invoice")
        else:
            key = (first.role, first.payment_id or "", first.invoice_id)
        expected = expected_entries.get(key)
        if expected is None:
            errors.append(f"{entry_id}: unexpected document entry")
            continue
        require(key not in seen, f"{entry_id}: duplicate document entry")
        seen.add(key)
        debit_account, credit_account, amount, timestamp, entity = expected
        require(debit.account == debit_account, f"{entry_id}: wrong debit account")
        require(credit.account == credit_account, f"{entry_id}: wrong credit account")
        require(debit.debit_minor == amount, f"{entry_id}: wrong debit amount")
        require(credit.credit_minor == amount, f"{entry_id}: wrong credit amount")
        require(first.timestamp == timestamp, f"{entry_id}: wrong document time")
        if entity:
            require(first.entity_id == entity, f"{entry_id}: wrong document entity")
        require(debit.allocated_source_minor is None, f"{entry_id}: debit has allocation")
        require(
            credit.allocated_source_minor
            == (amount if first.role == "payment_allocation" else None),
            f"{entry_id}: wrong allocated source amount",
        )
    for key in expected_entries.keys() - seen:
        errors.append(f"missing entry for {key}")
    return errors
