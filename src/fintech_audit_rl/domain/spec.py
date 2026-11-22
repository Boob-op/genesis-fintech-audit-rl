"""Load the single versioned financial contract without copying its rules."""

import json
from pathlib import Path

SPEC_PATH = Path(__file__).resolve().parents[3] / "docs/error_spec.json"
REQUIRED = {
    "type",
    "version",
    "definition",
    "amount_semantics",
    "currency_rule",
    "affected_ids_rule",
    "evidence_sets",
    "tolerance_minor",
}


def load_error_spec(path: Path = SPEC_PATH) -> dict:
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("spec_version") != "1.0.0":
        raise ValueError("unsupported error specification")
    errors = spec.get("errors")
    if not isinstance(errors, list) or len(errors) != 4:
        raise ValueError("exactly four error passports required")
    if any(not isinstance(item, dict) or not REQUIRED <= item.keys() for item in errors):
        raise ValueError("incomplete error passport")
    types = [item["type"] for item in errors]
    if len(set(types)) != 4:
        raise ValueError("duplicate error type")
    if not isinstance(spec.get("interactions"), list) or len(spec["interactions"]) != 2:
        raise ValueError("exactly two interactions required")
    return spec
