import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


load_dotenv()


def read_sql(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Run a SQL migration file against a target database.")
    parser.add_argument("migration", help="Migration filename inside backend/migrations")
    parser.add_argument(
        "--database-url",
        dest="database_url",
        default=None,
        help="Override database URL. Defaults to MIGRATION_DATABASE_URL or DATABASE_URL.",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    migration_path = base_dir / "migrations" / args.migration
    if not migration_path.exists():
        raise SystemExit(f"Migration file not found: {migration_path}")

    database_url = args.database_url or os.getenv("MIGRATION_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("No database URL provided.")

    engine = create_engine(database_url)
    sql = read_sql(migration_path)

    with engine.begin() as conn:
        conn.execute(text(sql))

    print(f"Applied {migration_path.name} to {database_url}")


if __name__ == "__main__":
    main()
