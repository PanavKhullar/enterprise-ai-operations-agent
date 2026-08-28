from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = (
    "postgresql+psycopg2://"
    "ops_user:ops_password@localhost:5432/ops_db"
)

# Read-only role used by tools that execute LLM-generated SQL.
# Grants SELECT only (see _setup_readonly_role.py), so even if a
# generated query bypasses the app-level SELECT-only check, the
# database itself will reject any write/DDL statement.
READONLY_DATABASE_URL = (
    "postgresql+psycopg2://"
    "ops_readonly:ops_readonly_password@localhost:5432/ops_db"
)


class Base(DeclarativeBase):
    pass


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

readonly_engine = create_engine(
    READONLY_DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)