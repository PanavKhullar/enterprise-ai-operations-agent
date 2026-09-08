import logging
import time
import uuid
from typing import Any, Literal, Optional

from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from pydantic import BaseModel

import app.telemetry as telemetry
from app.celery_app import celery_app
from app.tasks import resume_investigation_task, run_investigation_task
from app.telemetry import (
    correlation_context,
    get_tracer,
    setup_logging,
    setup_metrics,
    setup_tracing,
)

setup_logging()
setup_tracing("ops-agent-api")
setup_metrics("ops-agent-api")

logger = logging.getLogger("ops_agent.api")
tracer = get_tracer(__name__)

app = FastAPI(title="Enterprise AI Operations Agent")
FastAPIInstrumentor.instrument_app(app)
RedisInstrumentor().instrument()
SQLAlchemyInstrumentor().instrument()


@app.middleware("http")
async def correlation_and_metrics_middleware(request: Request, call_next):
    """Assigns/propagates a request_id for structured logs and traces, and
    records API-level request count/latency/error metrics for every route."""

    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    start = time.perf_counter()

    with correlation_context(request_id=request_id):
        response = await call_next(request)

    duration_ms = (time.perf_counter() - start) * 1000
    attributes = {
        "path": request.url.path,
        "method": request.method,
        "status_code": response.status_code,
    }
    telemetry.api_request_counter.add(1, attributes)
    telemetry.api_request_duration.record(duration_ms, attributes)
    response.headers["x-request-id"] = request_id
    return response

# Maps thread_id -> latest Celery task_id for that investigation, so the
# status-poll endpoint knows which task to check.
#
# NOTE: in-memory only. This is a deliberate, documented limitation for
# now — it doesn't survive an API process restart, and won't work across
# multiple API instances behind a load balancer. A production multi-instance
# deployment would move this to Redis/Postgres alongside the LangGraph
# checkpoint (which already persists the actual investigation state).
_task_registry: dict[str, str] = {}


class InvestigateRequest(BaseModel):
    question: str


class DecisionRequest(BaseModel):
    approved: bool
    action: str = "no_action"
    params: dict = {}


class ApprovalRequest(BaseModel):
    """What a human operator needs to see to make a decision."""

    question: str
    analysis: str
    confidence: Optional[float] = None
    recommendation: str
    allowed_actions: list[str]


class InvestigationResponse(BaseModel):
    """Unified response shape for both endpoints.

    When `status == "processing"`, only `thread_id` and `status` are
    populated — the graph is still running in a Celery worker. When
    `status == "pending_approval"`, `approval_request` is also populated.
    When `status == "completed"`, the result fields are populated and
    `approval_request` is None.
    """

    thread_id: str
    status: Literal["processing", "pending_approval", "completed", "failed"]
    approval_request: Optional[ApprovalRequest] = None
    analysis: Optional[str] = None
    confidence: Optional[float] = None
    citations: Optional[list[dict[str, Any]]] = None
    recommendation: Optional[str] = None
    approved: Optional[bool] = None
    action_name: Optional[str] = None
    action_result: Optional[dict[str, Any]] = None
    node_timings: Optional[list[dict[str, Any]]] = None


class ErrorResponse(BaseModel):
    detail: str


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catch-all so an internal error (LLM failure, DB error, etc.) never
    leaks a raw traceback/stack trace to the client. The real error is
    logged server-side for debugging.
    """

    logger.exception("Unhandled error while processing %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            detail="An internal error occurred while processing the request."
        ).model_dump(),
    )


def _initial_state(thread_id: str, question: str) -> dict:
    return {
        "thread_id": thread_id,
        "question": question,
        "investigation_plan": [],
        "hypotheses": [],
        "current_step": 0,
        "evidence": [],
        "analysis": "",
        "confidence": 0.0,
        "hypothesis_evaluations": [],
        "citations": [],
        "recommendation": "",
        "approved": False,
        "action_name": "",
        "action_params": {},
        "action_result": {},
        "node_timings": [],
    }


def _format_task_result(thread_id: str, result: dict) -> InvestigationResponse:
    """Build a response from a completed task's serialized result dict
    (see `app.tasks._serialize_result`)."""

    if "interrupt" in result:
        return InvestigationResponse(
            thread_id=thread_id,
            status="pending_approval",
            approval_request=ApprovalRequest(**result["interrupt"]),
        )

    return InvestigationResponse(
        thread_id=thread_id,
        status="completed",
        analysis=result.get("analysis"),
        confidence=result.get("confidence"),
        citations=result.get("citations"),
        recommendation=result.get("recommendation"),
        approved=result.get("approved"),
        action_name=result.get("action_name"),
        action_result=result.get("action_result"),
        node_timings=result.get("node_timings"),
    )


def _poll_task(thread_id: str) -> InvestigationResponse:
    """Look up the latest Celery task for a thread_id and report its status."""

    task_id = _task_registry.get(thread_id)
    if task_id is None:
        raise HTTPException(
            status_code=404,
            detail=f"No investigation found for thread_id '{thread_id}'.",
        )

    task_result = AsyncResult(task_id, app=celery_app)

    if not task_result.ready():
        return InvestigationResponse(thread_id=thread_id, status="processing")

    if task_result.failed():
        logger.error(
            "Investigation task failed for thread_id=%s: %s",
            thread_id,
            task_result.result,
        )
        return InvestigationResponse(thread_id=thread_id, status="failed")

    return _format_task_result(thread_id, task_result.result)


@app.post(
    "/investigate",
    response_model=InvestigationResponse,
    responses={500: {"model": ErrorResponse}},
)
def investigate(request: InvestigateRequest):
    """
    Kick off a new investigation. Enqueues the full pipeline (planner
    through approval) onto a Celery worker and returns immediately with a
    `thread_id` — the caller polls `GET /investigate/{thread_id}` for the
    result instead of holding the HTTP connection open for the ~25-90s the
    graph run takes.
    """

    thread_id = str(uuid.uuid4())

    with correlation_context(thread_id=thread_id):
        with tracer.start_as_current_span("investigate.submit") as span:
            span.set_attribute("thread_id", thread_id)
            task = run_investigation_task.delay(
                thread_id, _initial_state(thread_id, request.question)
            )
            span.set_attribute("celery.task_id", task.id)
        _task_registry[thread_id] = task.id
        logger.info("event=investigation_submitted task_id=%s", task.id)

    return InvestigationResponse(thread_id=thread_id, status="processing")


@app.get(
    "/investigate/{thread_id}",
    response_model=InvestigationResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_investigation(thread_id: str):
    """Poll the status/result of a previously started investigation."""

    with correlation_context(thread_id=thread_id):
        return _poll_task(thread_id)


@app.post(
    "/investigate/{thread_id}/decision",
    response_model=InvestigationResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def decide(thread_id: str, request: DecisionRequest):
    """
    Resume a paused investigation with a human operator's decision on
    whether (and how) to act on the recommendation. Enqueues the resume
    onto a Celery worker and returns immediately; poll
    `GET /investigate/{thread_id}` for the final result.
    """

    with correlation_context(thread_id=thread_id):
        current = _poll_task(thread_id)
        if current.status != "pending_approval":
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Thread_id '{thread_id}' is not awaiting approval "
                    f"(current status: '{current.status}')."
                ),
            )

        decision = {
            "approved": request.approved,
            "action": request.action,
            "params": request.params,
        }

        task = resume_investigation_task.delay(thread_id, decision)
        _task_registry[thread_id] = task.id
        logger.info("event=investigation_resumed task_id=%s", task.id)

    return InvestigationResponse(thread_id=thread_id, status="processing")
