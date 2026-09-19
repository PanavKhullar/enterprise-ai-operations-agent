from datetime import datetime, timedelta, timezone

from app.agent.llm_provider import get_llm
from app.agent.llm_retry import llm_retry

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

# Fixed reference date for the synthetic evaluation dataset.
# The current database contains data through 27 Aug 2026.
# Using a fixed date keeps evaluation reproducible and aligns
# the recent window with the injected anomalies.
REFERENCE_END_DATE = datetime(
    2026, 8, 27, 0, 0, 0, tzinfo=timezone.utc
)


def _compute_windows() -> dict[str, str]:
    now = REFERENCE_END_DATE
    recent_start = now - timedelta(days=RECENT_WINDOW_DAYS)
    baseline_start = recent_start - timedelta(days=BASELINE_WINDOW_DAYS)

    return {
        "now": now.isoformat(),
        "recent_start": recent_start.isoformat(),
        "baseline_start": baseline_start.isoformat(),
    }


@llm_retry
def _invoke_llm(prompt: str):
    return get_llm().invoke(prompt)


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
- event_type   -- ONLY two possible values: 'SLA_BREACH' or 'SLA_MET'.
                  There is exactly ONE sla_events row per order (not per
                  delay/damage/exception incident) — it always exists,
                  regardless of outcome. There is NO separate delay/damage/
                  exception event type or table anywhere in this schema.
                  Do NOT invent or filter on event_type values like
                  'DELAY', 'DAMAGE', 'EXCEPTION' etc. — they don't exist
                  and will silently return 0 rows.
- expected_time
- actual_time
- delay_minutes  -- 0 when the order was on time, > 0 when it breached.
- created_at

Generate ONE PostgreSQL SELECT query that answers the investigation step.

Rules:
- Only generate SELECT queries.
- Do not INSERT, UPDATE, DELETE, DROP, ALTER, or CREATE.
- Use only the tables and columns provided above.
- Because every order has exactly one sla_events row regardless of
  outcome, counting/joining sla_events WITHOUT filtering
  "event_type = 'SLA_BREACH'" will always equal the total shipment/order
  count and is almost never what's meant by "breaches", "delays", or
  "SLA violations". When the step is about breaches/delays specifically,
  filter with `event_type = 'SLA_BREACH'` (and/or `delay_minutes > 0`).
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