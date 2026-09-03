import json

from app.db.database import SessionLocal
from app.db.models import Investigation


def history_node(state):
    """
    Persist the completed investigation (plan, evidence, analysis,
    recommendation) to the `investigations` table for later retrieval.

    This is a terminal node: it does not need to mutate agent state, but
    returns an empty dict update to remain a well-behaved LangGraph node.
    """

    session = SessionLocal()

    try:
        record = Investigation(
            thread_id=state.get("thread_id", ""),
            question=state.get("question", ""),
            investigation_plan=state.get("investigation_plan", []),
            hypotheses=state.get("hypotheses", []),
            evidence=json.loads(json.dumps(state.get("evidence", []), default=str)),
            analysis=state.get("analysis", ""),
            confidence=state.get("confidence"),
            hypothesis_evaluations=state.get("hypothesis_evaluations", []),
            citations=state.get("citations", []),
            recommendation=state.get("recommendation", ""),
            approved=state.get("approved", False),
            action_name=state.get("action_name", ""),
            action_result=state.get("action_result", {}),
        )

        session.add(record)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return {}
