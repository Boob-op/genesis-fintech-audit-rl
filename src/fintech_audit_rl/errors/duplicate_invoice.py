"""Repeat recognition of one genuine invoice, preserving balanced entries."""

from hashlib import sha256

from fintech_audit_rl.generator.company import CleanCompany
from fintech_audit_rl.schemas.private import ProvenanceEvent


def duplicate_invoice_recognition(
    clean: CleanCompany, invoice_id: str
) -> tuple[CleanCompany, ProvenanceEvent]:
    """Return a changed public bundle and private causal event.

    The original and repeated entries share one invoice document. The new
    entry uses fresh public IDs; insertion order has no meaning for truth.
    """
    invoice = next((item for item in clean.invoices if item.invoice_id == invoice_id), None)
    if invoice is None:
        raise ValueError("unknown invoice")
    original = [
        row
        for row in clean.ledger
        if row.role == "invoice_recognition" and row.invoice_id == invoice_id
    ]
    if len(original) != 2 or len({row.entry_id for row in original}) != 1:
        raise ValueError("invoice must have exactly one recognition entry")
    if {row.account for row in original} != {"receivables", "revenue"}:
        raise ValueError("recognition accounts differ from contract")
    existing_ids = {row.row_id for row in clean.ledger}
    existing_entries = {row.entry_id for row in clean.ledger}

    def opaque(label: str) -> str:
        digest = sha256(f"{clean.manifest.episode_id}:{invoice_id}:{label}".encode()).hexdigest()
        return f"id-{digest[:32]}"

    entry_id = opaque("entry")
    if entry_id in existing_entries:
        raise ValueError("repeated entry ID already exists")
    repeated = []
    for position, row in enumerate(original):
        row_id = opaque(f"leg-{position}")
        if row_id in existing_ids:
            raise ValueError("repeated row ID already exists")
        repeated.append(row.model_copy(update={"row_id": row_id, "entry_id": entry_id}))
    ledger = (*clean.ledger, *repeated)
    changed = clean.model_copy(
        update={
            "ledger": ledger,
            "manifest": clean.manifest.model_copy(update={"ledger_count": len(ledger)}),
        }
    )
    event = ProvenanceEvent(
        event_id=opaque("provenance"),
        type="duplicate_invoice",
        mutation="repeated invoice recognition entry",
        public_ids=[row.row_id for row in repeated],
    )
    return changed, event
