import asyncio

from app.agent.sql_generator import generate_sql
from app.tools.sql_tool import execute_sql


async def _investigate_step(question: str, index: int, step: str) -> dict:
    """
    Run one investigation step (SQL generation + execution).

    `generate_sql` (LLM call) and `execute_sql` (psycopg2/SQLAlchemy call)
    are both synchronous, blocking calls. They're offloaded to
    `asyncio.to_thread` so multiple steps' blocking I/O can overlap on
    separate threads while `investigator_node` awaits them concurrently
    via `asyncio.gather` — turning `sum(step times)` into ~`max(step
    times)` without rewriting the LLM/DB clients to be natively async.
    """

    print(f"\nInvestigating step {index}: {step}")

    # Generate SQL dynamically using Gemini. Generation can fail for
    # reasons execute_sql can't catch (e.g. a non-retryable LLM error,
    # malformed/empty response). Isolate that failure to this step so
    # one bad step doesn't crash the whole investigation.
    try:
        query = await asyncio.to_thread(generate_sql, question, step)
    except Exception as e:
        print(f"SQL generation failed for step {index}: {e}")
        return {
            "step": step,
            "sql": None,
            "result": {
                "success": False,
                "error": f"SQL generation failed: {e}",
            },
        }

    print(f"Generated SQL:\n{query}")

    # Execute generated SQL. execute_sql already catches its own
    # exceptions and returns {"success": False, "error": ...}, but we
    # guard here too in case of an unexpected error bubbling out.
    try:
        result = await asyncio.to_thread(execute_sql, query)
    except Exception as e:
        print(f"SQL execution failed for step {index}: {e}")
        result = {
            "success": False,
            "error": f"SQL execution failed: {e}",
        }

    print(f"Query result:\n{result}")

    return {
        "step": step,
        "sql": query,
        "result": result,
    }


async def _investigate_all(question: str, plan: list[str]) -> list[dict]:
    tasks = [
        _investigate_step(question, index, step)
        for index, step in enumerate(plan)
    ]
    return list(await asyncio.gather(*tasks))


def investigator_node(state):
    question = state["question"]
    plan = state["investigation_plan"]

    evidence = asyncio.run(_investigate_all(question, plan)) if plan else []

    return {
        "evidence": evidence,
        "current_step": len(plan) - 1 if plan else 0,
    }