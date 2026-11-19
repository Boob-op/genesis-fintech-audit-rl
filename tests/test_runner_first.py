from decimal import Decimal

from fintech_audit_rl.runner.supervisor import run_first_episode


def test_worker_uses_public_protocol_and_finds_duplicate():
    run = run_first_episode(101)
    assert run.worker_exit_code == 0
    assert run.steps == 6  # ledger, invoice, payment, invoice, FX, submit
    assert run.score.metrics.f1 == 1
    assert run.score.reward == Decimal("0.990")
    assert run.trajectory[-1]["terminated"]
    assert run.trajectory[-1]["reward"] == 0.99
    assert all("truth" not in str(item["observation"]) for item in run.trajectory)
    assert all("provenance" not in str(item["observation"]) for item in run.trajectory)


def test_clean_episode_empty_submit_and_closed_reward():
    run = run_first_episode(102, duplicate=False, closed=True)
    assert run.worker_exit_code == 0
    assert run.score.metrics.f1 == 1
    assert run.score.reward == Decimal("0.992")
    assert run.trajectory[-1]["reward"] == 0


def test_replay_same_seed_actions_and_rewards():
    first = run_first_episode(103)
    second = run_first_episode(103)
    assert first == second
