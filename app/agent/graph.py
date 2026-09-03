from psycopg import Connection

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver

from app.agent.state import AgentState
from app.db.database import CHECKPOINTER_DATABASE_URL
from app.agent.planner import planner_node
from app.agent.hypothesis import hypothesis_node
from app.agent.investigator import investigator_node
from app.agent.analyst import analyst_node
from app.agent.recommender import recommender_node
from app.agent.approval import approval_node
from app.agent.action_executor import action_node
from app.agent.history import history_node


def build_graph():

    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_node)
    graph.add_node("hypothesis", hypothesis_node)
    graph.add_node("investigator", investigator_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("recommender", recommender_node)
    graph.add_node("approval", approval_node)
    graph.add_node("action", action_node)
    graph.add_node("history", history_node)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "hypothesis")
    graph.add_edge("hypothesis", "investigator")
    graph.add_edge("investigator", "analyst")
    graph.add_edge("analyst", "recommender")
    graph.add_edge("recommender", "approval")
    graph.add_edge("approval", "action")
    graph.add_edge("action", "history")
    graph.add_edge("history", END)

    # A checkpointer is required for `interrupt()` in the approval node:
    # it lets the graph pause mid-run and be resumed later (e.g. from a
    # separate API request) once a human operator has made a decision.
    #
    # PostgresSaver (instead of InMemorySaver) persists checkpoints to the
    # ops_db Postgres instance, so a paused investigation survives an app
    # restart/crash — the human operator can approve/reject even if the
    # API process was restarted in between.
    conn = Connection.connect(
        CHECKPOINTER_DATABASE_URL,
        autocommit=True,
        prepare_threshold=0,
    )
    checkpointer = PostgresSaver(conn)
    checkpointer.setup()

    return graph.compile(checkpointer=checkpointer)


agent = build_graph()