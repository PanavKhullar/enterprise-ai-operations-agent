from app.agent.graph import agent


initial_state = {
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
}

result = agent.invoke(initial_state)

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