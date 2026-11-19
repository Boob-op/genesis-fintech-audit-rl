"""B00.2 document acceptance, not a production loader or financial validator."""

import json
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

import pytest

SPEC = json.loads((Path(__file__).parents[1] / "docs/error_spec.json").read_text("utf-8"))
ERRORS = {item["type"]: item for item in SPEC["errors"]}


def test_passports_and_interactions_are_complete():
    assert SPEC["spec_version"] == "1.0.0"
    assert len(SPEC["errors"]) == len(ERRORS) == 4
    assert set(ERRORS) == {
        "duplicate_invoice",
        "partial_allocation",
        "fx_date_or_rate",
        "period_cutoff",
    }
    required = {
        "version",
        "definition",
        "correct_scenario",
        "preconditions",
        "mutation",
        "amount_semantics",
        "currency_rule",
        "affected_ids_rule",
        "evidence_sets",
        "evidence_access",
        "tolerance_minor",
        "compatibility",
        "example",
        "clean_analogue",
    }
    for passport in ERRORS.values():
        assert required <= passport.keys()
        assert all(passport[key] for key in required - {"tolerance_minor"})
        assert type(passport["tolerance_minor"]) is int
        assert passport["tolerance_minor"] == 0
        example = passport["example"]
        assert type(example["expected_amount_minor"]) is int
        assert example["expected_amount_minor"] >= 0
        assert len(example["public_ids"]) == len(set(example["public_ids"]))
        assert set(example["affected_ids"]) <= set(example["evidence_ids"])
        assert set(example["evidence_ids"]) <= set(example["public_ids"])
        assert len(example["evidence_ids"]) <= 10
    assert len(SPEC["interactions"]) == 2
    for interaction in SPEC["interactions"]:
        for field in (
            "preconditions",
            "mutation_order",
            "manual_calculation",
            "independent_evidence",
            "no_double_counting",
            "masking_rule",
            "clean_analogue",
        ):
            assert interaction[field]
        assert len(interaction["expected_issues"]) == 2
        assert set(interaction["types"]) == {
            issue["type"] for issue in interaction["expected_issues"]
        }
        for issue in interaction["expected_issues"]:
            assert issue["type"] in ERRORS
            assert set(issue["affected_ids"]) <= set(issue["evidence_ids"])
            assert set(issue["evidence_ids"]) <= set(interaction["public_ids"])
            assert len(issue["evidence_ids"]) <= 10


def test_duplicate_manual_amount_counts_one_leg_per_entry():
    example = ERRORS["duplicate_invoice"]["example"]
    assert sum(example["recognized_debits_minor"]) - example["invoice_minor"] == 100000
    assert example["expected_amount_minor"] == 100000
    assert set(example["affected_ids"]) == {row for entry in example["entry_rows"] for row in entry}


def test_allocation_manual_amount_and_legal_partial_payment():
    passport = ERRORS["partial_allocation"]
    example = passport["example"]
    assert example["intended_minor"] - sum(example["allocated_minor"]) == 20000
    assert example["expected_amount_minor"] == 20000
    assert sum(ref["amount_minor"] for ref in example["invoice_refs"]) == 60000
    missing = passport["omission_example"]
    assert missing["intended_minor"] - sum(missing["allocated_minor"]) == 60000
    assert missing["expected_amount_minor"] == 60000
    assert set(missing["evidence_ids"]) == {"p1", "i1", "pol"}
    split = passport["split_payment_example"]
    assert sum(split["payments_minor"]) == split["invoice_minor"]
    assert split["instructions_minor"] == split["allocations_minor"]
    assert split["expected_issues"] == 0
    # Remaining debt and authorized advances are not an instruction shortfall.
    assert 100000 - 60000 == 40000
    assert 70000 - 60000 == 10000


def test_fx_manual_receipt_values():
    example = ERRORS["fx_date_or_rate"]["example"]
    correct = (Decimal(example["source_minor"]) * Decimal(example["correct_rate"])).quantize(
        Decimal(1), rounding=ROUND_HALF_EVEN
    )
    recorded = (Decimal(example["source_minor"]) * Decimal(example["recorded_rate"])).quantize(
        Decimal(1), rounding=ROUND_HALF_EVEN
    )
    assert correct == example["correct_base_minor"] == 5003000
    assert recorded == example["recorded_base_minor"] == 5013001
    assert abs(recorded - correct) == example["expected_amount_minor"] == 10001
    assert Decimal("500.25").quantize(Decimal(1)) == Decimal("500.26").quantize(Decimal(1))


@pytest.mark.parametrize("case", ERRORS["fx_date_or_rate"]["rounding_examples"])
def test_rounding_and_currency_exponents(case):
    value = (
        Decimal(case["source_minor"])
        * Decimal(case["rate"])
        * Decimal(10) ** (case["target_exponent"] - case["source_exponent"])
    )
    assert int(value.quantize(Decimal(1), rounding=ROUND_HALF_EVEN)) == case["expected_base_minor"]


@pytest.mark.parametrize("case", ERRORS["period_cutoff"]["boundary_examples"])
def test_period_boundaries_compare_instants(case):
    example = ERRORS["period_cutoff"]["example"]
    start = datetime.fromisoformat(example["period_start"])
    end = datetime.fromisoformat(example["period_end"])
    assert (start <= datetime.fromisoformat(case["instant"]) < end) is case["inside"]


def test_cutoff_manual_amount():
    example = ERRORS["period_cutoff"]["example"]
    assert datetime.fromisoformat(example["issued_at"]) == datetime.fromisoformat(
        example["period_end"]
    )
    assert (
        abs(int(example["recorded_in_target"]) - int(example["expected_in_target"]))
        * example["base_minor"]
        == example["expected_amount_minor"]
        == 75000
    )


def test_interaction_manual_amounts_do_not_add_balance_as_third_issue():
    foreign, duplicate = SPEC["interactions"]
    assert [
        (issue["expected_amount_minor"], issue["currency"]) for issue in foreign["expected_issues"]
    ] == [(10001 - 6000, "USD"), (5013001 - 5003000, "KZT")]
    assert 5013001 - 3001500 == 2011501
    assert [issue["expected_amount_minor"] for issue in duplicate["expected_issues"]] == [
        200000 - 100000,
        60000 - 40000,
    ]
    assert (200000 - 40000) - (100000 - 60000) == 120000
