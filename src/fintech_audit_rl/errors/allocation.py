"""Reduce or remove an instructed KZT payment allocation."""

from hashlib import sha256

from fintech_audit_rl.generator.company import CleanCompany
from fintech_audit_rl.schemas.private import ProvenanceEvent


def short_allocate(
    clean: CleanCompany, payment_id: str, invoice_id: str, actual_source_minor: int
) -> tuple[CleanCompany, ProvenanceEvent]:
    payment = next((item for item in clean.payments if item.payment_id == payment_id), None)
    if payment is None:
        raise ValueError("unknown payment")
    ref = next((item for item in payment.invoice_refs if item.invoice_id == invoice_id), None)
    if (
        ref is None
        or type(actual_source_minor) is not int
        or not 0 <= actual_source_minor < ref.amount_minor
    ):
        raise ValueError("actual allocation must be below a declared positive instruction")
    pair = [
        row
        for row in clean.ledger
        if row.role == "payment_allocation"
        and row.payment_id == payment_id
        and row.invoice_id == invoice_id
    ]
    if len(pair) != 2 or {row.account for row in pair} != {"receivables", "unapplied_cash"}:
        raise ValueError("expected one complete allocation entry")
    if any(row.currency != payment.currency for row in pair):
        raise ValueError("KZT allocation mutation only")
    affected_rows = {row.row_id for row in pair}
    if actual_source_minor:
        ledger = tuple(
            row.model_copy(
                update={
                    "debit_minor": actual_source_minor if row.debit_minor else 0,
                    "credit_minor": actual_source_minor if row.credit_minor else 0,
                    "allocated_source_minor": actual_source_minor
                    if row.account == "receivables"
                    else None,
                }
            )
            if row.row_id in affected_rows
            else row
            for row in clean.ledger
        )
    else:
        ledger = tuple(row for row in clean.ledger if row.row_id not in affected_rows)
    changed = clean.model_copy(
        update={
            "ledger": ledger,
            "manifest": clean.manifest.model_copy(update={"ledger_count": len(ledger)}),
        }
    )
    digest = sha256(
        f"{clean.manifest.episode_id}:{payment_id}:{invoice_id}:allocation".encode()
    ).hexdigest()
    event = ProvenanceEvent(
        event_id=f"id-{digest[:32]}",
        type="partial_allocation",
        mutation="reduced instructed allocation",
        public_ids=[payment.doc_id],
    )
    return changed, event
