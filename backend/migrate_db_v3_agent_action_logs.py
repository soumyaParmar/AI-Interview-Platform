import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


load_dotenv()

DATABASE_URL = os.getenv("MIGRATION_DATABASE_URL") or os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL not found")
    sys.exit(1)

engine = create_engine(DATABASE_URL)


def run_sql(conn, statement: str, label: str):
    try:
        conn.execute(text(statement))
        conn.commit()
        print(f"SUCCESS: {label}")
    except Exception as exc:
        conn.rollback()
        message = str(exc).lower()
        if "already exists" in message or "duplicate" in message:
            print(f"SKIP: {label} already exists")
        else:
            print(f"FAILURE: {label}: {exc}")


def run_migration():
    print("Starting agent action log migration...")
    print(f"Target database: {DATABASE_URL}")

    with engine.connect() as conn:
        if DATABASE_URL.startswith("sqlite"):
            run_sql(
                conn,
                """
                CREATE TABLE IF NOT EXISTS agent_action_logs (
                    id VARCHAR PRIMARY KEY,
                    session_id VARCHAR NOT NULL,
                    node_name VARCHAR(100),
                    action_type VARCHAR(100) NOT NULL,
                    summary TEXT,
                    payload JSON,
                    timestamp DATETIME,
                    FOREIGN KEY(session_id) REFERENCES interview_sessions (id)
                )
                """,
                "create agent_action_logs table",
            )
            run_sql(
                conn,
                "CREATE INDEX IF NOT EXISTS ix_agent_action_logs_session_id ON agent_action_logs (session_id)",
                "create agent_action_logs session_id index",
            )
            run_sql(
                conn,
                "CREATE INDEX IF NOT EXISTS ix_agent_action_logs_timestamp ON agent_action_logs (timestamp)",
                "create agent_action_logs timestamp index",
            )
        else:
            run_sql(
                conn,
                """
                CREATE TABLE IF NOT EXISTS agent_action_logs (
                    id VARCHAR PRIMARY KEY,
                    session_id VARCHAR NOT NULL REFERENCES interview_sessions(id),
                    node_name VARCHAR(100),
                    action_type VARCHAR(100) NOT NULL,
                    summary TEXT,
                    payload JSONB,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                "create agent_action_logs table",
            )
            run_sql(
                conn,
                "CREATE INDEX IF NOT EXISTS ix_agent_action_logs_session_id ON agent_action_logs (session_id)",
                "create agent_action_logs session_id index",
            )
            run_sql(
                conn,
                "CREATE INDEX IF NOT EXISTS ix_agent_action_logs_timestamp ON agent_action_logs (timestamp)",
                "create agent_action_logs timestamp index",
            )

    print("Agent action log migration complete.")


if __name__ == "__main__":
    run_migration()
