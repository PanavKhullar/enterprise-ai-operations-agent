"""
Evaluation runner for the ops investigation agent (Phase 6C).

Runs every question in `eval/questions.py` through the agent directly
(same pattern as `app/agent/test_graph.py` — no HTTP/Celery needed,
just Postgres running), and writes one row per question to a JSON
report under `eval/results/`.

Any recommendation requiring approval is auto-resumed with
`no_action` — this eval is scoring investigation/analysis quality,
not the HITL approval flow itself.

Usage:
    python -m eval.run_eval
"""

import json
import os
import uuid
from datetime import datetime, timezone

from langgraph.types import Command
# Prevent OpenTelemetry console exporters from flooding evaluation output.
os.environ.setdefault("OTEL_CONSOLE_EXPORT", "false")

from app.telemetry import setup_logging, setup_metrics, setup_tracing

# Initialize observability for this standalone evaluation process.
setup_logging()
setup_tracing("ops-agent-evaluation")
setup_metrics("ops-agent-evaluation")

from app.agent.graph import agent
from eval.questions import QUESTIONS

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")


def _initial_state(thread_id: str, question: str) -> dict:
    return {
        "thread_id": thread_id,
        "question": question,
        "investigation_plan": [],
        "current_step": 0,
        "evidence": [],
        "analysis": "",
        "confidence": 0.0,
        "citations": [],
        "recommendation": "",
        "approved": False,
        "action_name": "",
        "action_params": {},
        "action_result": {},
        "node_timings": [],
    }


def _evidence_tables_hit(evidence: list[dict], expected_tables: list[str]) -> dict:
    """Substring-match each expected table name against every generated
    SQL string in the evidence, so evidence/tool-selection correctness
    is checked deterministically instead of via LLM judgment."""

    all_sql = " ".join((item.get("sql") or "") for item in evidence).lower()
    hits = {table: (table.lower() in all_sql) for table in expected_tables}
    return hits


def run_one(entry: dict) -> dict:
    thread_id = f"eval-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}

    print(f"\n=== Running: {entry['question']} ===")

    result = agent.invoke(_initial_state(thread_id, entry["question"]), config=config)

    if "__interrupt__" in result:
        # Auto-resume with no_action so the run completes; we're scoring
        # analysis/evidence quality, not the approval decision itself.
        result = agent.invoke(
            Command(resume={"approved": False, "action": "no_action", "params": {}}),
            config=config,
        )

    evidence = result.get("evidence", [])
    evidence_hits = _evidence_tables_hit(evidence, entry["expected_tables"])

    return {
        "thread_id": thread_id,
        "category": entry["category"],
        "question": entry["question"],
        "expected_tables": entry["expected_tables"],
        "evidence_table_hits": evidence_hits,
        "evidence_all_tables_hit": all(evidence_hits.values()),
        "generated_sql": [item.get("sql") for item in evidence],
        "expected_conclusion": entry["expected_conclusion"],
        "actual_analysis": result.get("analysis", ""),
        "actual_confidence": result.get("confidence"),
        "actual_recommendation": result.get("recommendation", ""),
        "node_timings": result.get("node_timings", []),
        # Filled in manually after the run (see eval/README usage).
        "verdict": "",
        "verdict_notes": "",
    }


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    rows = []
    for entry in QUESTIONS:
        try:
            rows.append(run_one(entry))
        except Exception as e:
            print(f"FAILED: {entry['question']}: {e}")
            rows.append(
                {
                    "category": entry["category"],
                    "question": entry["question"],
                    "error": str(e),
                    "verdict": "error",
                    "verdict_notes": "",
                }
            )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = os.path.join(RESULTS_DIR, f"eval_run_{timestamp}.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, default=str)

    print(f"\n\nWrote {len(rows)} results to {out_path}")
    print("Next: open the file and fill in 'verdict' per row "
          "(correct / partial / incorrect), then run eval/report.py")


if __name__ == "__main__":
    main()
