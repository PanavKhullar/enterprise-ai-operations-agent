from app.agent.graph import agent


initial_state = {
    "question": "Why has SLA performance deteriorated recently?",
    "investigation_plan": [],
    "current_step": 0,
    "evidence": [],
    "analysis": "",
    "recommendation": "",
    "approved": False,
}

result = agent.invoke(initial_state)

print("\nInvestigation Plan:\n")

for step in result["investigation_plan"]:
    print(step)

print("\n\n=== EVIDENCE ===\n")
for item in result.get("evidence", []):
    print(item)
    print("---")

print("\n\n=== ANALYSIS ===\n")
print(result.get("analysis", "<no analysis produced>"))