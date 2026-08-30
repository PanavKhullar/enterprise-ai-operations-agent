import httpx
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

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
def _invoke_llm(prompt: str):
    return llm.invoke(prompt)


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts = []

        for block in content:
            if isinstance(block, dict) and "text" in block:
                text_parts.append(block["text"])

        if text_parts:
            return "\n".join(text_parts).strip()

    raise ValueError(f"LLM returned unexpected content format: {type(content)}")


def hypothesis_node(state):
    """
    Generate candidate root-cause hypotheses before evidence is collected.

    Reads `question` and `investigation_plan` from state and produces a
    `hypotheses` list of plausible operational causes to investigate. These
    are exploratory candidates only — not conclusions — and are later
    validated or discarded by the analyst once evidence is gathered.
    """

    question = state["question"]
    plan = state.get("investigation_plan", [])
    plan_text = "\n".join(plan)

    prompt = f"""
You are an operations analyst forming initial hypotheses before investigating.

Question:
{question}

Planned investigation steps:
{plan_text}

Based on common operational failure modes (carrier delays, warehouse
capacity/fulfillment bottlenecks, regional demand spikes, seasonal effects,
system/process changes), list 3-5 plausible candidate root-cause hypotheses
for this question. These are guesses to be tested against evidence, not
conclusions.

Return ONLY a numbered list of concise hypotheses.
"""

    response = _invoke_llm(prompt)
    text = _extract_text(response.content)

    hypotheses = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    return {"hypotheses": hypotheses}
