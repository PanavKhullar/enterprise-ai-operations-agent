from app.tools.sql_tool import execute_sql


query = """
SELECT
    warehouse_id,
    COUNT(*) AS order_count
FROM orders
GROUP BY warehouse_id
ORDER BY order_count DESC;
"""

result = execute_sql(query)

print(result)