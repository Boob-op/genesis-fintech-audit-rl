from fintech_audit_rl.errors.duplicate_invoice import duplicate_invoice_recognition
from fintech_audit_rl.evaluation.oracle import oracle_submit
from fintech_audit_rl.generator.company import seeded_clean_kzt
from fintech_audit_rl.generator.truth import duplicate_truth
from fintech_audit_rl.schemas.actions import Submit


def test_oracle_builds_valid_duplicate_and_clean_envelopes():
    clean, _ = seeded_clean_kzt(13)
    changed, event = duplicate_invoice_recognition(clean, clean.invoices[0].invoice_id)
    truth = duplicate_truth(changed, event)
    answer = oracle_submit(changed.manifest, [truth])
    assert Submit.model_validate_json(answer.model_dump_json()) == answer
    assert answer.episode_id == changed.manifest.episode_id
    assert len(answer.findings) == 1
    assert set(answer.findings[0].affected_ids) == set(truth.affected_ids)
    assert set(answer.findings[0].evidence_ids) == set(truth.evidence_sets[0])
    assert oracle_submit(clean.manifest, []).findings == []
