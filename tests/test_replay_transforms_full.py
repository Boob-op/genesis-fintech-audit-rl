import pytest

from fintech_audit_rl.benchmark.transforms import rename_ids, shuffle_ledger
from fintech_audit_rl.errors.allocation import short_allocate
from fintech_audit_rl.errors.duplicate_invoice import duplicate_invoice_recognition
from fintech_audit_rl.errors.fx import wrong_receipt_fx
from fintech_audit_rl.errors.period import wrong_invoice_period
from fintech_audit_rl.evaluation.oracle import oracle_submit
from fintech_audit_rl.evaluation.service import Evaluator
from fintech_audit_rl.generator.company import (
    clean_distractor_company,
    clean_usd_company,
    seeded_clean_kzt,
)
from fintech_audit_rl.generator.truth import (
    allocation_truth,
    duplicate_truth,
    fx_truth,
    period_truth,
)
from fintech_audit_rl.runner.supervisor import run_first_episode
from fintech_audit_rl.storage.public_store import PublicStore

RUN_CASES = [
    {"duplicate": True},
    {"duplicate": False, "allocation_actual_minor": 40000},
    {"duplicate": False, "fx_case": True, "fx_error": True},
    {"duplicate": False, "period_error": True},
    {
        "duplicate": False,
        "fx_case": True,
        "fx_error": True,
        "allocation_actual_minor": 6000,
    },
    {"duplicate": True, "allocation_actual_minor": 40000},
    {"duplicate": False, "distractors": True},
    {"duplicate": True, "scale_pairs": 34},
]


@pytest.mark.parametrize("options", RUN_CASES)
def test_every_supported_case_replays_exactly(options):
    assert run_first_episode(201, **options) == run_first_episode(201, **options)


@pytest.mark.parametrize("options", RUN_CASES)
def test_every_supported_case_preserves_score_after_rename_and_shuffle(options):
    reference = run_first_episode(202, **options)
    for transform in ("rename", "shuffle"):
        moved = run_first_episode(202, transform=transform, **options)
        assert moved.score.metrics == reference.score.metrics
        assert moved.score.reward == reference.score.reward
        assert moved.steps == reference.steps


def _oracle_case(seed, name, transform):
    clean, _ = clean_usd_company(seed) if name == "fx_allocation" else seeded_clean_kzt(seed)
    if transform == "rename":
        clean = rename_ids(clean)
    public = clean
    issues = []
    if name in {"duplicate", "duplicate_allocation"}:
        public, event = duplicate_invoice_recognition(public, public.invoices[0].invoice_id)
        issues.append(duplicate_truth(public, event))
    if name in {"allocation", "duplicate_allocation", "fx_allocation"}:
        actual = 6000 if name == "fx_allocation" else 40000
        public, event = short_allocate(
            public, public.payments[0].payment_id, public.invoices[0].invoice_id, actual
        )
        issues.append(allocation_truth(public, event))
    if name in {"fx", "fx_allocation"}:
        if name == "fx":
            public, _ = clean_usd_company(seed)
            if transform == "rename":
                public = rename_ids(public)
        public, event = wrong_receipt_fx(public, public.payments[0].payment_id, "2026-11-09")
        issues.append(fx_truth(public, event))
    if name == "period":
        public, event = wrong_invoice_period(public, public.invoices[0].invoice_id)
        issues.append(period_truth(public, event))
    if transform == "shuffle":
        public = shuffle_ledger(public, seed)
    store = PublicStore(public)
    evaluator = Evaluator(public.manifest.episode_id, tuple(issues), store.public_ids)
    submission = oracle_submit(public.manifest, issues).model_dump(mode="json")
    return evaluator.score(submission, 7)


@pytest.mark.parametrize(
    "name", ["duplicate", "allocation", "fx", "period", "duplicate_allocation", "fx_allocation"]
)
def test_oracle_f1_and_reward_survive_all_transforms(name):
    reference = _oracle_case(203, name, "none")
    assert reference.metrics.f1 == 1
    for transform in ("rename", "shuffle"):
        moved = _oracle_case(203, name, transform)
        assert moved.metrics == reference.metrics
        assert moved.reward == reference.reward


def test_rename_updates_refund_reference_and_all_public_ids():
    company, _ = clean_distractor_company(204)
    renamed = rename_ids(company)
    old_ids = PublicStore(company).public_ids
    new_store = PublicStore(renamed)
    refund = next(payment for payment in renamed.payments if payment.kind == "refund")

    assert old_ids.isdisjoint(new_store.public_ids)
    assert refund.reverses_payment_id in {payment.payment_id for payment in renamed.payments}
