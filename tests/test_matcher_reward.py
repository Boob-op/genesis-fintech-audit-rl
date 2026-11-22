from decimal import Decimal

from fintech_audit_rl.errors.duplicate_invoice import duplicate_invoice_recognition
from fintech_audit_rl.evaluation.matcher import match_count
from fintech_audit_rl.evaluation.metrics import metrics
from fintech_audit_rl.evaluation.oracle import oracle_submit
from fintech_audit_rl.evaluation.reward import terminal_reward
from fintech_audit_rl.generator.company import seeded_clean_kzt
from fintech_audit_rl.generator.truth import duplicate_truth


def fixture():
    clean, _ = seeded_clean_kzt(19)
    changed, event = duplicate_invoice_recognition(clean, clean.invoices[0].invoice_id)
    truth = duplicate_truth(changed, event)
    finding = oracle_submit(changed.manifest, [truth]).findings[0]
    public = {changed.policy.doc_id}
    public.update(row.row_id for row in changed.ledger)
    public.update(doc.doc_id for doc in (*changed.invoices, *changed.payments))
    return truth, finding, public


def test_manual_match_and_reward_cases():
    issue, good, public = fixture()
    assert match_count([good], [issue], public) == 1
    assert metrics(1, 1, 1).f1 == 1
    assert terminal_reward(Decimal(1), 4) == Decimal("0.992")
    assert metrics(0, 0, 1).fn == 1
    assert terminal_reward(metrics(0, 0, 1).f1, 0) == -1
    assert metrics(0, 0, 0).f1 == 1
    assert metrics(0, 1, 0).f1 == 0
    assert terminal_reward(Decimal(1), 100) == Decimal("0.800")


def test_duplicate_finding_is_fp_and_order_does_not_increase_tp():
    issue, good, public = fixture()
    assert match_count([good, good], [issue], public) == 1
    scored = metrics(1, 2, 1)
    assert (scored.tp, scored.fp, scored.fn) == (1, 1, 0)
    assert scored.f1 == Decimal(2) / 3
    assert match_count([good, good], [issue], public) == match_count(
        list(reversed([good, good])), [issue], public
    )


def test_wrong_amount_currency_and_evidence_do_not_match():
    issue, good, public = fixture()
    wrong = [
        good.model_copy(update={"claimed_amount_minor": good.claimed_amount_minor + 1}),
        good.model_copy(update={"currency": "USD"}),
        good.model_copy(update={"evidence_ids": good.evidence_ids[:-1]}),
        good.model_copy(update={"evidence_ids": ["private-guess", *good.evidence_ids]}),
        good.model_copy(update={"affected_ids": [*good.affected_ids, "extra"]}),
    ]
    assert all(match_count([finding], [issue], public) == 0 for finding in wrong)


def test_extra_known_evidence_is_allowed_but_missing_full_set_is_not():
    issue, good, public = fixture()
    extra = next(item for item in public if item not in good.evidence_ids)
    assert (
        match_count(
            [good.model_copy(update={"evidence_ids": [*good.evidence_ids, extra]})], [issue], public
        )
        == 1
    )


def test_explicit_tolerance_after_integer_rounding():
    issue, good, public = fixture()
    near = good.model_copy(update={"claimed_amount_minor": good.claimed_amount_minor + 1})
    assert match_count([near], [issue], public, 0) == 0
    assert match_count([near], [issue], public, 1) == 1
