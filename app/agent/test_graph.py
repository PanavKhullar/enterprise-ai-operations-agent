import os
import uuid

# Prevent OpenTelemetry console exporters from flooding test output.
os.environ.setdefault("OTEL_CONSOLE_EXPORT", "false")

from app.telemetry import setup_logging, setup_metrics, setup_tracing

# Initialize observability for this standalone test process.
setup_logging()
setup_tracing("ops-agent-test")
setup_metrics("ops-agent-test")

from langgraph.types import Command
from app.agent.graph import agent

# A fresh thread_id per run is required: node_timings uses an operator.add
# reducer and the graph is checkpointed in Postgres by thread_id, so
# reusing a fixed thread_id across script runs causes each new run's
# node_timings to be appended onto every previous run's entries instead
# of starting clean, silently corrupting the latency measurement.
thread_id = f"test-graph-run-{uuid.uuid4()}"

initial_state = {
    "thread_id": thread_id,
    "question": "Compare average order processing time by warehouse for the last 30 days vs the prior period.",
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

config = {"configurable": {"thread_id": thread_id}}

result = agent.invoke(initial_state, config=config)

if "__interrupt__" in result:
    interrupt_payload = result["__interrupt__"][0].value

    print("\n\n=== AWAITING HUMAN APPROVAL ===\n")
    print(interrupt_payload["recommendation"])

    # Simulate a human operator approving the top remediation action so this
    # script can still demonstrate the full pipeline non-interactively.
    decision = {
        "approved": True,
        "action": "reassign_carrier_volume",
        "params": {
            "carrier": "Delhivery",
            "target_carrier": "BlueDart Express",
            "percentage": 50,
        },
    }

    result = agent.invoke(Command(resume=decision), config=config)

print("\nInvestigation Plan:\n")

for step in result["investigation_plan"]:
    print(step)

print("\n\n=== EVIDENCE ===\n")
for item in result.get("evidence", []):
    print(item)
    print("---")

print("\n\n=== ANALYSIS ===\n")
print(result.get("analysis", "<no analysis produced>"))

print("\n\n=== CONFIDENCE ===\n")
print(result.get("confidence"))

print("\n\n=== CITATIONS ===\n")
for c in result.get("citations", []):
    print(c)

print("\n\n=== RECOMMENDATION ===\n")
print(result.get("recommendation", "<no recommendation produced>"))

print("\n\n=== APPROVAL ===\n")
print("approved:", result.get("approved"))
print("action_name:", result.get("action_name"))
print("action_params:", result.get("action_params"))

print("\n\n=== ACTION RESULT ===\n")
print(result.get("action_result", "<no action result>"))

print("\n\n=== NODE TIMINGS ===\n")
for t in result.get("node_timings", []):
    print(t)