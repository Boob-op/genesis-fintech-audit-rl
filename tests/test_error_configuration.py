import pytest

from fintech_audit_rl.runner.supervisor import run_first_episode


@pytest.mark.parametrize(
    ("options", "expected_issues"),
    [
        ({"duplicate": False}, 0),
        ({"duplicate": True}, 1),
        ({"duplicate": False, "allocation_actual_minor": 40000}, 1),
        ({"duplicate": False, "fx_case": True}, 0),
        ({"duplicate": False, "fx_case": True, "fx_error": True}, 1),
        ({"duplicate": False, "period_error": True}, 1),
    ],
)
def test_each_type_switch_and_clean_variant(options, expected_issues):
    run = run_first_episode(141, **options)
    assert run.worker_exit_code == 0
    assert run.score.metrics.tp == expected_issues
    assert run.score.metrics.fp == run.score.metrics.fn == 0
    assert run.score.metrics.f1 == 1


@pytest.mark.parametrize(
    "options",
    [
        {"duplicate": False, "allocation_actual_minor": 0},
        {"duplicate": False, "fx_case": True, "fx_error": True},
        {"duplicate": False, "period_error": True},
    ],
)
def test_each_new_type_survives_rename_and_shuffle(options):
    original = run_first_episode(142, **options)
    renamed = run_first_episode(142, transform="rename", **options)
    shuffled = run_first_episode(142, transform="shuffle", **options)
    for candidate in (renamed, shuffled):
        assert candidate.score.metrics.f1 == original.score.metrics.f1 == 1
        assert candidate.score.reward == original.score.reward
        assert candidate.worker_exit_code == 0
