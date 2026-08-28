from app.agent.sql_generator import generate_sql


question = "Why are SLA breaches increasing from the past week?"

step = "Compare SLA breaches in the recent 7 days with the previous 7 days."

sql = generate_sql(question, step)

print("\nGenerated SQL:\n")
print(sql)