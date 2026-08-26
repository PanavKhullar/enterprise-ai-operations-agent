from app.agent.planner import planner_node


state = {
    "question": "Why has SLA performance deteriorated recently?",
    "investigation_plan": [],
    "evidence": [],
    "analysis": "",
    "recommendation": "",
    "approved": False,
}


result = planner_node(state)

print("\nInvestigation Plan:\n")

for step in result["investigation_plan"]:
    print(step)