from fintech_audit_rl.runner.supervisor import run_first_episode


def test_random_explorer_replays_and_finishes_with_public_actions():
    first = run_first_episode(91, policy="random_explorer", policy_seed=8)
    second = run_first_episode(91, policy="random_explorer", policy_seed=8)
    assert first == second
    assert first.worker_exit_code == 0
    assert first.steps == 10
    assert first.trajectory[-1]["terminated"]
    assert first.score.metrics.fn == 1
    assert all(
        item["action"]["type"] in {"list_records", "get_record", "calculator", "submit"}
        for item in first.trajectory
    )


def test_policy_seed_changes_exploration_without_changing_episode():
    first = run_first_episode(92, policy="random_explorer", policy_seed=1)
    second = run_first_episode(92, policy="random_explorer", policy_seed=2)
    assert first.trajectory[0] == second.trajectory[0]
    assert first.trajectory[1:-1] != second.trajectory[1:-1]
    assert first.score == second.score
