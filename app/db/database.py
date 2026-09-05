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

# Plain psycopg (v3) DSN — no SQLAlchemy driver prefix — used by
# PostgresSaver (LangGraph checkpointing) which talks to psycopg directly.
CHECKPOINTER_DATABASE_URL = (
    "postgresql://ops_user:ops_password@localhost:5432/ops_db"
)


class Base(DeclarativeBase):
    pass


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

# pool_size/max_overflow raised above SQLAlchemy's defaults (5/10) because
# investigator_node now runs investigation steps concurrently
# (asyncio.gather + asyncio.to_thread over execute_sql). With the default
# pool, a plan with more concurrent steps than available connections would
# have some steps block waiting on a connection instead of actually
# running in parallel, silently limiting the concurrency win.
readonly_engine = create_engine(
    READONLY_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)