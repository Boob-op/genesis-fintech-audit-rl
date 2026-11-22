import pytest

from fintech_audit_rl.errors.allocation import short_allocate
from fintech_audit_rl.errors.duplicate_invoice import duplicate_invoice_recognition
from fintech_audit_rl.errors.fx import wrong_receipt_fx
from fintech_audit_rl.generator.company import clean_usd_company, seeded_clean_kzt
from fintech_audit_rl.generator.truth import allocation_truth, duplicate_truth, fx_truth
from fintech_audit_rl.runner.supervisor import run_first_episode
from fintech_audit_rl.storage.public_store import PublicStore
from fintech_audit_rl.validation.evidence import (
    allocation_issues,
    duplicate_invoice_issues,
    receipt_fx_issues,
)


def test_foreign_allocation_and_fx_keep_two_independent_public_issues():
    clean, _ = clean_usd_company(151)
    short, allocation_event = short_allocate(
        clean, clean.payments[0].payment_id, clean.invoices[0].invoice_id, 6000
    )
    changed, fx_event = wrong_receipt_fx(short, short.payments[0].payment_id, "2026-11-09")
    allocation = allocation_truth(changed, allocation_event)
    fx = fx_truth(changed, fx_event)
    store = PublicStore(changed)
    fx_rows = tuple(store.list_records("fx", None, 50)["records"])
    public_allocation = allocation_issues(
        changed.policy, changed.invoices, changed.payments, changed.ledger
    )
    public_fx = receipt_fx_issues(
        changed.manifest, changed.policy, changed.payments, changed.ledger, fx_rows
    )
    assert (allocation.expected_amount_minor, allocation.currency) == (4001, "USD")
    assert (fx.expected_amount_minor, fx.currency) == (10001, "KZT")
    assert len(public_allocation) == len(public_fx) == 1
    assert set(allocation.affected_ids) == public_allocation[0].affected_ids
    assert set(fx.affected_ids) == public_fx[0].affected_ids
    assert set(allocation.evidence_sets[0]) == public_allocation[0].evidence_ids
    assert set(fx.evidence_sets[0]) == public_fx[0].evidence_ids
    assert (
        sum(row.credit_minor for row in changed.ledger if row.role == "payment_receipt") == 5013001
    )
    assert (
        sum(row.credit_minor for row in changed.ledger if row.role == "payment_allocation")
        == 3001500
    )
    assert (
        run_first_episode(
            151, duplicate=False, fx_case=True, fx_error=True, allocation_actual_minor=6000
        ).score.metrics.tp
        == 2
    )


def test_duplicate_and_allocation_are_two_issues_not_derived_balance():
    clean, _ = seeded_clean_kzt(152)
    duplicate, duplicate_event = duplicate_invoice_recognition(clean, clean.invoices[0].invoice_id)
    changed, allocation_event = short_allocate(
        duplicate, duplicate.payments[0].payment_id, duplicate.invoices[0].invoice_id, 40000
    )
    truth_duplicate = duplicate_truth(changed, duplicate_event)
    truth_allocation = allocation_truth(changed, allocation_event)
    assert [truth_duplicate.expected_amount_minor, truth_allocation.expected_amount_minor] == [
        100000,
        20000,
    ]
    public_duplicate = duplicate_invoice_issues(
        changed.manifest, changed.policy, changed.invoices, changed.ledger
    )
    public_allocation = allocation_issues(
        changed.policy, changed.invoices, changed.payments, changed.ledger
    )
    assert len(public_duplicate) == len(public_allocation) == 1
    assert public_duplicate[0].expected_amount_minor == 100000
    assert public_allocation[0].expected_amount_minor == 20000
    assert run_first_episode(152, allocation_actual_minor=40000).score.metrics.tp == 2


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ({"duplicate": False, "fx_case": True}, 0),
        ({"duplicate": False, "fx_case": True, "fx_error": True}, 1),
        ({"duplicate": False, "fx_case": True, "allocation_actual_minor": 6000}, 1),
        (
            {
                "duplicate": False,
                "fx_case": True,
                "fx_error": True,
                "allocation_actual_minor": 6000,
            },
            2,
        ),
        ({"duplicate": False}, 0),
        ({"duplicate": True}, 1),
        ({"duplicate": False, "allocation_actual_minor": 40000}, 1),
        ({"duplicate": True, "allocation_actual_minor": 40000}, 2),
    ],
)
def test_repairing_each_mutation_leaves_only_the_other_issue(options, expected):
    run = run_first_episode(153, **options)
    assert run.score.metrics.tp == expected
    assert run.score.metrics.fp == run.score.metrics.fn == 0


@pytest.mark.parametrize(
    "options",
    [
        {"duplicate": False, "fx_case": True, "fx_error": True, "allocation_actual_minor": 6000},
        {"duplicate": True, "allocation_actual_minor": 40000},
    ],
)
def test_interactions_survive_rename_and_shuffle(options):
    reference = run_first_episode(154, **options)
    assert reference.score.metrics.f1 == 1
    for transform in ("rename", "shuffle"):
        moved = run_first_episode(154, transform=transform, **options)
        assert moved.score.metrics.tp == 2
        assert moved.score.metrics.f1 == 1
        assert moved.score.reward == reference.score.reward
