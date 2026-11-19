"""Consistent public ID rename and record shuffle for first-scenario tests."""

import json
import random

from fintech_audit_rl.generator.company import CleanCompany


def rename_ids(company: CleanCompany) -> CleanCompany:
    """Rename every public document, business, row, entry and entity reference."""
    fields = {
        "episode_id",
        "policy_doc_id",
        "doc_id",
        "invoice_id",
        "payment_id",
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
