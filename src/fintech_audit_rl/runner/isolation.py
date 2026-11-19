"""Container launch options for a worker without host/private mounts."""


def isolated_worker_command(
    policy: str, policy_seed: int, image: str = "genesis-audit-dev"
) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "-i",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "64",
        "--cpus",
        "2",
        "--memory",
        "4g",
        "--user",
        "65534:65534",
        "--env",
        "PYTHONDONTWRITEBYTECODE=1",
        image,
        "python",
        "-m",
        "fintech_audit_rl.runner.worker",
        policy,
        str(policy_seed),
    ]
