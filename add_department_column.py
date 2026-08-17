"""
Migration: add columns from the latest Candidate / InterviewScore model changes.

Fixes: sqlite3.OperationalError: no such column: candidates.department
(and the matching gap for interview_scores.role_assessed / .recommendation,
which are NOT NULL in the model and would hit the same error once code
starts reading/writing them)

Usage:
    python add_department_column.py --db /path/to/your.db

If --db is omitted, it tries to read DATABASE_URL from your .env / environment
(sqlite:///path/to.db format) the same way the app does.

Safe to run multiple times — it checks whether each column already exists
before doing anything.
"""

import argparse
import os
import sqlite3
import sys

DEFAULT_DEPARTMENT = "AI / ML"  # matches the value the app currently filters by

# interview_scores.role_assessed / .recommendation are declared NOT NULL in
# the model with no default, so SQLite requires a DEFAULT at ADD COLUMN time
# (see column_specs below). role_assessed defaults to "AI/ML Engineer (L1)"
# to match the rubric's own default option; recommendation has no sensible
# guessable value for historical rows, so it defaults to "" as a placeholder
# — flag/update these manually if that matters for old records.
DEFAULT_ROLE_ASSESSED = "AI/ML Engineer (L1)"
DEFAULT_RECOMMENDATION = ""

# (table, column, sql_type, not_null, default_sql_literal)
COLUMN_SPECS = [
    ("candidates", "department", "VARCHAR", False, None),
    ("interview_scores", "role_assessed", "VARCHAR", True, DEFAULT_ROLE_ASSESSED),
    ("interview_scores", "recommendation", "VARCHAR", True, DEFAULT_RECOMMENDATION),
]


def resolve_db_path(cli_path: str | None) -> str:
    if cli_path:
        return cli_path

    db_url = os.environ.get("DATABASE_URL", "")
    if db_url.startswith("sqlite:///"):
        return db_url.replace("sqlite:///", "", 1)

    print(
        "Could not determine DB path. Pass it explicitly, e.g.:\n"
        "  python add_department_column.py --db app.db",
        file=sys.stderr,
    )
    sys.exit(1)


def column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def migrate(db_path: str) -> None:
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    try:
        for table, column, sql_type, not_null, default in COLUMN_SPECS:
            if column_exists(cur, table, column):
                print(f"Column '{column}' already exists on '{table}' — skipping add.")
                continue

            print(f"Adding '{column}' column to '{table}'...")
            ddl = f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"
            if not_null:
                # SQLite requires a DEFAULT to add a NOT NULL column to a
                # non-empty table, so this branch always supplies one.
                ddl += f" NOT NULL DEFAULT '{default}'"
            cur.execute(ddl)
            conn.commit()
            print("Column added.")

        # department stays nullable in the model, so it's backfilled
        # separately rather than via an ADD-time DEFAULT.
        cur.execute(
            "UPDATE candidates SET department = ? WHERE department IS NULL OR department = ''",
            (DEFAULT_DEPARTMENT,),
        )
        conn.commit()
        print(f"Backfilled {cur.rowcount} existing candidate(s) with department = '{DEFAULT_DEPARTMENT}'.")

    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", help="Path to the sqlite .db file", default=None)
    args = parser.parse_args()

    db_path = resolve_db_path(args.db)
    migrate(db_path)