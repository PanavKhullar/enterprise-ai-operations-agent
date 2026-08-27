from langgraph.graph import StateGraph, START, END

from app.agent.state import AgentState
from app.agent.planner import planner_node


def build_graph():

    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("planner", planner_node)

    # Define flow
    graph.add_edge(START, "planner")
    graph.add_edge("planner", END)

    return graph.compile()


agent = build_graph()