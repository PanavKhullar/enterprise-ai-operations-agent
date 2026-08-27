from typing import Any

from sqlalchemy import text

from app.db.database import engine


def execute_sql(query: str) -> dict[str, Any]:
    """
    Execute a read-only SQL query against the operational database.
    """

    query = query.strip()

    if not query:
        return {
            "success": False,
            "error": "Query cannot be empty."
        }

    if not query.lower().startswith("select"):
        return {
            "success": False,
            "error": "Only SELECT queries are allowed."
        }

    try:
        with engine.connect() as connection:
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