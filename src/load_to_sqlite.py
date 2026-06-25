"""
Load processed parquet files into a SQLite database, applying the DDL schema.
"""
import sqlite3
from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
SQL_DIR = Path(__file__).parent.parent / "sql"
DB_PATH = Path(__file__).parent.parent / "data" / "ehr_warehouse.db"


def create_schema(conn: sqlite3.Connection):
    schema_file = SQL_DIR / "schema.sql"
    if schema_file.exists():
        conn.executescript(schema_file.read_text())
    conn.commit()


def load_table(conn: sqlite3.Connection, name: str, df: pd.DataFrame):
    df.to_sql(name, conn, if_exists="replace", index=False)
    print(f"  Loaded {name}: {len(df):,} rows")


def main():
    if not any(PROCESSED_DIR.glob("*.parquet")):
        raise FileNotFoundError("Run parse_fhir.py first.")

    conn = sqlite3.connect(DB_PATH)
    print(f"Connected to {DB_PATH}")

    create_schema(conn)

    for pq in sorted(PROCESSED_DIR.glob("*.parquet")):
        df = pd.read_parquet(pq)
        load_table(conn, pq.stem, df)

    # Create analytical views
    views_file = SQL_DIR / "views.sql"
    if views_file.exists():
        conn.executescript(views_file.read_text())
        print("Created analytical views.")

    conn.close()
    print(f"\nDatabase ready: {DB_PATH}")


if __name__ == "__main__":
    main()
