from app.agent.sql_generator import generate_sql


question = " Which warehouse had the highest average delay last week?"

step = "Compare SLA breaches in the recent 7 days with the previous 7 days."

sql = generate_sql(question, step)

print("\nGenerated SQL:\n")
print(sql)