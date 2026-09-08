"""Celery application for running the LangGraph agent in the background.

Reason: `agent.invoke(...)` for a full investigation takes ~25-90s. Running
it inline inside a FastAPI request handler ties up the HTTP connection for
that whole duration, which risks a client/proxy timeout (nginx/ALB commonly
default to 30-60s) even though the agent is still working fine server-side.
Celery + Redis decouples "accept the request" from "run the graph": the API
enqueues a task and returns immediately, and the client polls a status
endpoint instead of holding the connection open.
"""

import os

from celery import Celery
from celery.signals import setup_logging as celery_setup_logging_signal
from celery.signals import worker_init, worker_process_init
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

from app.telemetry import setup_logging, setup_metrics, setup_tracing

# Redis used as both the message broker (task queue) and the result
# backend (task status/return value storage). Overridable via env var so
# the docker-compose service name ("redis") can be used in containers
# while local dev defaults to localhost.
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "ops_agent",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Task results expire after an hour — long enough for a client to
    # poll for the outcome, short enough not to grow Redis unbounded.
    result_expires=3600,
    # A long-running LLM+DB investigation shouldn't be silently retried by
    # a worker restart mid-run; track failures explicitly instead.
    task_acks_late=False,
)


def _init_worker_telemetry(**kwargs):
    """Sets up structured logging + tracing + metrics before any task runs.

    Connected to both `worker_init` and `worker_process_init` because:
    - `worker_init` fires once in the main worker process for *every* pool
      type, including `--pool=solo` (which never spawns a separate child
      process, so `worker_process_init` alone would never fire there).
    - `worker_process_init` additionally fires in each forked child under
      the default `prefork` pool, where tasks actually execute.
    All setup_* functions are idempotent, so connecting both signals is
    safe and just guarantees at least one of them runs in the process
    that executes tasks.
    """

    setup_logging()
    setup_tracing("ops-agent-worker")
    setup_metrics("ops-agent-worker")
    CeleryInstrumentor().instrument()
    RedisInstrumentor().instrument()
    SQLAlchemyInstrumentor().instrument()


worker_init.connect(_init_worker_telemetry)
worker_process_init.connect(_init_worker_telemetry)


@celery_setup_logging_signal.connect
def _skip_celery_default_logging(**kwargs):
    """Merely having a receiver connected to this signal tells Celery to
    skip its own default logging configuration (which would otherwise
    reset the root logger's handlers to plain-text after our JSON
    formatter is installed by `_init_worker_telemetry`). The actual JSON
    logging setup happens in `_init_worker_telemetry` above."""
    setup_logging()
