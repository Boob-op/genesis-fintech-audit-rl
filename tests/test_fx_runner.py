from fintech_audit_rl.runner.supervisor import run_first_episode


def test_fx_clean_and_error_worker_scoring():
    clean = run_first_episode(122, duplicate=False, fx_case=True)
    wrong = run_first_episode(122, duplicate=False, fx_case=True, fx_error=True)
    assert clean.score.metrics.f1 == 1
    assert wrong.score.metrics.tp == 1
    assert wrong.score.metrics.f1 == 1
    assert wrong.worker_exit_code == 0
    assert wrong.score.reward < 1  # inspection steps charged
