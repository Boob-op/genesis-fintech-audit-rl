FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY . .
RUN uv sync --locked --dev
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "-m", "fintech_audit_rl", "verify"]
