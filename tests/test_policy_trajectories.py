import json
import subprocess
import sys

from fintech_audit_rl.reporting.trajectory import write_trajectory
from fintech_audit_rl.runner.supervisor import run_first_episode


def test_reconciliation_beats_flag_all_and_trajectory_has_no_truth(tmp_path):
    good = run_first_episode(51)
    attack = run_first_episode(51, policy="flag_all")
    assert good.score.metrics.f1 == 1
    assert attack.score.metrics.f1 == 0
    assert attack.score.metrics.fp > 0
    assert good.score.reward > attack.score.reward
    path = tmp_path / "trajectories.jsonl"
    write_trajectory(path, good.trajectory)
    entries = [json.loads(line) for line in path.read_text("utf-8").splitlines()]
    assert len(entries) == good.steps
    for entry in entries:
        assert set(entry) == {
            "episode_id",
            "step",
            "action",
            "observation",
            "reward",
            "terminated",
            "truncated",
        }
        assert "truth" not in json.dumps(entry)
        assert "provenance" not in json.dumps(entry)


def test_closed_trajectory_records_visible_placeholder_only(tmp_path):
    run = run_first_episode(52, closed=True)
    assert run.score.reward > 0
    assert run.trajectory[-1]["reward"] == 0
    path = tmp_path / "closed.jsonl"
    write_trajectory(path, run.trajectory)
    assert json.loads(path.read_text("utf-8").splitlines()[-1])["reward"] == 0


def test_demo_command_saves_first_trajectory(tmp_path):
    path = tmp_path / "demo.jsonl"
    process = subprocess.run(
        [sys.executable, "-m", "fintech_audit_rl", "demo", "--seed", "53", "--output", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(process.stdout)
    assert report["mode"] == "developer_subprocess_not_os_isolated"
    assert report["f1"] == "1"
    assert report["worker_exit_code"] == 0
    assert path.exists()
