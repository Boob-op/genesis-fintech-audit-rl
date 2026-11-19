"""Reconstruct duplicate-invoice issues from public KZT records only."""

from dataclasses import dataclass

from fintech_audit_rl.schemas.public import Invoice, LedgerRow, Manifest, Payment, Policy


@dataclass(frozen=True)
class PublicIssue:
    type: str
    affected_ids: frozenset[str]
    expected_amount_minor: int
    currency: str
    evidence_ids: frozenset[str]


def duplicate_invoice_issues(
    manifest: Manifest,
    policy: Policy,
    invoices: tuple[Invoice, ...],
    ledger: tuple[LedgerRow, ...],
) -> list[PublicIssue]:
    """Rebuild expected findings; never read provenance, seed or truth."""
    if manifest.base_currency != "KZT" or policy.doc_id != manifest.policy_doc_id:
        raise ValueError("this independent checker supports the KZT baseline only")
    issues = []
    for invoice in invoices:
        if invoice.currency != "KZT":
            raise ValueError("foreign invoice requires FX-aware checker")
        rows = [
            row
            for row in ledger
            if row.role == "invoice_recognition" and row.invoice_id == invoice.invoice_id
        ]
        entries = {row.entry_id for row in rows}
        if len(entries) <= 1:
            continue
        for entry_id in entries:
            pair = [row for row in rows if row.entry_id == entry_id]
            if len(pair) != 2 or sum(row.debit_minor for row in pair) != sum(
                row.credit_minor for row in pair
            ):
                raise ValueError("malformed recognition entry")
        recognized = sum(row.debit_minor for row in rows if row.account == "receivables")
        excess = recognized - invoice.total_minor
        if excess <= 0:
            raise ValueError("repeated entries do not create positive excess")
        row_ids = frozenset(row.row_id for row in rows)
        issues.append(
            PublicIssue(
                type="duplicate_invoice",
                affected_ids=row_ids,
                expected_amount_minor=excess,
                currency="KZT",
                evidence_ids=row_ids | {invoice.doc_id, policy.doc_id},
            )
        )
    return issues


def allocation_issues(
    policy: Policy,
    invoices: tuple[Invoice, ...],
    payments: tuple[Payment, ...],
    ledger: tuple[LedgerRow, ...],
) -> list[PublicIssue]:
    """Compare declared source-unit instructions to complete public allocation rows."""
    invoice_by_id = {invoice.invoice_id: invoice for invoice in invoices}
    issues = []
    for payment in payments:
        for ref in payment.invoice_refs:
            invoice = invoice_by_id.get(ref.invoice_id)
            if invoice is None or invoice.currency != payment.currency:
                raise ValueError("unsupported payment reference")
            rows = [
                row
                for row in ledger
                if row.role == "payment_allocation"
                and row.payment_id == payment.payment_id
                and row.invoice_id == ref.invoice_id
                and row.account == "receivables"
                and row.credit_minor > 0
            ]
            allocated = sum(row.allocated_source_minor or 0 for row in rows)
            if allocated > ref.amount_minor:
                raise ValueError("over-allocation is outside this passport")
            if allocated == ref.amount_minor:
                continue
            evidence = {payment.doc_id, invoice.doc_id, policy.doc_id}
            evidence.update(row.row_id for row in rows)
            issues.append(
                PublicIssue(
                    type="partial_allocation",
                    affected_ids=frozenset((payment.doc_id, invoice.doc_id)),
                    expected_amount_minor=ref.amount_minor - allocated,
                    currency=payment.currency,
                    evidence_ids=frozenset(evidence),
                )
            )
    return issues
