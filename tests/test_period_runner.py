from fintech_audit_rl.runner.supervisor import run_first_episode


def test_worker_detects_period_cutoff_without_truth_access():
    run = run_first_episode(133, duplicate=False, period_error=True)
    assert run.worker_exit_code == 0
    assert run.score.metrics.tp == 1
    assert run.score.metrics.f1 == 1
    assert run.score.reward < 1
