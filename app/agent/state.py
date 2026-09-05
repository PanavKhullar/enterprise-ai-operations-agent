import operator
from typing import Annotated, TypedDict


class AgentState(TypedDict):

    thread_id: str

    question: str

    investigation_plan: list[str]

    hypotheses: list[str]

    current_step: int

    evidence: list[dict]

    analysis: str

    confidence: float

    hypothesis_evaluations: list[dict]

    citations: list[dict]

    recommendation: str

    approved: bool

    action_name: str

    action_params: dict

    action_result: dict

    # Per-node timing entries ({"node": str, "duration_ms": float}),
    # appended (not overwritten) by each node via the `timed_node`
    # decorator, so the full per-node latency breakdown for a run
    # accumulates across the graph traversal.
    node_timings: Annotated[list[dict], operator.add]