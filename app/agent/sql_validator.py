import re


FORBIDDEN_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
}


def validate_sql(sql: str) -> str:
    """
    Validate that the generated SQL is a safe PostgreSQL SELECT query.

    Returns:
        Cleaned SQL query.

    Raises:
        ValueError: If the SQL is unsafe or invalid.
    """

    if not sql or not sql.strip():
        raise ValueError("SQL query is empty.")

    sql = sql.strip()

    # Remove markdown code fences if the LLM returned them.
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s*```$", "", sql)

    sql = sql.strip()

    # Must start with SELECT or WITH.
    # WITH is allowed because PostgreSQL queries can use CTEs:
    # WITH x AS (...) SELECT ...
    if not re.match(r"^(SELECT|WITH)\b", sql, re.IGNORECASE):
        raise ValueError("Only SELECT queries are allowed.")

    # Remove a trailing semicolon for easier validation.
    sql = sql.rstrip(";").strip()

    # Check for forbidden SQL commands.
    for keyword in FORBIDDEN_KEYWORDS:
        pattern = rf"\b{keyword}\b"

        if re.search(pattern, sql, re.IGNORECASE):
            raise ValueError(
                f"Forbidden SQL keyword detected: {keyword}"
            )

    # Prevent multiple statements.
    if ";" in sql:
        raise ValueError("Multiple SQL statements are not allowed.")

    return sql