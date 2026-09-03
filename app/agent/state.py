from typing import TypedDict


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