"""Evaluator-owned records; never serialize these into worker observations."""

from typing import Literal

from pydantic import Field, model_validator

from fintech_audit_rl.schemas.public import Currency, Id, Money, StrictModel

ErrorType = Literal["duplicate_invoice", "partial_allocation", "fx_date_or_rate", "period_cutoff"]


class TruthIssue(StrictModel):
    issue_id: Id
    type: ErrorType
    affected_ids: list[Id] = Field(min_length=1)
    expected_amount_minor: Money
    currency: Currency
    evidence_sets: list[list[Id]] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self):
        if len(set(self.affected_ids)) != len(self.affected_ids):
            raise ValueError("truth affected IDs must be unique")
        if any(not ids or len(ids) > 10 or len(set(ids)) != len(ids) for ids in self.evidence_sets):
            raise ValueError("invalid truth evidence set")
        return self


class ProvenanceEvent(StrictModel):
    event_id: Id
    type: ErrorType
    mutation: Id
    public_ids: list[Id]


class GenerationMetadata(StrictModel):
    seed: int = Field(strict=True)
    config_version: Id
    spec_version: Id


class PrivateBundle(StrictModel):
    truth: list[TruthIssue]
    provenance: list[ProvenanceEvent]
    generation: GenerationMetadata
