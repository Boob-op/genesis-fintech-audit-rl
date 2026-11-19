"""Small KZT receivables history for B02.2; no seeded variability yet."""

from datetime import datetime
from random import Random

from pydantic import BaseModel, ConfigDict

from fintech_audit_rl.schemas.private import GenerationMetadata
from fintech_audit_rl.schemas.public import FxRow, Invoice, LedgerRow, Manifest, Payment, Policy


class CleanCompany(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest: Manifest
    policy: Policy
    invoices: tuple[Invoice, ...]
    payments: tuple[Payment, ...]
    ledger: tuple[LedgerRow, ...]
    fx: tuple[FxRow, ...] = ()


def _row(
    row_id: str,
    entry_id: str,
    timestamp: datetime,
    account: str,
    amount: int,
    side: str,
    role: str,
    start: datetime,
    end: datetime,
    invoice_id: str | None,
    payment_id: str | None,
    allocated_source_minor: int | None = None,
) -> LedgerRow:
    return LedgerRow(
        row_id=row_id,
        entry_id=entry_id,
        timestamp=timestamp,
        effective_at=timestamp,
        account=account,
        debit_minor=amount if side == "debit" else 0,
        credit_minor=amount if side == "credit" else 0,
        currency="KZT",
        entity_id="entity-1",
        invoice_id=invoice_id,
        payment_id=payment_id,
        role=role,
        reporting_period_start=start,
        reporting_period_end=end,
        fx_date=None,
        fx_rate=None,
        allocated_source_minor=allocated_source_minor,
    )


def clean_kzt_company() -> CleanCompany:
    """One invoice and a legal partial payment: 40000 KZT minor remains receivable."""
    start = datetime.fromisoformat("2026-11-01T00:00:00+05:00")
    end = datetime.fromisoformat("2026-12-01T00:00:00+05:00")
    issued = datetime.fromisoformat("2026-11-03T09:00:00+05:00")
    paid = datetime.fromisoformat("2026-11-10T12:00:00+05:00")
    policy = Policy(
        doc_id="policy-1",
        timezone="Asia/Qyzylorda",
        period_start=start,
        period_end=end,
        currency_exponents={"KZT": 2, "USD": 2, "JPY": 0},
        rounding="ROUND_HALF_EVEN",
        invoice_recognition="issued_at",
        payment_recognition="timestamp",
        fx_date_rule="local_event_date",
        allocation_rule="immediate_invoice_refs",
    )
    invoice = Invoice(
        doc_id="doc-invoice-1",
        invoice_id="invoice-1",
        entity_id="entity-1",
        issued_at=issued,
        due_at=end,
        currency="KZT",
        total_minor=100000,
        line_items=[{"description": "Synthetic service", "amount_minor": 100000}],
    )
    payment = Payment(
        doc_id="doc-payment-1",
        payment_id="payment-1",
        timestamp=paid,
        currency="KZT",
        amount_minor=60000,
        invoice_refs=[{"invoice_id": "invoice-1", "amount_minor": 60000}],
    )
    ledger = (
        _row(
            "row-1",
            "entry-1",
            issued,
            "receivables",
            100000,
            "debit",
            "invoice_recognition",
            start,
            end,
            "invoice-1",
            None,
        ),
        _row(
            "row-2",
            "entry-1",
            issued,
            "revenue",
            100000,
            "credit",
            "invoice_recognition",
            start,
            end,
            "invoice-1",
            None,
        ),
        _row(
            "row-3",
            "entry-2",
            paid,
            "bank",
            60000,
            "debit",
            "payment_receipt",
            start,
            end,
            None,
            "payment-1",
        ),
        _row(
            "row-4",
            "entry-2",
            paid,
            "unapplied_cash",
            60000,
            "credit",
            "payment_receipt",
            start,
            end,
            None,
            "payment-1",
        ),
        _row(
            "row-5",
            "entry-3",
            paid,
            "unapplied_cash",
            60000,
            "debit",
            "payment_allocation",
            start,
            end,
            "invoice-1",
            "payment-1",
        ),
        _row(
            "row-6",
            "entry-3",
            paid,
            "receivables",
            60000,
            "credit",
            "payment_allocation",
            start,
            end,
            "invoice-1",
            "payment-1",
            60000,
        ),
    )
    manifest = Manifest(
        schema_version="1.0.0",
        episode_id="clean-kzt-1",
        base_currency="KZT",
        period_start=start,
        period_end=end,
        timezone=policy.timezone,
        ledger_count=len(ledger),
        invoice_count=1,
        payment_count=1,
        fx_count=0,
        policy_doc_id=policy.doc_id,
        rounding=policy.rounding,
    )
    return CleanCompany(
        manifest=manifest, policy=policy, invoices=(invoice,), payments=(payment,), ledger=ledger
    )


def seeded_clean_kzt(
    seed: int, config_version: str = "1"
) -> tuple[CleanCompany, GenerationMetadata]:
    """Generate local opaque IDs; keep seed only in trusted metadata."""
    if type(seed) is not int or not config_version:
        raise ValueError("seed must be integer and config_version nonempty")
    base = clean_kzt_company()
    rng = Random(seed)
    old_ids = [
        base.manifest.episode_id,
        base.policy.doc_id,
        base.invoices[0].doc_id,
        base.invoices[0].invoice_id,
        base.invoices[0].entity_id,
        base.payments[0].doc_id,
        base.payments[0].payment_id,
        *(row.row_id for row in base.ledger),
        *(row.entry_id for row in base.ledger),
    ]
    mapping = {old: f"id-{rng.getrandbits(128):032x}" for old in dict.fromkeys(old_ids)}

    def new(old: str | None) -> str | None:
        return mapping[old] if old is not None else None

    policy = base.policy.model_copy(update={"doc_id": new(base.policy.doc_id)})
    invoice = base.invoices[0].model_copy(
        update={
            "doc_id": new(base.invoices[0].doc_id),
            "invoice_id": new(base.invoices[0].invoice_id),
            "entity_id": new(base.invoices[0].entity_id),
        }
    )
    payment = base.payments[0].model_copy(
        update={
            "doc_id": new(base.payments[0].doc_id),
            "payment_id": new(base.payments[0].payment_id),
            "invoice_refs": [
                ref.model_copy(update={"invoice_id": new(ref.invoice_id)})
                for ref in base.payments[0].invoice_refs
            ],
        }
    )
    ledger = tuple(
        row.model_copy(
            update={
                "row_id": new(row.row_id),
                "entry_id": new(row.entry_id),
                "entity_id": new(row.entity_id),
                "invoice_id": new(row.invoice_id),
                "payment_id": new(row.payment_id),
            }
        )
        for row in base.ledger
    )
    manifest = base.manifest.model_copy(
        update={
            "episode_id": new(base.manifest.episode_id),
            "policy_doc_id": policy.doc_id,
        }
    )
    company = CleanCompany(
        manifest=manifest, policy=policy, invoices=(invoice,), payments=(payment,), ledger=ledger
    )
    metadata = GenerationMetadata(seed=seed, config_version=config_version, spec_version="1.0.0")
    return company, metadata


def clean_usd_company(seed: int) -> tuple[CleanCompany, GenerationMetadata]:
    """One USD invoice/settlement booked in KZT at 500.25, no realized FX gain."""
    base, metadata = seeded_clean_kzt(seed)
    fx = (
        FxRow(date="2026-11-03", source_currency="USD", target_currency="KZT", rate="500.25"),
        FxRow(date="2026-11-08", source_currency="USD", target_currency="KZT", rate="500.25"),
        FxRow(date="2026-11-09", source_currency="USD", target_currency="KZT", rate="501.25"),
        FxRow(date="2026-11-10", source_currency="USD", target_currency="KZT", rate="500.25"),
    )
    invoice = base.invoices[0].model_copy(
        update={
            "currency": "USD",
            "total_minor": 10001,
            "line_items": [
                base.invoices[0].line_items[0].model_copy(update={"amount_minor": 10001})
            ],
        }
    )
    payment = base.payments[0].model_copy(
        update={
            "currency": "USD",
            "amount_minor": 10001,
            "invoice_refs": [
                base.payments[0].invoice_refs[0].model_copy(update={"amount_minor": 10001})
            ],
        }
    )
    ledger = []
    for row in base.ledger:
        source_date = "2026-11-03" if row.role == "invoice_recognition" else "2026-11-10"
        ledger.append(
            row.model_copy(
                update={
                    "debit_minor": 5003000 if row.debit_minor else 0,
                    "credit_minor": 5003000 if row.credit_minor else 0,
                    "fx_date": source_date,
                    "fx_rate": "500.25",
                    "allocated_source_minor": 10001
                    if row.allocated_source_minor is not None
                    else None,
                }
            )
        )
    manifest = base.manifest.model_copy(update={"fx_count": len(fx)})
    company = base.model_copy(
        update={
            "manifest": manifest,
            "invoices": (invoice,),
            "payments": (payment,),
            "ledger": tuple(ledger),
            "fx": fx,
        }
    )
    return company, metadata
