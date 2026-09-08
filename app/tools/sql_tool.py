import re
import time
from typing import Any

from sqlalchemy import text

from app.db.database import readonly_engine
from app.agent.sql_validator import validate_sql
from app.cache import get_cached_query_result, set_cached_query_result
import app.telemetry as telemetry
from app.telemetry import get_tracer

tracer = get_tracer(__name__)

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

    Safety is enforced in three layers:
    1. App-level check: `validate_sql` strips markdown fences, requires
       a single SELECT/WITH statement, and blocks forbidden keywords.
    2. Row cap + statement timeout: bound cost/latency of the query.
    3. DB-level: connection uses the `ops_readonly` role, which only
       has SELECT privileges, so even a bypassed check can't write.
    """

    try:
        query = validate_sql(query)
    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
        }

    if not _LIMIT_RE.search(query):
        query = f"{query} LIMIT {MAX_ROWS}"

    cached = get_cached_query_result(query)
    if cached is not None:
        return cached

    start = time.perf_counter()
    with tracer.start_as_current_span("db.execute_sql") as span:
        try:
            with readonly_engine.connect() as connection:
                connection.execute(
                    text("SET statement_timeout = :timeout_ms"),
                    {"timeout_ms": STATEMENT_TIMEOUT_MS},
                )

                result = connection.execute(text(query))

                columns = list(result.keys())
                rows = [dict(row._mapping) for row in result]

                response = {
                    "success": True,
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows),
                }
                set_cached_query_result(query, response)

                duration_ms = (time.perf_counter() - start) * 1000
                span.set_attribute("row_count", len(rows))
                telemetry.db_query_duration.record(duration_ms, {"status": "ok"})
                return response

        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            span.set_attribute("status", "error")
            span.record_exception(e)
            telemetry.db_query_duration.record(duration_ms, {"status": "error"})
            telemetry.db_error_counter.add(1, {"error": type(e).__name__})
            return {
                "success": False,
                "error": str(e),
            }