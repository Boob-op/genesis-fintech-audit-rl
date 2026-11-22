"""Trusted truth construction from causal mutation events."""

from fintech_audit_rl.domain.money import convert_minor
from fintech_audit_rl.generator.company import CleanCompany
from fintech_audit_rl.schemas.private import ProvenanceEvent, TruthIssue
from fintech_audit_rl.schemas.public import fx_evidence_id


def duplicate_truth(changed: CleanCompany, event: ProvenanceEvent) -> TruthIssue:
    if event.type != "duplicate_invoice":
        raise ValueError("wrong mutation type")
    repeated = [row for row in changed.ledger if row.row_id in set(event.public_ids)]
    if len(repeated) != 2 or len({row.invoice_id for row in repeated}) != 1:
        raise ValueError("incomplete duplicate mutation event")
    invoice_id = repeated[0].invoice_id
    invoice = next((doc for doc in changed.invoices if doc.invoice_id == invoice_id), None)
    if invoice is None:
        raise ValueError("mutated invoice document missing")
    amount = next(row.debit_minor for row in repeated if row.account == "receivables")
    group = [
        row
        for row in changed.ledger
        if row.role == "invoice_recognition" and row.invoice_id == invoice_id
    ]
    row_ids = [row.row_id for row in group]
    return TruthIssue(
        issue_id=event.event_id,
        type="duplicate_invoice",
        affected_ids=row_ids,
        expected_amount_minor=amount,
        currency=changed.manifest.base_currency,
        evidence_sets=[[invoice.doc_id, *row_ids, changed.policy.doc_id]],
    )


def allocation_truth(changed: CleanCompany, event: ProvenanceEvent) -> TruthIssue:
    if event.type != "partial_allocation" or len(event.public_ids) != 1:
        raise ValueError("wrong allocation event")
    payment = next((doc for doc in changed.payments if doc.doc_id == event.public_ids[0]), None)
    if payment is None or len(payment.invoice_refs) != 1:
        raise ValueError("unsupported allocation event")
    ref = payment.invoice_refs[0]
    invoice = next((doc for doc in changed.invoices if doc.invoice_id == ref.invoice_id), None)
    if invoice is None:
        raise ValueError("instructed invoice absent")
    credits = [
        row
        for row in changed.ledger
        if row.role == "payment_allocation"
        and row.payment_id == payment.payment_id
        and row.invoice_id == invoice.invoice_id
        and row.account == "receivables"
        and row.credit_minor > 0
    ]
    allocated = sum(row.allocated_source_minor or 0 for row in credits)
    shortage = ref.amount_minor - allocated
    if shortage <= 0:
        raise ValueError("allocation was not reduced")
    return TruthIssue(
        issue_id=event.event_id,
        type="partial_allocation",
        affected_ids=[payment.doc_id, invoice.doc_id],
        expected_amount_minor=shortage,
        currency=payment.currency,
        evidence_sets=[
            [
                payment.doc_id,
                invoice.doc_id,
                changed.policy.doc_id,
                *[row.row_id for row in credits],
            ]
        ],
    )


def fx_truth(changed: CleanCompany, event: ProvenanceEvent) -> TruthIssue:
    if event.type != "fx_date_or_rate" or len(event.public_ids) != 2:
        raise ValueError("wrong FX event")
    receipt = [row for row in changed.ledger if row.row_id in event.public_ids]
    if len(receipt) != 2:
        raise ValueError("receipt evidence missing")
    payment = next(doc for doc in changed.payments if doc.payment_id == receipt[0].payment_id)
    from fintech_audit_rl.domain.time import local_fx_date

    required_date = local_fx_date(payment.timestamp, changed.policy.timezone)
    reference = next(
        row
        for row in changed.fx
        if row.date == required_date
        and row.source_currency == payment.currency
        and row.target_currency == changed.manifest.base_currency
    )
    correct = convert_minor(
        payment.amount_minor,
        reference.rate,
        changed.policy.currency_exponents[payment.currency],
        changed.policy.currency_exponents[changed.manifest.base_currency],
    )
    recorded = next(row.debit_minor for row in receipt if row.account == "bank")
    return TruthIssue(
        issue_id=event.event_id,
        type="fx_date_or_rate",
        affected_ids=event.public_ids,
        expected_amount_minor=abs(recorded - correct),
        currency=changed.manifest.base_currency,
        evidence_sets=[
            [
                payment.doc_id,
                *event.public_ids,
                changed.policy.doc_id,
                fx_evidence_id(changed.manifest.episode_id, reference),
            ]
        ],
    )


def period_truth(changed: CleanCompany, event: ProvenanceEvent) -> TruthIssue:
    if event.type != "period_cutoff" or len(event.public_ids) != 2:
        raise ValueError("wrong period event")
    rows = [row for row in changed.ledger if row.row_id in event.public_ids]
    if len(rows) != 2 or len({row.invoice_id for row in rows}) != 1:
        raise ValueError("period rows missing")
    invoice = next(doc for doc in changed.invoices if doc.invoice_id == rows[0].invoice_id)
    amount = next(row.debit_minor for row in rows if row.account == "receivables")
    return TruthIssue(
        issue_id=event.event_id,
        type="period_cutoff",
        affected_ids=event.public_ids,
        expected_amount_minor=amount,
        currency=changed.manifest.base_currency,
        evidence_sets=[[invoice.doc_id, *event.public_ids, changed.policy.doc_id]],
    )
