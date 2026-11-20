import json
from pathlib import Path

from fintech_audit_rl.benchmark.suites import (
    DEV,
    HOLDOUT,
    TRAIN,
    build_episode,
    export_suite,
    paired_configs,
)
from fintech_audit_rl.evaluation.oracle import oracle_submit
from fintech_audit_rl.evaluation.service import Evaluator
from fintech_audit_rl.schemas.public import FxRow, Invoice, LedgerRow, Manifest, Payment
from fintech_audit_rl.storage.codec import parse_csv
from fintech_audit_rl.storage.public_store import PublicStore


def _score_oracle(config):
    bundle = build_episode(config)
    store = PublicStore(bundle.public)
    evaluator = Evaluator(
        bundle.public.manifest.episode_id, tuple(bundle.private.truth), store.public_ids
    )
    submission = oracle_submit(bundle.public.manifest, bundle.private.truth).model_dump(mode="json")
    return bundle, evaluator.score(submission, 5)


def test_suite_sizes_separation_and_required_holdout_mix():
    assert (len(TRAIN), len(DEV), len(HOLDOUT), len(paired_configs())) == (10, 10, 20, 20)
    all_configs = (*TRAIN, *DEV, *HOLDOUT)
    assert len({config.name for config in all_configs}) == 40
    assert len({config.seed for config in all_configs}) == 40
    scored = [_score_oracle(config) for config in all_configs]
    built = [bundle for bundle, _ in scored]
    assert len({bundle.public.manifest.episode_id for bundle in built}) == 40
    assert all(score.metrics.f1 == 1 for _, score in scored)

    holdout_issue_counts = [len(bundle.private.truth) for bundle in built[20:]]
    assert holdout_issue_counts.count(0) == 5
    assert holdout_issue_counts.count(2) == 5


def test_open_suites_cover_clean_single_errors_interactions_and_scale():
    for configs in (TRAIN, DEV):
        bundles = [build_episode(config) for config in configs]
        issue_types = [{issue.type for issue in bundle.private.truth} for bundle in bundles]
        assert set().union(*issue_types) == {
            "duplicate_invoice",
            "partial_allocation",
            "fx_date_or_rate",
            "period_cutoff",
        }
        assert any(not types for types in issue_types)
        assert sum(len(types) == 2 for types in issue_types) == 2
        assert any(bundle.public.manifest.ledger_count >= 200 for bundle in bundles)


def test_twenty_paired_transform_checks_preserve_oracle_score():
    for original, transformed in paired_configs():
        original_bundle, original_score = _score_oracle(original)
        transformed_bundle, transformed_score = _score_oracle(transformed)
        assert original_score.metrics.f1 == transformed_score.metrics.f1 == 1
        assert original_score.reward == transformed_score.reward
        if (
            original_bundle.public.manifest.episode_id
            == transformed_bundle.public.manifest.episode_id
        ):
            assert [row.row_id for row in original_bundle.public.ledger] != [
                row.row_id for row in transformed_bundle.public.ledger
            ]


def test_open_suite_export_is_complete_and_deterministic(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_index = export_suite((*TRAIN, *DEV), first)
    second_index = export_suite((*TRAIN, *DEV), second)

    assert first_index == second_index
    assert json.loads((first / "index.json").read_text("utf-8")) == first_index
    assert sorted(path.relative_to(first) for path in first.rglob("*") if path.is_file()) == sorted(
        path.relative_to(second) for path in second.rglob("*") if path.is_file()
    )
    for item in first_index:
        root = first / item["split"] / item["episode_id"]
        assert {path.name for path in (root / "public").iterdir()} == {
            "manifest.json",
            "policy.json",
            "invoices.jsonl",
            "payments.jsonl",
            "ledger.csv",
            "fx.csv",
        }
        assert {path.name for path in (root / "private").iterdir()} == {
            "truth.json",
            "provenance.json",
            "generation.json",
        }
        manifest = Manifest.model_validate_json((root / "public/manifest.json").read_text("utf-8"))
        invoices = [
            Invoice.model_validate_json(line)
            for line in (root / "public/invoices.jsonl").read_text("utf-8").splitlines()
        ]
        payments = [
            Payment.model_validate_json(line)
            for line in (root / "public/payments.jsonl").read_text("utf-8").splitlines()
        ]
        ledger = parse_csv((root / "public/ledger.csv").read_text("utf-8"), LedgerRow)
        fx = parse_csv((root / "public/fx.csv").read_text("utf-8"), FxRow)
        assert (len(ledger), len(invoices), len(payments), len(fx)) == (
            manifest.ledger_count,
            manifest.invoice_count,
            manifest.payment_count,
            manifest.fx_count,
        )
        for relative in [path.relative_to(first) for path in root.rglob("*") if path.is_file()]:
            assert (first / relative).read_bytes() == (second / relative).read_bytes()


def test_checked_in_open_suite_matches_current_builder(tmp_path):
    generated = tmp_path / "generated"
    export_suite((*TRAIN, *DEV), generated)
    checked_in = Path(__file__).resolve().parents[1] / "episodes"
    generated_files = sorted(
        path.relative_to(generated) for path in generated.rglob("*") if path.is_file()
    )
    checked_files = sorted(
        path.relative_to(checked_in) for path in checked_in.rglob("*") if path.is_file()
    )
    assert checked_files == generated_files
    assert all(
        (checked_in / relative).read_bytes() == (generated / relative).read_bytes()
        for relative in generated_files
    )
