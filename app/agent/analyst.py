import json

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


def _format_evidence(evidence: list[dict]) -> str:
    """Render each evidence item's SQL + result as compact text for the prompt."""

    blocks = []

    for i, item in enumerate(evidence, start=1):
        result = item.get("result", {})

        if result.get("success"):
            rows_preview = result.get("rows", [])[:20]
            result_summary = (
                f"columns={result.get('columns')}, "
                f"row_count={result.get('row_count')}, "
                f"rows={json.dumps(rows_preview, default=str)}"
            )
        else:
            result_summary = f"ERROR: {result.get('error')}"

        blocks.append(
            f"Step {i}: {item.get('step')}\n"
            f"SQL: {item.get('sql')}\n"
            f"Result: {result_summary}"
        )

    return "\n\n".join(blocks)


def analyst_node(state):
    """
    Summarize the collected evidence into a coherent root-cause analysis.

    Reads `question` and `evidence` from state, produces a natural-language
    `analysis` covering what was found, which dimensions/entities are driving
    the anomaly, and the likely root cause(s), grounded only in the evidence
    collected by the investigator.
    """

    question = state["question"]
    evidence = state.get("evidence", [])
    hypotheses = state.get("hypotheses", [])

    if not evidence:
        return {"analysis": "No evidence was collected, so no analysis could be produced."}

    evidence_text = _format_evidence(evidence)
    hypotheses_text = "\n".join(hypotheses) if hypotheses else "(none generated)"

    prompt = f"""
You are a senior operations analyst reviewing an automated investigation.

Original question:
{question}

Candidate hypotheses formed before evidence was collected (unverified guesses,
to be confirmed, refined, or discarded based on the evidence below):
{hypotheses_text}

Below is the evidence gathered during the investigation, in order. Each item
contains the investigation step, the SQL query that was run, and its result.

{evidence_text}

Write a concise root-cause analysis based ONLY on this evidence. State which
of the candidate hypotheses above are supported, partially supported, or
contradicted by the evidence. Do not invent data that is not present above.

Structure your answer as:
1. Summary of what was found (1-2 sentences).
2. Key contributing factors/dimensions (e.g. specific warehouses, carriers,
   regions, service levels) that stand out, with the supporting numbers.
3. Most likely root cause(s).

Keep it factual and grounded in the query results. If the evidence is
inconclusive or contains errors, say so explicitly.
"""

    response = _invoke_llm(prompt)

    analysis = _extract_text(response.content)

    return {"analysis": analysis}
