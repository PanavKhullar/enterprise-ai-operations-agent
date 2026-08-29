from langgraph.graph import StateGraph, START, END

from app.agent.state import AgentState
from app.agent.planner import planner_node
from app.agent.investigator import investigator_node


def build_graph():

    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_node)
    graph.add_node("investigator", investigator_node)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "investigator")
    graph.add_edge("investigator", END)

    return graph.compile()


agent = build_graph()