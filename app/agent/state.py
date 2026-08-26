from typing import TypedDict, List, Dict, Any


class AgentState(TypedDict):

    # Original question from the user
    question: str

    # Investigation plan created by the agent
    investigation_plan: List[str]

    # Results returned by tools
    evidence: List[Dict[str, Any]]

    # Final root-cause analysis
    analysis: str

    # Recommended action
    recommendation: str

    # Human approval status
    approved: bool