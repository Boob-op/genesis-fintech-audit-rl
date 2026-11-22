"""Strict submit envelope; scoring rules are implemented in M09 later."""

from pydantic import Field, model_validator

from fintech_audit_rl.schemas.private import ErrorType
from fintech_audit_rl.schemas.public import Currency, Id, Money, StrictModel


class Finding(StrictModel):
    type: ErrorType
    affected_ids: list[Id] = Field(min_length=1)
    claimed_amount_minor: Money
    currency: Currency
    evidence_ids: list[Id] = Field(min_length=1, max_length=10)
    explanation: str = Field(max_length=1000)


class Submit(StrictModel):
    episode_id: Id
    findings: list[Finding] = Field(max_length=30)

    @model_validator(mode="after")
    def raw_limits_already_checked(self):
        # Pydantic validates raw list lengths before a future matcher normalizes IDs.
        return self
