import httpx
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",
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


def recommender_node(state):
    """
    Produce an actionable recommendation based on the analyst's root-cause
    analysis, confidence, and hypothesis evaluations.

    This runs after the analyst node and is a prerequisite for any later
    human-approval / action-execution steps: the recommendation is what a
    human operator will be asked to approve.
    """

    question = state["question"]
    analysis = state.get("analysis", "")
    confidence = state.get("confidence", 0.0)
    hypothesis_evaluations = state.get("hypothesis_evaluations", [])

    if not analysis:
        return {"recommendation": "No analysis was available, so no recommendation could be produced."}

    evaluations_text = (
        "\n".join(
            f"- {e.get('hypothesis')}: {e.get('verdict')} ({e.get('explanation')})"
            for e in hypothesis_evaluations
        )
        or "(none)"
    )

    prompt = f"""
You are a senior operations lead deciding what action to take following an
automated investigation.

Original question:
{question}

Root-cause analysis (confidence={confidence}):
{analysis}

Hypothesis evaluations:
{evaluations_text}

Based ONLY on the above, write a concise, actionable recommendation for what
the operations team should do next. Requirements:
- If confidence is high (>= 0.6) and a clear root cause is identified,
  propose 1-3 specific, concrete remediation actions (e.g. reassign carrier
  volume, scale a specific warehouse, escalate to a specific vendor),
  referencing the entities/dimensions named in the analysis.
- If confidence is low (< 0.6) or the evidence is inconclusive, recommend
  further investigation steps instead of a remediation action, and say so
  explicitly.
- Do not invent facts, entities, or numbers not present in the analysis
  above.
- Keep the response to 3-6 sentences, plain text, no markdown, no headers.
"""

    response = _invoke_llm(prompt)

    recommendation = _extract_text(response.content)

    return {"recommendation": recommendation}
