"""Minimal reset/step for the first duplicate-invoice episode."""

from collections.abc import Callable
from decimal import Decimal

from fintech_audit_rl.evaluation.service import Score
from fintech_audit_rl.storage.public_store import PublicStore


class AuditEnv:
    def __init__(
        self,
        store: PublicStore,
        score: Callable[[dict, int], Score],
        empty_score: Callable[[int], Score],
        closed: bool = False,
    ):
        self._store = store
        self._score = score
        self._empty_score = empty_score
        self._closed = closed
        self._steps = 0
        self._done = False
        self._ended_by_submit = False
        self.scored_result: Score | None = None

    def reset(self) -> tuple[dict, dict]:
        self._steps = 0
        self._done = False
        self._ended_by_submit = False
        self.scored_result = None
        observation = {
            "task": "Audit the public financial records and submit supported findings.",
            "manifest": self._store.manifest.model_dump(mode="json"),
            "policy": self._store.policy.model_dump(mode="json"),
            "remaining_steps": 100,
        }
        return observation, {"api_version": "1.0.0"}

    def step(self, action: dict) -> tuple[dict, Decimal, bool, bool, dict]:
        if self._done:
            return (
                {"error": "episode_closed", "remaining_steps": 100 - self._steps},
                Decimal(0),
                self._ended_by_submit,
                not self._ended_by_submit,
                {},
            )
        self._steps += 1
        remaining = 100 - self._steps
        if not isinstance(action, dict) or type(action.get("type")) is not str:
            observation = {"error": "invalid_action", "remaining_steps": remaining}
        elif action["type"] == "submit" and set(action) == {"type", "submission"}:
            self.scored_result = self._score(action.get("submission"), self._steps - 1)
            self._done = True
            self._ended_by_submit = True
            visible = Decimal(0) if self._closed else self.scored_result.reward
            status = "invalid_submit" if self.scored_result.invalid_submit else "submitted"
            return {"status": status, "remaining_steps": remaining}, visible, True, False, {}
        else:
            try:
                observation = self._read_action(action)
                observation["remaining_steps"] = remaining
            except (ValueError, TypeError, KeyError):
                observation = {"error": "invalid_query", "remaining_steps": remaining}
        if self._steps >= 100:
            self._done = True
            self.scored_result = self._empty_score(100)
            visible = Decimal(0) if self._closed else self.scored_result.reward
            return observation, visible, False, True, {}
        return observation, Decimal(0), False, False, {}

    def _read_action(self, action: dict) -> dict:
        kind = action["type"]
        if kind == "list_records" and set(action) == {"type", "table", "cursor", "limit"}:
            return self._store.list_records(action["table"], action["cursor"], action["limit"])
        if kind == "get_record" and set(action) == {"type", "table", "id"}:
            return {"record": self._store.get_record(action["table"], action["id"])}
        if kind == "get_document" and set(action) == {"type", "doc_id"}:
            return {"document": self._store.get_document(action["doc_id"])}
        raise ValueError("unknown action")
