"""Celery tasks that run the LangGraph agent outside the request/response
cycle. See `app/celery_app.py` for the rationale.
"""

import logging
import time

from langgraph.types import Command

import app.telemetry as telemetry
from app.celery_app import celery_app
from app.agent.graph import agent
from app.telemetry import correlation_context, get_tracer
from app.excel_export import export_investigation_to_excel

tracer = get_tracer(__name__)
logger = logging.getLogger(__name__)


def _serialize_result(result: dict) -> dict:
    """
    Convert a raw `agent.invoke(...)` return value into a plain,
    JSON-serializable dict (Celery's JSON result backend can't store the
    LangGraph `Interrupt` objects `__interrupt__` normally holds).
    """

    if "__interrupt__" in result:
        return {
            "interrupt": result["__interrupt__"][0].value,
            "question": result.get("question"),
            "investigation_plan": result.get("investigation_plan"),
            "evidence": result.get("evidence"),
            "node_timings": result.get("node_timings"),
        }

    return {
        "question": result.get("question"),
        "investigation_plan": result.get("investigation_plan"),
        "evidence": result.get("evidence"),
        "analysis": result.get("analysis"),
        "confidence": result.get("confidence"),
        "citations": result.get("citations"),
        "recommendation": result.get("recommendation"),
        "approved": result.get("approved"),
        "action_name": result.get("action_name"),
        "action_result": result.get("action_result"),
        "node_timings": result.get("node_timings"),
    }


def _run_with_telemetry(task_name: str, thread_id: str, task_id: str, invoke_fn, benchmark_run_id: str = ""):
    start = time.perf_counter()
    with correlation_context(thread_id=thread_id, task_id=task_id, benchmark_run_id=benchmark_run_id):
        with tracer.start_as_current_span(f"celery.{task_name}") as span:
            span.set_attribute("thread_id", thread_id)
            try:
                result = invoke_fn()
            except Exception as exc:
                duration_ms = (time.perf_counter() - start) * 1000
                span.set_attribute("status", "error")
                span.record_exception(exc)
                telemetry.celery_task_counter.add(1, {"task": task_name, "status": "error"})
                telemetry.celery_task_duration.record(
                    duration_ms, {"task": task_name, "status": "error"}
                )
                telemetry.investigation_counter.add(1, {"status": "error"})
                telemetry.emit_benchmark_event(
                    "celery_task", task=task_name, status="error", duration_ms=duration_ms,
                    error_type=type(exc).__name__,
                )
                raise

            duration_ms = (time.perf_counter() - start) * 1000
            status = "interrupted" if "interrupt" in result else "ok"
            span.set_attribute("status", status)
            telemetry.celery_task_counter.add(1, {"task": task_name, "status": status})
            telemetry.celery_task_duration.record(
                duration_ms, {"task": task_name, "status": status}
            )
            telemetry.investigation_counter.add(1, {"status": status})
            telemetry.investigation_duration.record(duration_ms, {"status": status})
            telemetry.emit_benchmark_event(
                "celery_task", task=task_name, status=status, duration_ms=duration_ms
            )

            try:
                export_investigation_to_excel(thread_id, result)
            except Exception:
                logger.exception(
                    "Failed to export investigation thread_id=%s to Excel", thread_id
                )

            return result


@celery_app.task(name="run_investigation")
def run_investigation_task(thread_id: str, initial_state: dict) -> dict:
    """Run a brand-new investigation (planner through approval) in a worker."""

    config = {"configurable": {"thread_id": thread_id}}

    def _invoke():
        return _serialize_result(agent.invoke(initial_state, config=config))

    return _run_with_telemetry(
        "run_investigation", thread_id, run_investigation_task.request.id, _invoke,
        initial_state.get("benchmark_run_id", ""),
    )


@celery_app.task(name="resume_investigation")
def resume_investigation_task(thread_id: str, decision: dict, benchmark_run_id: str = "") -> dict:
    """Resume a paused (awaiting-approval) investigation in a worker."""

    config = {"configurable": {"thread_id": thread_id}}

    def _invoke():
        return _serialize_result(agent.invoke(Command(resume=decision), config=config))

    return _run_with_telemetry(
        "resume_investigation", thread_id, resume_investigation_task.request.id, _invoke,
        benchmark_run_id,
    )
