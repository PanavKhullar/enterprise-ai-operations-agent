from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from app.agent.state import AgentState


llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
)


planner_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
You are an enterprise operations investigation planner.

Your job is to create a structured investigation plan
for operational questions.

The database contains:
- orders
- shipments
- warehouses
- carriers
- sla_events

The investigation should use data and evidence rather than assumptions.

Break the investigation into clear steps.

For example:
1. Establish the overall metric.
2. Compare recent performance with historical performance.
3. Identify the dimensions contributing to the problem.
4. Investigate likely causes.
5. Validate the suspected root cause with additional evidence.

Return ONLY a numbered list of investigation steps.
"""
    ),
    (
        "human",
        "Investigation question:\n{question}"
    ),
])


def planner_node(state: AgentState):

    question = state["question"]

    prompt = planner_prompt.invoke({
        "question": question
    })

    response = llm.invoke(prompt)

    plan = [
        line.strip()
        for line in response.content.splitlines()
        if line.strip()
    ]

    return {
        "investigation_plan": plan
    }