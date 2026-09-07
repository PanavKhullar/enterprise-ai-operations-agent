"""Celery tasks that run the LangGraph agent outside the request/response
cycle. See `app/celery_app.py` for the rationale.
"""

from langgraph.types import Command

from app.celery_app import celery_app
from app.agent.graph import agent


def _serialize_result(result: dict) -> dict:
    """
    Convert a raw `agent.invoke(...)` return value into a plain,
    JSON-serializable dict (Celery's JSON result backend can't store the
    LangGraph `Interrupt` objects `__interrupt__` normally holds).
    """

    if "__interrupt__" in result:
        return {"interrupt": result["__interrupt__"][0].value}

    return {
        "analysis": result.get("analysis"),
        "confidence": result.get("confidence"),
        "citations": result.get("citations"),
        "recommendation": result.get("recommendation"),
        "approved": result.get("approved"),
        "action_name": result.get("action_name"),
        "action_result": result.get("action_result"),
        "node_timings": result.get("node_timings"),
    }


@celery_app.task(name="run_investigation")
def run_investigation_task(thread_id: str, initial_state: dict) -> dict:
    """Run a brand-new investigation (planner through approval) in a worker."""

    config = {"configurable": {"thread_id": thread_id}}
    result = agent.invoke(initial_state, config=config)
    return _serialize_result(result)


@celery_app.task(name="resume_investigation")
def resume_investigation_task(thread_id: str, decision: dict) -> dict:
    """Resume a paused (awaiting-approval) investigation in a worker."""

    config = {"configurable": {"thread_id": thread_id}}
    result = agent.invoke(Command(resume=decision), config=config)
    return _serialize_result(result)
