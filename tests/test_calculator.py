import pytest

from fintech_audit_rl.env.calculator import calculate
from fintech_audit_rl.env.core import AuditEnv
from fintech_audit_rl.evaluation.service import Evaluator
from fintech_audit_rl.generator.company import seeded_clean_kzt
from fintech_audit_rl.storage.public_store import PublicStore


def test_exact_decimal_arithmetic_and_restrictions():
    assert calculate("0.1 + 0.2") == "0.3"
    assert calculate("(10001 * 500.25) - (10001 * 501.25)") == "-10001"
    assert calculate("1 / 4") == "0.25"
    for expression in (
        "__import__('os')",
        "open('x')",
        "x",
        "1 ** 1000",
        "1 / 0",
        "[1]",
        "True",
        "1e309",
        "9" * 129,
    ):
        with pytest.raises(ValueError):
            calculate(expression)


def test_calculator_action_consumes_step_and_returns_only_result():
    company, _ = seeded_clean_kzt(71)
    store = PublicStore(company)
    evaluator = Evaluator(company.manifest.episode_id, (), store.public_ids)
    env = AuditEnv(store, evaluator.score, evaluator.empty_score)
    env.reset()
    observation, reward, terminated, truncated, info = env.step(
        {"type": "calculator", "expression": "0.1 + 0.2"}
    )
    assert observation == {"result": "0.3", "remaining_steps": 99}
    assert (reward, terminated, truncated, info) == (0, False, False, {})
