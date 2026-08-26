from sqlalchemy import text

from app.db.database import engine


def execute_sql(query: str) -> str:
    """
    Execute a read-only SQL query against the operational database.
    """

    query = query.strip()

    # Basic safety check
    if not query.lower().startswith("select"):
        return "Error: Only SELECT queries are allowed."

    try:
        with engine.connect() as connection:
            result = connection.execute(text(query))

            rows = result.fetchall()

            if not rows:
                return "Query returned no results."

            columns = result.keys()

            output = []

            # Header
            output.append(" | ".join(columns))

            # Rows
            for row in rows:
                output.append(
                    " | ".join(str(value) for value in row)
                )

            return "\n".join(output)

    except Exception as e:
        return f"SQL execution error: {str(e)}"