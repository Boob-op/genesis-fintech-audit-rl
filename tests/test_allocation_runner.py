import pytest

from fintech_audit_rl.runner.supervisor import run_first_episode


@pytest.mark.parametrize("actual", [40000, 0])
def test_public_worker_detects_partial_and_missing_allocation(actual):
    run = run_first_episode(112, duplicate=False, allocation_actual_minor=actual)
    assert run.worker_exit_code == 0
    assert run.score.metrics.tp == 1
    assert run.score.metrics.f1 == 1


def test_first_two_types_can_coexist_without_double_counting():
    run = run_first_episode(113, duplicate=True, allocation_actual_minor=40000)
    assert run.worker_exit_code == 0
    assert run.score.metrics.tp == 2
    assert run.score.metrics.fp == run.score.metrics.fn == 0
    assert run.score.metrics.f1 == 1
