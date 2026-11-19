"""Write the agent-visible trajectory without evaluator diagnostics."""

import json
from collections.abc import Iterable
from pathlib import Path


def write_trajectory(path: Path, events: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for event in events:
            required = {
                "episode_id",
                "step",
                "action",
                "observation",
                "reward",
                "terminated",
                "truncated",
            }
            if set(event) != required:
                raise ValueError("unexpected trajectory fields")
            stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
