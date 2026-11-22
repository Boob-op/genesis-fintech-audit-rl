"""Deterministic public JSONL/CSV and private JSON serialization."""

import csv
import io
import json
from collections.abc import Iterable
from typing import TypeVar

from pydantic import BaseModel

from fintech_audit_rl.schemas.public import FxRow, LedgerRow

Model = TypeVar("Model", bound=BaseModel)


def json_record(model: BaseModel) -> str:
    return json.dumps(
        model.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def jsonl_records(models: Iterable[BaseModel]) -> str:
    return "".join(json_record(model) + "\n" for model in models)


def parse_jsonl(content: str, model_type: type[Model]) -> list[Model]:
    return [model_type.model_validate_json(line) for line in content.splitlines() if line]


def csv_records(models: Iterable[LedgerRow] | Iterable[FxRow], model_type: type[Model]) -> str:
    rows = [model.model_dump(mode="json") for model in models]
    fields = list(model_type.model_fields)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def parse_csv(content: str, model_type: type[Model]) -> list[Model]:
    reader = csv.DictReader(io.StringIO(content, newline=""))
    if reader.fieldnames != list(model_type.model_fields):
        raise ValueError("unexpected CSV columns")
    result = []
    for row in reader:
        if None in row:
            raise ValueError("extra CSV columns")
        values = {key: value if value != "" else None for key, value in row.items()}
        if model_type is LedgerRow:
            for key in ("debit_minor", "credit_minor", "allocated_source_minor"):
                if values[key] is not None:
                    raw = values[key]
                    if not raw.isascii() or not raw.isdecimal():
                        raise ValueError(f"invalid integer in {key}")
                    values[key] = int(raw)
        result.append(model_type.model_validate_json(json.dumps(values)))
    return result
