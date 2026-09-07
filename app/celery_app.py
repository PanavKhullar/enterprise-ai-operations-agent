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
