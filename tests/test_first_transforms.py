from fintech_audit_rl.benchmark.transforms import rename_ids, shuffle_ledger
from fintech_audit_rl.errors.duplicate_invoice import duplicate_invoice_recognition
from fintech_audit_rl.generator.company import seeded_clean_kzt
from fintech_audit_rl.runner.supervisor import run_first_episode
from fintech_audit_rl.validation.financial import clean_kzt_errors


def test_rename_updates_every_reference_and_keeps_clean_history():
    clean, _ = seeded_clean_kzt(61)
    renamed = rename_ids(clean)
    assert renamed.manifest.episode_id != clean.manifest.episode_id
    assert renamed.policy.doc_id == renamed.manifest.policy_doc_id
    assert renamed.invoices[0].invoice_id == renamed.payments[0].invoice_refs[0].invoice_id
    assert not clean_kzt_errors(
        renamed.manifest, renamed.policy, renamed.invoices, renamed.payments, renamed.ledger
    )


def test_shuffle_and_rename_keep_oracle_quality_and_reward():
    original = run_first_episode(62)
    for transformed in (
        run_first_episode(62, transform="rename"),
        run_first_episode(62, transform="shuffle"),
    ):
        assert transformed.score.metrics.f1 == original.score.metrics.f1 == 1
        assert transformed.score.reward == original.score.reward
        assert transformed.steps == original.steps
    clean, _ = seeded_clean_kzt(62)
    assert {row.row_id for row in shuffle_ledger(clean).ledger} == {
        row.row_id for row in clean.ledger
    }


def test_closed_trace_has_no_private_issue_or_seed_values():
    run = run_first_episode(63, closed=True)
    clean, metadata = seeded_clean_kzt(63)
    _, private_event = duplicate_invoice_recognition(clean, clean.invoices[0].invoice_id)
    public_values = str(run.trajectory)
    assert "seed" not in public_values
    assert "provenance" not in public_values
    assert "truth" not in public_values
    assert private_event.event_id not in public_values
    assert metadata.seed not in [item["reward"] for item in run.trajectory]
    assert clean.manifest.episode_id in public_values
