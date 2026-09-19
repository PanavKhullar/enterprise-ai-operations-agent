import json

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
            f"[evidence_id={i}] Step {i}: {item.get('step')}\n"
            f"SQL: {item.get('sql')}\n"
            f"Result: {result_summary}"
        )

    return "\n\n".join(blocks)


def _extract_json(text: str) -> dict:
    """Extract a JSON object from LLM output, tolerating markdown code fences."""

    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in LLM output: {text!r}")

    return json.loads(cleaned[start : end + 1])


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

    if not evidence:
        return {
            "analysis": "No evidence was collected, so no analysis could be produced.",
            "confidence": 0.0,
            "citations": [],
        }

    evidence_text = _format_evidence(evidence)

    prompt = f"""
You are a senior operations analyst reviewing an automated investigation.

Original question:
{question}

Below is the evidence gathered during the investigation, in order. Each item
is tagged with an [evidence_id=N] and contains the investigation step, the
SQL query that was run, and its result.

{evidence_text}

Write a concise root-cause analysis based ONLY on this evidence. Do not
invent data that is not present above.

Respond with ONLY a single JSON object (no markdown fences, no extra text),
matching exactly this schema:

{{
  "analysis": "<string: 1) summary of what was found, 2) key contributing "
              "factors/dimensions with supporting numbers, 3) most likely "
              "root cause(s). Reference evidence using [evidence_id=N] "
              "inline where a claim is backed by specific evidence.>",
  "confidence": <float 0.0-1.0: overall confidence in the root-cause "
                "analysis, based on how directly and completely the "
                "evidence supports the conclusion>,
  "citations": [
    {{
      "claim": "<short paraphrase of a specific claim made in the analysis>",
      "evidence_ids": [<int, ...>]
    }}
  ]
}}

If the evidence is inconclusive or contains errors, reflect that with a low
confidence score and say so explicitly in the analysis text.
"""

    response = _invoke_llm(prompt)

    raw_text = _extract_text(response.content)

    try:
        parsed = _extract_json(raw_text)
    except (ValueError, json.JSONDecodeError):
        return {
            "analysis": raw_text,
            "confidence": 0.0,
            "citations": [],
        }

    return {
        "analysis": parsed.get("analysis", raw_text),
        "confidence": float(parsed.get("confidence", 0.0)),
        "citations": parsed.get("citations", []),
    }
