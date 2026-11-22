from decimal import Decimal
from itertools import permutations

import pytest

from fintech_audit_rl.errors.duplicate_invoice import duplicate_invoice_recognition
from fintech_audit_rl.evaluation.matcher import match_count
from fintech_audit_rl.evaluation.oracle import oracle_submit
from fintech_audit_rl.evaluation.service import Evaluator
from fintech_audit_rl.generator.company import seeded_clean_kzt
from fintech_audit_rl.generator.truth import duplicate_truth
from fintech_audit_rl.schemas.actions import Finding
from fintech_audit_rl.schemas.private import TruthIssue
from fintech_audit_rl.storage.public_store import PublicStore


def episode():
    clean, _ = seeded_clean_kzt(91)
    public, event = duplicate_invoice_recognition(clean, clean.invoices[0].invoice_id)
    truth = duplicate_truth(public, event)
    store = PublicStore(public)
    finding = oracle_submit(public.manifest, [truth]).findings[0]
    evaluator = Evaluator(public.manifest.episode_id, (truth,), store.public_ids)
    return public, truth, finding, store.public_ids, evaluator


def test_ambiguous_graph_uses_order_independent_maximum_matching():
    common = {
        "type": "duplicate_invoice",
        "affected_ids": ["row"],
        "expected_amount_minor": 100,
        "currency": "KZT",
    }
    issues = [
        TruthIssue(issue_id="issue-a", evidence_sets=[["a"]], **common),
        TruthIssue(issue_id="issue-b", evidence_sets=[["b"]], **common),
    ]
    flexible = Finding(
        type="duplicate_invoice",
        affected_ids=["row"],
        claimed_amount_minor=100,
        currency="KZT",
        evidence_ids=["a", "b"],
        explanation="Can match either issue.",
    )
    specific = flexible.model_copy(update={"evidence_ids": ["a"]})

    for answers in permutations([flexible, specific]):
        for targets in permutations(issues):
            assert match_count(answers, targets, {"row", "a", "b"}) == 2


def test_repeated_raw_ids_normalize_but_repeated_findings_are_false_positives():
    public, truth, good, public_ids, evaluator = episode()
    repeated_ids = good.model_copy(
        update={
            "affected_ids": [*good.affected_ids, good.affected_ids[0]],
            "evidence_ids": [*good.evidence_ids, good.evidence_ids[0]],
        }
    )
    assert match_count([repeated_ids], [truth], public_ids) == 1

    submission = {
        "episode_id": public.manifest.episode_id,
        "findings": [good.model_dump(mode="json")] * 30,
    }
    score = evaluator.score(submission, 0)
    assert (score.metrics.tp, score.metrics.fp, score.metrics.fn) == (1, 29, 0)
    assert score.metrics.f1 == Decimal(2) / 31


def test_over_limit_flag_all_and_malformed_envelopes_are_invalid():
    public, _, good, _, evaluator = episode()
    base = good.model_dump(mode="json")
    invalid_findings = [base] * 31
    cases = [
        {"episode_id": public.manifest.episode_id, "findings": invalid_findings},
        {"episode_id": "wrong-episode", "findings": []},
        {"episode_id": public.manifest.episode_id, "findings": [{**base, "type": "unknown"}]},
        {
            "episode_id": public.manifest.episode_id,
            "findings": [{**base, "claimed_amount_minor": True}],
        },
        {
            "episode_id": public.manifest.episode_id,
            "findings": [{**base, "evidence_ids": base["evidence_ids"] + ["x"] * 5}],
        },
        {
            "episode_id": public.manifest.episode_id,
            "findings": [{**base, "explanation": "x" * 1001}],
        },
        {
            "episode_id": public.manifest.episode_id,
            "findings": [{**base, "unexpected": "field"}],
        },
    ]
    for submission in cases:
        score = evaluator.score(submission, 0)
        assert score.invalid_submit
        assert score.metrics is None
        assert score.reward == -1


def test_valid_but_wrong_fields_are_fp_not_structural_errors():
    public, _, good, public_ids, evaluator = episode()
    extra_public = next(item for item in public_ids if item not in good.affected_ids)
    wrong_findings = [
        good.model_copy(update={"claimed_amount_minor": good.claimed_amount_minor + 1}),
        good.model_copy(update={"currency": "USD"}),
        good.model_copy(update={"evidence_ids": good.evidence_ids[:-1]}),
        good.model_copy(update={"evidence_ids": [*good.evidence_ids, "unknown-public-id"]}),
        good.model_copy(update={"affected_ids": [*good.affected_ids, extra_public]}),
    ]
    for wrong in wrong_findings:
        score = evaluator.score(
            {
                "episode_id": public.manifest.episode_id,
                "findings": [wrong.model_dump(mode="json")],
            },
            0,
        )
        assert not score.invalid_submit
        assert (score.metrics.tp, score.metrics.fp, score.metrics.fn) == (0, 1, 1)


def test_evaluator_rejects_duplicate_or_non_public_truth():
    public, truth, _, public_ids, _ = episode()
    duplicate_id = truth.model_copy(update={"issue_id": "other-id"})
    unknown = truth.model_copy(update={"affected_ids": ["private-row"]})

    with pytest.raises(ValueError, match="duplicate truth issue ID"):
        Evaluator(public.manifest.episode_id, (truth, truth), public_ids)
    with pytest.raises(ValueError, match="duplicate semantic truth issue"):
        Evaluator(public.manifest.episode_id, (truth, duplicate_id), public_ids)
    with pytest.raises(ValueError, match="non-public"):
        Evaluator(public.manifest.episode_id, (unknown,), public_ids)
