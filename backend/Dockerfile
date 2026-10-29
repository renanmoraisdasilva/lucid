# Backend image for the full-stack Compose profile.
# Development runs on the host with uv; this exists to prove the app starts from
# documented steps alone (spec acceptance criterion).

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /uvx /bin/

COPY pyproject.toml uv.lock alembic.ini ./
COPY migrations ./migrations
COPY src ./src
COPY prompts ./prompts

RUN uv sync --frozen --no-dev

EXPOSE 8000

# Local full-stack path: apply migrations, then serve. This is a development
# convenience, not a production migration strategy.
CMD ["sh", "-c", "uv run --no-dev alembic upgrade head && uv run --no-dev uvicorn lucid.main:app --host 0.0.0.0 --port 8000"]
