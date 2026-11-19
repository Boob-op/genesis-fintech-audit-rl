"""Trusted truth construction from causal mutation events."""

from fintech_audit_rl.generator.company import CleanCompany
from fintech_audit_rl.schemas.private import ProvenanceEvent, TruthIssue


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
