import json
from pathlib import Path

from fintech_audit_rl.benchmark.runner import AdapterResult
from fintech_audit_rl.reporting.summary import summarize


def _result(adapter, tp, fp, fn, f1, reward, steps, privileged=False):
    return AdapterResult(
        adapter=adapter,
        privileged=privileged,
        config_name="case",
        split="train",
        episode_id="episode",
        expected_issues=tp + fn,
        tp=tp,
        fp=fp,
        fn=fn,
        precision="0",
        recall="0",
        f1=f1,
        reward=reward,
        steps=steps,
        worker_exit_code=None if privileged else 0,
        truncated=False,
        elapsed_seconds=0.25,
        peak_traced_bytes=1000,
    )


def test_summary_recomputes_micro_and_mean_metrics():
    rows = summarize(
        (
            _result("policy", 1, 0, 0, "1", "0.9", 5),
            _result("policy", 0, 1, 1, "0", "-1", 7),
        )
    )
    assert rows == [
        {
            "adapter": "policy",
            "privileged": False,
            "runs": 2,
            "tp": 1,
            "fp": 1,
            "fn": 1,
            "micro_precision": "0.5",
            "micro_recall": "0.5",
            "micro_f1": "0.5",
            "mean_episode_f1": "0.5",
            "mean_reward": "-0.05",
            "mean_steps": "6",
            "total_elapsed_seconds": 0.5,
            "mean_elapsed_seconds": 0.25,
            "max_peak_traced_bytes": 1000,
        }
    ]


def test_checked_in_summary_and_trajectories_have_public_shape():
    root = Path(__file__).resolve().parents[1]
    summary = json.loads((root / "reports/benchmark_summary.json").read_text("utf-8"))
    assert {row["adapter"] for row in summary} == {
        "reconciliation",
        "flag_all",
        "random_explorer",
        "oracle",
    }
    entries = [
        json.loads(line)
        for line in (root / "reports/trajectories.jsonl").read_text("utf-8").splitlines()
    ]
    assert entries
    assert all(
        set(entry)
        == {
            "episode_id",
            "step",
            "action",
            "observation",
            "reward",
            "terminated",
            "truncated",
        }
        for entry in entries
    )
    serialized = json.dumps(entries).lower()
    assert all(word not in serialized for word in ("truth", "provenance", "generation", "seed"))
