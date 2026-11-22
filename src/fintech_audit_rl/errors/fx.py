"""Mutate both receipt legs to an alternate public FX date and rate."""

from hashlib import sha256

from fintech_audit_rl.domain.money import convert_minor
from fintech_audit_rl.generator.company import CleanCompany
from fintech_audit_rl.schemas.private import ProvenanceEvent


def wrong_receipt_fx(
    company: CleanCompany, payment_id: str, alternate_date: str
) -> tuple[CleanCompany, ProvenanceEvent]:
    payment = next((doc for doc in company.payments if doc.payment_id == payment_id), None)
    if payment is None or payment.currency == company.manifest.base_currency:
        raise ValueError("foreign payment required")
    alternate = next(
        (
            row
            for row in company.fx
            if row.date == alternate_date
            and row.source_currency == payment.currency
            and row.target_currency == company.manifest.base_currency
        ),
        None,
    )
    if alternate is None:
        raise ValueError("alternate FX row absent")
    receipt = [
        row
        for row in company.ledger
        if row.role == "payment_receipt" and row.payment_id == payment_id
    ]
    if len(receipt) != 2 or len({row.entry_id for row in receipt}) != 1:
        raise ValueError("one complete receipt required")
    amount = convert_minor(
        payment.amount_minor,
        alternate.rate,
        company.policy.currency_exponents[payment.currency],
        company.policy.currency_exponents[company.manifest.base_currency],
    )
    ids = {row.row_id for row in receipt}
    ledger = tuple(
        row.model_copy(
            update={
                "debit_minor": amount if row.debit_minor else 0,
                "credit_minor": amount if row.credit_minor else 0,
                "fx_date": alternate.date,
                "fx_rate": alternate.rate,
            }
        )
        if row.row_id in ids
        else row
        for row in company.ledger
    )
    digest = sha256(f"{company.manifest.episode_id}:{payment_id}:receipt-fx".encode()).hexdigest()
    return company.model_copy(update={"ledger": ledger}), ProvenanceEvent(
        event_id=f"id-{digest[:32]}",
        type="fx_date_or_rate",
        mutation="alternate receipt FX date and rate",
        public_ids=[row.row_id for row in receipt],
    )
