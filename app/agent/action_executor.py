from app.agent.actions import ALLOWED_ACTIONS


def action_node(state):
    """
    Execute the human-approved action, or record why nothing was executed.

    Runs strictly after `approval_node`, so `state["approved"]` reflects an
    explicit human decision, and `state["action_name"]` is constrained to
    the whitelist the human was shown (`ALLOWED_ACTIONS`).
    """

    if not state.get("approved"):
        return {
            "action_result": {
                "status": "skipped",
                "reason": "Recommendation was not approved by a human operator.",
            }
        }

    action_name = state.get("action_name", "no_action")
    params = state.get("action_params", {}) or {}

    action_fn = ALLOWED_ACTIONS.get(action_name)

    if action_fn is None:
        return {
            "action_result": {
                "status": "error",
                "reason": f"Unknown action '{action_name}'. No action executed.",
            }
        }

    result = action_fn(params)

    return {"action_result": result}
