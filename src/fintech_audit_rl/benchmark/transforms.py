"""Consistent public ID rename and record shuffle for first-scenario tests."""

import json
import random

from fintech_audit_rl.generator.company import CleanCompany
from fintech_audit_rl.schemas.public import policy_timezone


def rename_ids(company: CleanCompany) -> CleanCompany:
    """Rename every public document, business, row, entry and entity reference."""
    fields = {
        "episode_id",
        "policy_doc_id",
        "doc_id",
        "invoice_id",
        "payment_id",
        "reverses_payment_id",
        "entity_id",
        "row_id",
        "entry_id",
    }
    raw = company.model_dump(mode="json")
    identifiers = set()

    def collect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in fields and isinstance(item, str):
                    identifiers.add(item)
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(raw)
    mapping = {old: f"renamed-{index:04d}" for index, old in enumerate(sorted(identifiers))}

    def replace(value):
        if isinstance(value, dict):
            return {
                key: mapping[item] if key in fields and isinstance(item, str) else replace(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [replace(item) for item in value]
        return value

    return CleanCompany.model_validate_json(json.dumps(replace(raw)))


def shuffle_ledger(company: CleanCompany, seed: int = 1) -> CleanCompany:
    rows = list(company.ledger)
    random.Random(seed).shuffle(rows)
    return company.model_copy(update={"ledger": tuple(rows)})


def change_timezone(company: CleanCompany, timezone_name: str) -> CleanCompany:
    """Move all displayed offsets while preserving every financial instant."""
    zone = policy_timezone(timezone_name)

    def moved(value):
        return value.astimezone(zone)

    policy = company.policy.model_copy(
        update={
            "timezone": timezone_name,
            "period_start": moved(company.policy.period_start),
            "period_end": moved(company.policy.period_end),
        }
    )
    manifest = company.manifest.model_copy(
        update={
            "timezone": timezone_name,
            "period_start": moved(company.manifest.period_start),
            "period_end": moved(company.manifest.period_end),
        }
    )
    invoices = tuple(
        invoice.model_copy(
            update={"issued_at": moved(invoice.issued_at), "due_at": moved(invoice.due_at)}
        )
        for invoice in company.invoices
    )
    payments = tuple(
        payment.model_copy(update={"timestamp": moved(payment.timestamp)})
        for payment in company.payments
    )
    ledger = tuple(
        row.model_copy(
            update={
                "timestamp": moved(row.timestamp),
                "effective_at": moved(row.effective_at),
                "reporting_period_start": moved(row.reporting_period_start),
                "reporting_period_end": moved(row.reporting_period_end),
            }
        )
        for row in company.ledger
    )
    return company.model_copy(
        update={
            "manifest": manifest,
            "policy": policy,
            "invoices": invoices,
            "payments": payments,
            "ledger": ledger,
        }
    )
