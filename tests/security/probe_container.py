"""Run inside an isolated worker container in CI; exit nonzero on access."""

import socket
from pathlib import Path


def denied(action):
    try:
        action()
    except (OSError, PermissionError):
        return True
    return False


def network_attempt():
    with socket.socket() as connection:
        connection.settimeout(1)
        connection.connect(("1.1.1.1", 80))


assert denied(lambda: Path("/app/private/marker").read_text())
assert denied(lambda: Path("/app/forbidden-write").write_text("x"))
assert denied(network_attempt)
print("container read/write/network attempts denied")
