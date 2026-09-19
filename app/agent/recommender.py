from app.agent.llm_provider import get_llm
from app.agent.llm_retry import llm_retry


@llm_retry
def _invoke_llm(prompt: str):
    return get_llm().invoke(prompt)


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
    analysis and confidence.

    This runs after the analyst node and is a prerequisite for any later
    human-approval / action-execution steps: the recommendation is what a
    human operator will be asked to approve.
    """

    question = state["question"]
    analysis = state.get("analysis", "")
    confidence = state.get("confidence", 0.0)

    if not analysis:
        return {"recommendation": "No analysis was available, so no recommendation could be produced."}

    prompt = f"""
You are a senior operations lead deciding what action to take following an
automated investigation.

Original question:
{question}

Root-cause analysis (confidence={confidence}):
{analysis}

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
