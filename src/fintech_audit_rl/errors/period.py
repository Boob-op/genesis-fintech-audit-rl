"""Move both invoice-recognition legs to the adjacent reporting period."""

from datetime import datetime
from hashlib import sha256

from fintech_audit_rl.generator.company import CleanCompany
from fintech_audit_rl.schemas.private import ProvenanceEvent


def wrong_invoice_period(
    company: CleanCompany, invoice_id: str
) -> tuple[CleanCompany, ProvenanceEvent]:
    invoice = next((doc for doc in company.invoices if doc.invoice_id == invoice_id), None)
    if invoice is None or invoice.currency != company.manifest.base_currency:
        raise ValueError("domestic invoice required")
    rows = [
        row
        for row in company.ledger
        if row.role == "invoice_recognition" and row.invoice_id == invoice_id
    ]
    if len(rows) != 2 or len({row.entry_id for row in rows}) != 1:
        raise ValueError("one complete recognition entry required")
    # The next month is the adjacent synthetic period in this v1 scenario.
    start = company.policy.period_end
    next_month = start.month + 1
    year = start.year
    if next_month == 13:
        next_month, year = 1, year + 1
    end = datetime(year, next_month, 1, tzinfo=start.tzinfo)
    ids = {row.row_id for row in rows}
    ledger = tuple(
        row.model_copy(
            update={
                "reporting_period_start": start,
                "reporting_period_end": end,
            }
        )
        if row.row_id in ids
        else row
        for row in company.ledger
    )
    digest = sha256(f"{company.manifest.episode_id}:{invoice_id}:period".encode()).hexdigest()
    return company.model_copy(update={"ledger": ledger}), ProvenanceEvent(
        event_id=f"id-{digest[:32]}",
        type="period_cutoff",
        mutation="invoice recognition assigned to adjacent period",
        public_ids=[row.row_id for row in rows],
    )
