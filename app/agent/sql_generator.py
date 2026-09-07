import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agent.llm_retry import llm_retry

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
)

# Fixed "recent" vs "historical/baseline" windows used whenever a step asks
# for a recent-vs-historical comparison (e.g. "compare recent performance
# with historical performance", "identify when this started"). Without
# this, the LLM had to invent its own window per query, which made the
# comparison non-deterministic across steps/runs and could silently miss
# the actual anomaly window in the data.
#
# 30 days lines up with how the synthetic data is generated
# (data/generate_data.py): known anomalies (WH_03 slowdown, CAR_03 carrier
# delays) are injected only in the most recent 30 days of a 180-day range.
RECENT_WINDOW_DAYS = 30
BASELINE_WINDOW_DAYS = 150


def _compute_windows() -> dict[str, str]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    recent_start = now - timedelta(days=RECENT_WINDOW_DAYS)
    baseline_start = recent_start - timedelta(days=BASELINE_WINDOW_DAYS)

    return {
        "now": now.isoformat(),
        "recent_start": recent_start.isoformat(),
        "baseline_start": baseline_start.isoformat(),
    }


@llm_retry
def _invoke_llm(prompt: str):
    return llm.invoke(prompt)


def generate_sql(question: str, investigation_step: str) -> str:

    windows = _compute_windows()

    prompt = f"""
You are a SQL analyst for an operations investigation system.

User question:
{question}

Investigation step:
{investigation_step}

Fixed time windows (use these exact boundaries whenever this step involves
comparing "recent" vs "historical"/"baseline" performance, or asks when a
problem started — do NOT invent your own date ranges or use NOW() /
CURRENT_DATE for this purpose):
- Recent window:   timestamp >= '{windows["recent_start"]}' AND timestamp < '{windows["now"]}'
- Baseline window: timestamp >= '{windows["baseline_start"]}' AND timestamp < '{windows["recent_start"]}'
(Substitute "timestamp" with whichever date/time column of the relevant
table is appropriate for the metric, e.g. orders.created_at,
shipments.shipped_at/delivered_at, sla_events.created_at.)

If the step asks for a trend/breakdown over time (e.g. by day or week) to
locate when a deviation started, bucket by day/week within the recent
window above (optionally including the baseline window too) rather than
picking your own arbitrary range.

Available database tables:

warehouses:
- warehouse_id
- name
- region
- capacity

carriers:
- carrier_id
- name

orders:
- order_id
- warehouse_id
- region
- created_at
- promised_at

shipments:
- shipment_id
- order_id
- warehouse_id
- carrier_id
- shipped_at
- delivered_at

sla_events:
- event_id
- order_id
- warehouse_id
- event_type
- expected_time
- actual_time
- delay_minutes
- created_at

Generate ONE PostgreSQL SELECT query that answers the investigation step.

Rules:
- Only generate SELECT queries.
- Do not INSERT, UPDATE, DELETE, DROP, ALTER, or CREATE.
- Use only the tables and columns provided above.
- PostgreSQL has no ROUND(double precision, integer) overload. If you call
  ROUND() on an AVG(), SUM(), or other expression that may be a double
  precision value, cast it to numeric first, e.g. ROUND(AVG(x)::numeric, 2).
- Return ONLY the SQL query.
"""

    response = _invoke_llm(prompt)

    content = response.content

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