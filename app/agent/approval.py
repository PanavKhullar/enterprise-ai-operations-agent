from langgraph.types import interrupt

from app.agent.actions import ALLOWED_ACTIONS


def approval_node(state):
    """
    Pause the graph and surface the recommendation to a human operator.

    This node blocks the graph via `interrupt()` until the caller resumes
    execution with `Command(resume={"approved": bool, "action": str,
    "params": dict})`. No operational action is ever executed without an
    explicit human decision reaching this point.
    """

    decision = interrupt(
        {
            "question": state.get("question", ""),
            "analysis": state.get("analysis", ""),
            "confidence": state.get("confidence"),
            "recommendation": state.get("recommendation", ""),
            "allowed_actions": list(ALLOWED_ACTIONS.keys()),
        }
    )

    return {
        "approved": bool(decision.get("approved", False)),
        "action_name": decision.get("action", "no_action"),
        "action_params": decision.get("params", {}) or {},
    }
