from langgraph.graph import StateGraph, START, END

from app.agent.state import AgentState
from app.agent.planner import planner_node
from app.agent.hypothesis import hypothesis_node
from app.agent.investigator import investigator_node
from app.agent.analyst import analyst_node
from app.agent.history import history_node


def build_graph():

    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_node)
    graph.add_node("hypothesis", hypothesis_node)
    graph.add_node("investigator", investigator_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("history", history_node)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "hypothesis")
    graph.add_edge("hypothesis", "investigator")
    graph.add_edge("investigator", "analyst")
    graph.add_edge("analyst", "history")
    graph.add_edge("history", END)

    return graph.compile()


agent = build_graph()