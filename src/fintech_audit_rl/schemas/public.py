"""Strict public episode records. Financial consistency is checked elsewhere."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Id = Annotated[str, StringConstraints(min_length=1)]
Money = Annotated[int, Field(strict=True, ge=0)]
PositiveMoney = Annotated[int, Field(strict=True, gt=0)]
Currency = Literal["KZT", "USD", "JPY"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def offset_time(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include an explicit offset")
    return value


def policy_timezone(name: str):
    if name == "UTC":
        return timezone.utc
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        if name == "Asia/Qyzylorda":
            # Windows Python may lack the IANA database. This fallback covers
            # the synthetic November 2026 fixture; historic dates need tzdata.
            return timezone(timedelta(hours=5), name)
        raise ValueError("unknown timezone") from None


class Manifest(StrictModel):
    schema_version: Id
    episode_id: Id
    base_currency: Currency
    period_start: datetime
    period_end: datetime
    timezone: Id
    ledger_count: Money
    invoice_count: Money
    payment_count: Money
    fx_count: Money
    policy_doc_id: Id
    rounding: Literal["ROUND_HALF_EVEN"]

    _start = field_validator("period_start")(offset_time)
    _end = field_validator("period_end")(offset_time)

    @model_validator(mode="after")
    def valid_period(self):
        if self.period_start >= self.period_end:
            raise ValueError("period_start must precede period_end")
        policy_timezone(self.timezone)
        return self


class LedgerRow(StrictModel):
    row_id: Id
    entry_id: Id
    timestamp: datetime
    effective_at: datetime
    account: Id
    debit_minor: Money
    credit_minor: Money
    currency: Currency
    entity_id: Id
    invoice_id: Id | None
    payment_id: Id | None
    role: Literal["invoice_recognition", "payment_receipt", "payment_allocation", "payment_refund"]
    reporting_period_start: datetime
    reporting_period_end: datetime
    fx_date: str | None
    fx_rate: str | None
    allocated_source_minor: Money | None

    _timestamps = field_validator(
        "timestamp", "effective_at", "reporting_period_start", "reporting_period_end"
    )(offset_time)

    @model_validator(mode="after")
    def valid_sides(self):
        if (self.debit_minor > 0) == (self.credit_minor > 0):
            raise ValueError("exactly one positive journal side required")
        if self.reporting_period_start >= self.reporting_period_end:
            raise ValueError("invalid reporting interval")
        if self.allocated_source_minor is not None and (
            self.role != "payment_allocation" or self.credit_minor == 0
        ):
            raise ValueError("allocated source amount belongs to allocation credit row")
        return self


class LineItem(StrictModel):
    description: Id
    amount_minor: PositiveMoney


class Invoice(StrictModel):
    doc_id: Id
    invoice_id: Id
    entity_id: Id
    issued_at: datetime
    due_at: datetime
    currency: Currency
    total_minor: PositiveMoney
    line_items: list[LineItem] = Field(min_length=1)

    _timestamps = field_validator("issued_at", "due_at")(offset_time)

    @model_validator(mode="after")
    def valid_total(self):
        if sum(item.amount_minor for item in self.line_items) != self.total_minor:
            raise ValueError("line items do not equal invoice total")
        if self.due_at < self.issued_at:
            raise ValueError("due date precedes issue date")
        return self


class InvoiceRef(StrictModel):
    invoice_id: Id
    amount_minor: PositiveMoney


class Payment(StrictModel):
    doc_id: Id
    payment_id: Id
    timestamp: datetime
    currency: Currency
    amount_minor: PositiveMoney
    invoice_refs: list[InvoiceRef]
    kind: Literal["receipt", "refund"] = "receipt"
    reverses_payment_id: Id | None = None

    _timestamp = field_validator("timestamp")(offset_time)

    @model_validator(mode="after")
    def valid_refs(self):
        if len({ref.invoice_id for ref in self.invoice_refs}) != len(self.invoice_refs):
            raise ValueError("duplicate invoice reference")
        if sum(ref.amount_minor for ref in self.invoice_refs) > self.amount_minor:
            raise ValueError("references exceed payment")
        if self.kind == "receipt" and self.reverses_payment_id is not None:
            raise ValueError("receipt cannot reverse another payment")
        if self.kind == "refund" and (self.reverses_payment_id is None or self.invoice_refs):
            raise ValueError("refund requires one reversed payment and no invoice references")
        return self


class FxRow(StrictModel):
    date: str
    source_currency: Currency
    target_currency: Currency
    rate: str

    @field_validator("date")
    @classmethod
    def valid_date(cls, value: str) -> str:
        from datetime import date

        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("date must be ISO calendar date")
        return value

    @field_validator("rate")
    @classmethod
    def valid_rate(cls, value: str) -> str:
        try:
            rate = Decimal(value)
        except InvalidOperation as error:
            raise ValueError("invalid decimal FX rate") from error
        if not rate.is_finite() or rate <= 0:
            raise ValueError("FX rate must be finite and positive")
        return value

    @model_validator(mode="after")
    def distinct_currencies(self):
        if self.source_currency == self.target_currency:
            raise ValueError("same-currency FX row is unnecessary")
        return self


def fx_evidence_id(episode_id: str, row: FxRow) -> str:
    """Opaque stable public index ID; FX CSV retains the organizer's four columns."""
    digest = sha256(
        f"{episode_id}:{row.date}:{row.source_currency}:{row.target_currency}".encode()
    ).hexdigest()
    return f"id-{digest[:32]}"


class Policy(StrictModel):
    doc_id: Id
    timezone: Id
    period_start: datetime
    period_end: datetime
    currency_exponents: dict[Currency, Annotated[int, Field(strict=True, ge=0, le=3)]]
    rounding: Literal["ROUND_HALF_EVEN"]
    invoice_recognition: Literal["issued_at"]
    payment_recognition: Literal["timestamp"]
    fx_date_rule: Literal["local_event_date"]
    allocation_rule: Literal["immediate_invoice_refs"]

    _start = field_validator("period_start")(offset_time)
    _end = field_validator("period_end")(offset_time)

    @model_validator(mode="after")
    def valid_period(self):
        if self.period_start >= self.period_end:
            raise ValueError("invalid policy period")
        policy_timezone(self.timezone)
        return self
