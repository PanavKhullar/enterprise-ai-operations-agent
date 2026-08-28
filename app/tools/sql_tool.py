import re
from typing import Any

from sqlalchemy import text

from app.db.database import readonly_engine

# Hard cap on rows returned to the agent, to bound token cost/latency
# and avoid dumping huge result sets into the LLM context.
MAX_ROWS = 200

# Statement timeout (ms) applied per-connection so a slow/expensive
# generated query (e.g. an accidental cross join) can't hang the request.
STATEMENT_TIMEOUT_MS = 5000

_LIMIT_RE = re.compile(r"\blimit\s+\d+\b", re.IGNORECASE)


def execute_sql(query: str) -> dict[str, Any]:
    """
    Execute a read-only SQL query against the operational database.

    Safety is enforced in two layers:
    1. App-level check: query must be a single SELECT statement.
    2. DB-level: connection uses the `ops_readonly` role, which only
       has SELECT privileges, so even a bypassed check can't write.
    """

    query = query.strip().rstrip(";")

    if not query:
        return {
            "success": False,
            "error": "Query cannot be empty."
        }

    if ";" in query:
        return {
            "success": False,
            "error": "Multiple statements are not allowed."
        }

    if not query.lower().startswith("select"):
        return {
            "success": False,
            "error": "Only SELECT queries are allowed."
        }

    if not _LIMIT_RE.search(query):
        query = f"{query} LIMIT {MAX_ROWS}"

    try:
        with readonly_engine.connect() as connection:
            connection.execute(
                text("SET statement_timeout = :timeout_ms"),
                {"timeout_ms": STATEMENT_TIMEOUT_MS},
            )

            result = connection.execute(text(query))

            columns = list(result.keys())
            rows = [dict(row._mapping) for row in result]

            return {
                "success": True,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }