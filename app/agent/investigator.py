from app.agent.sql_generator import generate_sql
from app.tools.sql_tool import execute_sql


def investigator_node(state):
    question = state["question"]
    plan = state["investigation_plan"]

    evidence = []

    for step in plan:
        print(f"\nInvestigating step: {step}")

        # Generate SQL dynamically using Gemini
        query = generate_sql(
            question,
            step
        )

        print(f"Generated SQL:\n{query}")

        # Execute generated SQL
        result = execute_sql(query)

        print(f"Query result:\n{result}")

        evidence.append({
            "step": step,
            "sql": query,
            "result": result
        })

    return {
        "evidence": evidence
    }