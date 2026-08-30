import httpx
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.agent.state import AgentState
from dotenv import load_dotenv

load_dotenv()


llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",

)


@retry(
    retry=retry_if_exception_type((httpx.RemoteProtocolError, httpx.ReadTimeout, httpx.ConnectError)),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    reraise=True,
)
def _invoke_llm(prompt):
    return llm.invoke(prompt)


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

    response = _invoke_llm(prompt)

    content = response.content

    if isinstance(content, list):
        text = "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict)
        )
    else:
        text = content

    plan = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    return {
        "investigation_plan": plan
    }