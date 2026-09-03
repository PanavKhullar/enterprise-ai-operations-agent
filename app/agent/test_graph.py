from langgraph.types import Command

from app.agent.graph import agent


initial_state = {
    "thread_id": "test-graph-run",
    "question": "Why has SLA performance deteriorated recently?",
    "investigation_plan": [],
    "hypotheses": [],
    "current_step": 0,
    "evidence": [],
    "analysis": "",
    "confidence": 0.0,
    "hypothesis_evaluations": [],
    "citations": [],
    "recommendation": "",
    "approved": False,
    "action_name": "",
    "action_params": {},
    "action_result": {},
}

config = {"configurable": {"thread_id": "test-graph-run"}}

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

print("\n\n=== HYPOTHESES ===\n")
for h in result.get("hypotheses", []):
    print(h)

print("\n\n=== EVIDENCE ===\n")
for item in result.get("evidence", []):
    print(item)
    print("---")

print("\n\n=== ANALYSIS ===\n")
print(result.get("analysis", "<no analysis produced>"))

print("\n\n=== CONFIDENCE ===\n")
print(result.get("confidence"))

print("\n\n=== HYPOTHESIS EVALUATIONS ===\n")
for h in result.get("hypothesis_evaluations", []):
    print(h)

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