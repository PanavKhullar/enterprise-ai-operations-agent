from typing import TypedDict


class AgentState(TypedDict):

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