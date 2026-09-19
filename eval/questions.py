"""
Curated 20-question evaluation set for the ops investigation agent.

Grounded in the two anomalies actually injected by
`data/generate_data.py`:

1. WAREHOUSE anomaly: WH_03 (Mumbai) processing time (created_at ->
   shipped_at) gets +12-36h slower for orders created in the last 30
   days of the 180-day window (created_at >= start_date + 150 days).
2. CARRIER anomaly: CAR_03 (Delhivery) delivery time (shipped_at ->
   delivered_at) gets +1-3 days slower in that same recent window.

Both anomalies only show up when comparing the RECENT (last ~30 days)
period against the HISTORICAL baseline. Looking at the full 180-day
range dilutes/hides them. SLA breach rate (sla_events.event_type =
'SLA_BREACH') is a downstream symptom of both, since it's driven by
promised_at vs delivered_at.

Each entry:
- question: natural-language question to feed the agent
- expected_tables: table(s) the generated SQL should reference to
  correctly answer the question (used for evidence/tool-selection
  scoring — checked via substring match on generated SQL, not LLM
  judgment)
- expected_conclusion: the ground-truth takeaway, for manual
  correctness scoring against the agent's `analysis` output
- category: warehouse | carrier | sla | multi_factor | negative_control
"""

QUESTIONS = [
    # --- Warehouse anomaly (WH_03 / Mumbai) ---
    {
        "question": "Has any warehouse's order processing time gotten worse recently compared to before?",
        "expected_tables": ["orders", "shipments"],
        "expected_conclusion": "WH_03 (Mumbai Warehouse) processing time (created_at to shipped_at) increased in the most recent ~30 days versus the historical baseline.",
        "category": "warehouse",
    },
    {
        "question": "Compare average order processing time by warehouse for the last 30 days vs the prior period.",
        "expected_tables": ["orders", "shipments"],
        "expected_conclusion": "WH_03 shows a clear increase in processing time in the last 30 days; other warehouses stay roughly stable.",
        "category": "warehouse",
    },
    {
        "question": "Which warehouse is currently the slowest to process orders?",
        "expected_tables": ["orders", "shipments"],
        "expected_conclusion": "WH_03 (Mumbai Warehouse) is the slowest in the recent period due to the injected processing delay.",
        "category": "warehouse",
    },
    {
        "question": "Is Mumbai Warehouse (WH_03) experiencing any delays?",
        "expected_tables": ["orders", "shipments"],
        "expected_conclusion": "Yes — WH_03 has an elevated processing time in the last 30 days compared to its own historical baseline.",
        "category": "warehouse",
    },
    {
        "question": "Did warehouse capacity affect processing times for any warehouse recently?",
        "expected_tables": ["warehouses", "orders", "shipments"],
        "expected_conclusion": "The slowdown is specific to WH_03 and time-boxed to the recent period; it does not correlate with warehouse capacity (WH_03 isn't the smallest or largest by capacity).",
        "category": "warehouse",
    },

    # --- Carrier anomaly (CAR_03 / Delhivery) ---
    {
        "question": "Which carrier should we invest more in based on delivery performance?",
        "expected_tables": ["shipments"],
        "expected_conclusion": "Delhivery (CAR_03) should NOT get more investment right now — it has recently gotten slower; other carriers (FastTrack, BlueDart, Ecom Express) are comparatively more consistent.",
        "category": "carrier",
    },
    {
        "question": "Has any carrier's delivery time gotten worse recently?",
        "expected_tables": ["shipments"],
        "expected_conclusion": "CAR_03 (Delhivery) delivery time (shipped_at to delivered_at) increased in the last ~30 days versus the historical baseline.",
        "category": "carrier",
    },
    {
        "question": "Compare carrier delivery times for the last 30 days vs the prior period.",
        "expected_tables": ["shipments"],
        "expected_conclusion": "Delhivery (CAR_03) shows an increase in delivery time in the recent period; other carriers remain roughly stable.",
        "category": "carrier",
    },
    {
        "question": "Which carrier currently has the worst delivery performance?",
        "expected_tables": ["shipments"],
        "expected_conclusion": "Delhivery (CAR_03) currently has the worst delivery performance due to the injected recent slowdown.",
        "category": "carrier",
    },
    {
        "question": "Is Delhivery performing worse than other carriers?",
        "expected_tables": ["shipments"],
        "expected_conclusion": "Yes, in the recent ~30-day window Delhivery (CAR_03) delivery times are elevated versus its own historical baseline and versus other carriers.",
        "category": "carrier",
    },

    # --- SLA-focused (downstream symptom of both anomalies) ---
    {
        "question": "Why did our SLA breach rate increase recently?",
        "expected_tables": ["sla_events", "orders", "shipments"],
        "expected_conclusion": "SLA breaches rose mainly for WH_03 orders and CAR_03 shipments in the recent period, consistent with the processing/delivery slowdowns for those two.",
        "category": "sla",
    },
    {
        "question": "Which warehouse has the highest SLA breach rate?",
        "expected_tables": ["sla_events", "orders"],
        "expected_conclusion": "WH_03 has the highest SLA breach rate in the recent period due to its processing slowdown.",
        "category": "sla",
    },
    {
        "question": "What is the overall SLA compliance rate across all orders?",
        "expected_tables": ["sla_events"],
        "expected_conclusion": "A single overall figure blended across the full 180-day history; recent degradation from WH_03/CAR_03 is diluted and not obviously visible at this aggregate level.",
        "category": "sla",
    },
    {
        "question": "Are SLA breaches concentrated in a specific region?",
        "expected_tables": ["sla_events", "orders"],
        "expected_conclusion": "No strong regional pattern — breaches concentrate by specific warehouse (WH_03) and carrier (CAR_03), not by region as a whole.",
        "category": "sla",
    },
    {
        "question": "How many orders breached their SLA in the last 30 days?",
        "expected_tables": ["sla_events"],
        "expected_conclusion": "An elevated count/rate versus the historical baseline, driven primarily by WH_03 and CAR_03 orders.",
        "category": "sla",
    },

    # --- Multi-factor (both anomalies interacting) ---
    {
        "question": "Which combination of warehouse and carrier has the worst recent delivery performance?",
        "expected_tables": ["orders", "shipments"],
        "expected_conclusion": "Orders from WH_03 shipped via CAR_03 in the recent period show the worst combined delay, since both anomalies stack.",
        "category": "multi_factor",
    },
    {
        "question": "Is the recent SLA drop caused by warehouses, carriers, or both?",
        "expected_tables": ["orders", "shipments", "sla_events"],
        "expected_conclusion": "Both — WH_03's processing slowdown and CAR_03's delivery slowdown are independent contributing causes in the same recent window.",
        "category": "multi_factor",
    },
    {
        "question": "For orders delayed in the last 30 days, what's the split between warehouse-side delay and carrier-side delay?",
        "expected_tables": ["orders", "shipments"],
        "expected_conclusion": "Some delay attributable to WH_03 processing time, some to CAR_03 delivery time, and orders hitting both show compounded delay.",
        "category": "multi_factor",
    },

    # --- Negative controls (no seeded anomaly exists) ---
    {
        "question": "Are shipments experiencing more damage or loss recently?",
        "expected_tables": ["shipments"],
        "expected_conclusion": "No such anomaly exists in the data (no damage/loss field is even modeled) — the agent should not fabricate a damage-related finding.",
        "category": "negative_control",
    },
    {
        "question": "Has any region seen a sudden spike in order demand recently?",
        "expected_tables": ["orders"],
        "expected_conclusion": "No demand-spike anomaly is seeded by region; order volume per region should look roughly uniform/random, and the agent should not invent a regional demand spike.",
        "category": "negative_control",
    },
]
