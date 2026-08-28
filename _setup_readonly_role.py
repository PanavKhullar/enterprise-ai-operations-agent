"""
One-off script to create a read-only Postgres role for the SQL tool.
Run once, then delete this file.
"""
import sys
import psycopg2

print("connecting...", flush=True)
conn = psycopg2.connect(
    host="localhost",
    dbname="ops_db",
    user="ops_user",
    password="ops_password",
    connect_timeout=5,
)
print("connected", flush=True)
conn.autocommit = True
cur = conn.cursor()

cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'ops_readonly'")
exists = cur.fetchone()

if not exists:
    cur.execute("CREATE ROLE ops_readonly WITH LOGIN PASSWORD 'ops_readonly_password'")
    print("Created role ops_readonly")
else:
    print("Role ops_readonly already exists")

cur.execute("GRANT CONNECT ON DATABASE ops_db TO ops_readonly")
cur.execute("GRANT USAGE ON SCHEMA public TO ops_readonly")
cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO ops_readonly")
cur.execute(
    "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ops_readonly"
)

print("Granted read-only privileges to ops_readonly")

cur.close()
conn.close()
