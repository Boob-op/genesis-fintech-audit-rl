import json
from pathlib import Path

from fintech_audit_rl.benchmark.runner import ADAPTERS, run_adapter, run_benchmark, write_results
from fintech_audit_rl.benchmark.suites import DEV, TRAIN, build_episode


def test_four_adapters_share_the_same_episode_and_visibility_contract():
    config = TRAIN[6]
    results = [run_adapter(config, adapter, policy_seed=77) for adapter in ADAPTERS]

    assert {result.episode_id for result in results} == {results[0].episode_id}
    assert {result.expected_issues for result in results} == {2}
    assert [result.privileged for result in results] == [False, False, False, True]
    assert all(result.worker_exit_code == 0 for result in results[:3])
    assert results[-1].worker_exit_code is None
    assert results[0].f1 == results[-1].f1 == "1"
    assert results[1].fp > 0
    assert results[2].fn == 2


def test_benchmark_order_and_json_are_deterministic(tmp_path):
    configs = TRAIN[:2]
    first = run_benchmark(configs)
    second = run_benchmark(configs)
    assert first == second
    assert [result.adapter for result in first] == list(ADAPTERS) * 2

    path = tmp_path / "adapter_runs.json"
    write_results(first, path)
    raw = json.loads(path.read_text("utf-8"))
    assert len(raw) == 8
    assert all(
        set(item)
        == {
            "adapter",
            "privileged",
            "config_name",
            "split",
            "episode_id",
            "expected_issues",
            "tp",
            "fp",
            "fn",
            "precision",
            "recall",
            "f1",
            "reward",
            "steps",
            "worker_exit_code",
            "truncated",
            "elapsed_seconds",
            "peak_traced_bytes",
        }
        for item in raw
    )


def test_checked_in_benchmark_covers_every_open_config_and_adapter():
    root = Path(__file__).resolve().parents[1]
    raw = json.loads((root / "reports/adapter_runs.json").read_text("utf-8"))
    configs = (*TRAIN, *DEV)

    assert len(raw) == len(configs) * len(ADAPTERS) == 80
    assert {(item["config_name"], item["adapter"]) for item in raw} == {
        (config.name, adapter) for config in configs for adapter in ADAPTERS
    }
    episode_ids = {
        config.name: build_episode(config).public.manifest.episode_id for config in configs
    }
    assert all(item["episode_id"] == episode_ids[item["config_name"]] for item in raw)
    assert all(item["f1"] == "1" for item in raw if item["adapter"] in {"reconciliation", "oracle"})
    assert all(not item["privileged"] for item in raw if item["adapter"] != "oracle")
    assert all(item["privileged"] for item in raw if item["adapter"] == "oracle")
    assert all(item["elapsed_seconds"] > 0 for item in raw)
    assert all(item["peak_traced_bytes"] > 0 for item in raw)
