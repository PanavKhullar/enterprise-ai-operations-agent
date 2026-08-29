from sqlalchemy import text

from app.db.database import engine
from app.agent.sql_validator import validate_sql


def execute_sql(sql: str) -> list[dict]:
    """
    Validate and execute a read-only SQL query.

    Returns:
        Query results as a list of dictionaries.
    """

    validated_sql = validate_sql(sql)

    with engine.connect() as connection:
        result = connection.execute(text(validated_sql))

        rows = result.mappings().all()

    return [dict(row) for row in rows]