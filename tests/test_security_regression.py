import json

import pytest

from fintech_audit_rl.env.core import AuditEnv
from fintech_audit_rl.evaluation.service import Evaluator
from fintech_audit_rl.generator.company import clean_distractor_company
from fintech_audit_rl.runner.supervisor import run_first_episode
from fintech_audit_rl.storage.public_store import PublicStore

SCENARIOS = [
    {"duplicate": True},
    {"duplicate": False, "allocation_actual_minor": 40000},
    {"duplicate": False, "fx_case": True, "fx_error": True},
    {"duplicate": False, "period_error": True},
    {
        "duplicate": False,
        "fx_case": True,
        "fx_error": True,
        "allocation_actual_minor": 6000,
    },
    {"duplicate": True, "allocation_actual_minor": 40000},
    {"duplicate": False, "distractors": True},
    {"duplicate": True, "scale_pairs": 34},
]


@pytest.mark.parametrize("options", SCENARIOS)
def test_closed_trajectories_expose_only_public_contract(options):
    result = run_first_episode(211, closed=True, **options)
    serialized = json.dumps(result.trajectory, separators=(",", ":")).lower()

    for forbidden in ("truth", "provenance", "generation", "error_plan", "private", "seed"):
        assert forbidden not in serialized
    assert all(entry["reward"] == 0 for entry in result.trajectory)
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
        for entry in result.trajectory
    )


def test_invalid_queries_do_not_echo_paths_or_secret_values():
    company, _ = clean_distractor_company(212)
    store = PublicStore(company)
    evaluator = Evaluator(company.manifest.episode_id, (), store.public_ids)
    env = AuditEnv(store, evaluator.score, evaluator.empty_score, closed=True)
    env.reset()
    attacks = [
        {"type": "get_document", "doc_id": "C:\\private\\truth.json"},
        {
            "type": "list_records",
            "table": "ledger",
            "cursor": "../../private/provenance",
            "limit": 50,
        },
        {"type": "calculator", "expression": "__import__('os').environ"},
        {"type": "get_record", "table": "ledger", "id": "secret-marker"},
    ]
    for remaining, action in zip(range(99, 95, -1), attacks, strict=True):
        observation, reward, terminated, truncated, info = env.step(action)
        assert observation == {"error": "invalid_query", "remaining_steps": remaining}
        assert (reward, terminated, truncated, info) == (0, False, False, {})
