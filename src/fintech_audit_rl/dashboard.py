"""Local, dependency-free dashboard for observing public audit runs."""

from __future__ import annotations

import json
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from fintech_audit_rl.benchmark.suites import EpisodeConfig, build_episode
from fintech_audit_rl.runner.supervisor import run_first_episode

ASSET_ROOT = Path(__file__).with_name("web")
SCENARIOS: dict[str, dict[str, Any]] = {
    "clean": {"duplicate": False},
    "duplicate": {"duplicate": True},
    "allocation": {"duplicate": False, "allocation_actual_minor": 40000},
    "fx": {"duplicate": False, "fx_case": True, "fx_error": True},
    "period": {"duplicate": False, "period_error": True},
    "allocation_fx": {
        "duplicate": False,
        "fx_case": True,
        "fx_error": True,
        "allocation_actual_minor": 6000,
    },
    "duplicate_allocation": {"duplicate": True, "allocation_actual_minor": 40000},
    "distractors": {"duplicate": False, "distractors": True},
}
POLICIES = {"reconciliation", "flag_all", "random_explorer"}


def metric_values(payload: dict[str, Any]) -> tuple[str, str, str, str]:
    score = payload["score"]
    return (
        score["f1"],
        score["reward"],
        str(score["steps"]),
        f"{score['tp']} / {score['fp']} / {score['fn']}",
    )


def trajectory_label(event: dict[str, Any]) -> str:
    action = event["action"].get("action", event["action"].get("type", "unknown"))
    state = "DONE" if event["terminated"] else "TRUNCATED" if event["truncated"] else "OK"
    return f"{event['step']:02d}   {action.replace('_', ' ')}   [{state}]"


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def build_dashboard_payload(
    scenario: str,
    policy: str,
    seed: int,
    policy_seed: int = 0,
) -> dict[str, Any]:
    if scenario not in SCENARIOS:
        raise ValueError("unknown scenario")
    if policy not in POLICIES:
        raise ValueError("unknown policy")
    if type(seed) is not int or not 0 <= seed <= 2_147_483_647:
        raise ValueError("seed must be a non-negative 32-bit integer")
    if type(policy_seed) is not int or not 0 <= policy_seed <= 2_147_483_647:
        raise ValueError("policy seed must be a non-negative 32-bit integer")

    options = SCENARIOS[scenario]
    config = EpisodeConfig(name="dashboard", split="demo", seed=seed, **options)
    bundle = build_episode(config)
    result = run_first_episode(seed, policy=policy, policy_seed=policy_seed, **options)
    metrics = result.score.metrics
    if metrics is None:
        raise RuntimeError("dashboard run ended with an invalid submission")
    public = bundle.public
    return {
        "scenario": scenario,
        "policy": policy,
        "config": asdict(config),
        "manifest": _jsonable(public.manifest),
        "policy_document": _jsonable(public.policy),
        "documents": {
            "invoices": [_jsonable(item) for item in public.invoices],
            "payments": [_jsonable(item) for item in public.payments],
            "fx": [_jsonable(item) for item in public.fx],
        },
        "ledger": [_jsonable(item) for item in public.ledger],
        "trajectory": list(result.trajectory),
        "score": {
            "tp": metrics.tp,
            "fp": metrics.fp,
            "fn": metrics.fn,
            "precision": str(metrics.precision),
            "recall": str(metrics.recall),
            "f1": str(metrics.f1),
            "reward": str(result.score.reward),
            "steps": result.steps,
            "truncated": result.truncated,
            "worker_exit_code": result.worker_exit_code,
        },
    }


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "GenesisDashboard/1.0"

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(self, status: HTTPStatus, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        self._send(
            status,
            "application/json; charset=utf-8",
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )

    def do_GET(self) -> None:  # noqa: N802
        routes = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
        }
        if self.path == "/api/health":
            self._json(HTTPStatus.OK, {"status": "ok", "scenarios": list(SCENARIOS)})
            return
        route = routes.get(self.path)
        if route is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        name, content_type = route
        self._send(HTTPStatus.OK, content_type, (ASSET_ROOT / name).read_bytes())

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/run":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                raise ValueError("invalid request size")
            request = json.loads(self.rfile.read(length))
            payload = build_dashboard_payload(
                request.get("scenario", "duplicate"),
                request.get("policy", "reconciliation"),
                request.get("seed", 101),
                request.get("policy_seed", 0),
            )
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        except Exception:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "run failed"})
            return
        self._json(HTTPStatus.OK, payload)


def serve_dashboard(host: str = "127.0.0.1", port: int = 8765) -> None:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("dashboard must bind to localhost")
    if not 1024 <= port <= 65535:
        raise ValueError("port outside allowed range")
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"GENESIS dashboard: http://{host}:{port}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
