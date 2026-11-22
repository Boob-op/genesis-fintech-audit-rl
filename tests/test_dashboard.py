from fintech_audit_rl.dashboard import (
    ASSET_ROOT,
    build_dashboard_payload,
    metric_values,
    trajectory_label,
)


def test_dashboard_payload_shows_public_run_without_private_records() -> None:
    payload = build_dashboard_payload("duplicate", "reconciliation", 101)
    assert payload["score"]["f1"] == "1"
    assert payload["score"]["tp"] == 1
    assert payload["trajectory"][-1]["terminated"] is True
    assert set(payload).isdisjoint({"truth", "provenance", "generation"})
    serialized = str(payload["trajectory"])
    assert "truth" not in serialized
    assert "provenance" not in serialized


def test_dashboard_clean_and_false_positive_are_visible() -> None:
    clean = build_dashboard_payload("clean", "reconciliation", 102)
    false_positive = build_dashboard_payload("clean", "flag_all", 102)
    assert clean["score"]["f1"] == "1"
    assert false_positive["score"]["f1"] == "0"
    assert false_positive["score"]["fp"] > 0


def test_dashboard_assets_exist() -> None:
    for name in ("index.html", "styles.css", "app.js"):
        assert (ASSET_ROOT / name).is_file()


def test_desktop_presenters_use_dashboard_contract() -> None:
    payload = build_dashboard_payload("duplicate", "reconciliation", 103)
    assert metric_values(payload) == ("1", "0.990", "6", "1 / 0 / 0")
    assert trajectory_label(payload["trajectory"][-1]).endswith("[DONE]")
