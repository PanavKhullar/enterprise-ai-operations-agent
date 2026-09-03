import logging
import uuid
from typing import Any, Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from langgraph.types import Command
from pydantic import BaseModel

from app.agent.graph import agent

logger = logging.getLogger("ops_agent.api")

app = FastAPI(title="Enterprise AI Operations Agent")


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

    When `status == "pending_approval"`, only `thread_id`, `status`, and
    `approval_request` are populated. When `status == "completed"`, the
    result fields are populated and `approval_request` is None.
    """

    thread_id: str
    status: Literal["pending_approval", "completed"]
    approval_request: Optional[ApprovalRequest] = None
    analysis: Optional[str] = None
    confidence: Optional[float] = None
    citations: Optional[list[dict[str, Any]]] = None
    recommendation: Optional[str] = None
    approved: Optional[bool] = None
    action_name: Optional[str] = None
    action_result: Optional[dict[str, Any]] = None


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
    }


def _format_response(thread_id: str, result: dict) -> InvestigationResponse:
    if "__interrupt__" in result:
        return InvestigationResponse(
            thread_id=thread_id,
            status="pending_approval",
            approval_request=ApprovalRequest(**result["__interrupt__"][0].value),
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
    )


@app.post(
    "/investigate",
    response_model=InvestigationResponse,
    responses={500: {"model": ErrorResponse}},
)
def investigate(request: InvestigateRequest):
    """
    Kick off a new investigation. Runs the full pipeline (planner through
    recommender) and then pauses, awaiting human approval before any
    operational action is taken.
    """

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    result = agent.invoke(_initial_state(thread_id, request.question), config=config)

    return _format_response(thread_id, result)


@app.post(
    "/investigate/{thread_id}/decision",
    response_model=InvestigationResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def decide(thread_id: str, request: DecisionRequest):
    """
    Resume a paused investigation with a human operator's decision on
    whether (and how) to act on the recommendation.
    """

    config = {"configurable": {"thread_id": thread_id}}

    state = agent.get_state(config)
    if not state.next:
        raise HTTPException(
            status_code=404,
            detail=f"No pending approval found for thread_id '{thread_id}'.",
        )

    decision = {
        "approved": request.approved,
        "action": request.action,
        "params": request.params,
    }

    result = agent.invoke(Command(resume=decision), config=config)

    return _format_response(thread_id, result)
