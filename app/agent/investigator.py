from app.agent.sql_generator import generate_sql
from app.tools.sql_tool import execute_sql


def investigator_node(state):
    question = state["question"]
    plan = state["investigation_plan"]

    evidence = []
    current_step = 0

    for index, step in enumerate(plan):
        current_step = index
        print(f"\nInvestigating step {current_step}: {step}")

        # Generate SQL dynamically using Gemini. Generation can fail for
        # reasons execute_sql can't catch (e.g. a non-retryable LLM error,
        # malformed/empty response). Isolate that failure to this step so
        # one bad step doesn't crash the whole investigation.
        try:
            query = generate_sql(question, step)
        except Exception as e:
            print(f"SQL generation failed for step {current_step}: {e}")
            evidence.append({
                "step": step,
                "sql": None,
                "result": {
                    "success": False,
                    "error": f"SQL generation failed: {e}",
                },
            })
            continue

        print(f"Generated SQL:\n{query}")

        # Execute generated SQL. execute_sql already catches its own
        # exceptions and returns {"success": False, "error": ...}, but we
        # guard here too in case of an unexpected error bubbling out.
        try:
            result = execute_sql(query)
        except Exception as e:
            print(f"SQL execution failed for step {current_step}: {e}")
            result = {
                "success": False,
                "error": f"SQL execution failed: {e}",
            }

        print(f"Query result:\n{result}")

        evidence.append({
            "step": step,
            "sql": query,
            "result": result
        })

    return {
        "evidence": evidence,
        "current_step": current_step,
    }