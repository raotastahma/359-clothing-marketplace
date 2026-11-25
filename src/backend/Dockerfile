# Builds the backend API, worker, and beat images used by the deployment Compose files.
FROM public.ecr.aws/docker/library/python:3.12-slim AS base

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

RUN uv sync --frozen --no-dev

FROM base AS api
EXPOSE 8000
# Trust proxy headers only from FORWARDED_ALLOW_IPS, which Compose pins to nginx.
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers"]

FROM base AS worker
CMD ["uv", "run", "celery", "-A", "app.tasks.celery_app.celery_app", "worker", "--loglevel=info", "--concurrency=4", "-Q", "celery,email,delivery"]

FROM base AS beat
CMD ["uv", "run", "celery", "-A", "app.tasks.celery_app.celery_app", "beat", "--loglevel=info", "--scheduler", "celery.beat:PersistentScheduler"]
