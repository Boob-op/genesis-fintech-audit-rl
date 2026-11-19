"""Trusted evaluator; its truth is never part of environment observations."""

from dataclasses import dataclass
from decimal import Decimal

from fintech_audit_rl.evaluation.matcher import match_count
from fintech_audit_rl.evaluation.metrics import Metrics, metrics
from fintech_audit_rl.evaluation.reward import terminal_reward
from fintech_audit_rl.schemas.actions import Submit
from fintech_audit_rl.schemas.private import TruthIssue


@dataclass(frozen=True)
class Score:
    metrics: Metrics | None
    reward: Decimal
    invalid_submit: bool = False


class Evaluator:
    def __init__(self, episode_id: str, issues: tuple[TruthIssue, ...], public_ids: set[str]):
        self._episode_id = episode_id
        self._issues = issues
        self._public_ids = frozenset(public_ids)

    def score(self, submission: dict, inspection_steps: int) -> Score:
        try:
            answer = Submit.model_validate(submission)
            if answer.episode_id != self._episode_id:
                raise ValueError("wrong episode")
        except (ValueError, TypeError):
            return Score(metrics=None, reward=Decimal(-1), invalid_submit=True)
        tp = match_count(answer.findings, self._issues, set(self._public_ids))
        result = metrics(tp, len(answer.findings), len(self._issues))
        return Score(result, terminal_reward(result.f1, inspection_steps))

    def empty_score(self, inspection_steps: int) -> Score:
        result = metrics(0, 0, len(self._issues))
        return Score(result, terminal_reward(result.f1, inspection_steps))
