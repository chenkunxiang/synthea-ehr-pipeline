"""
Run analytical queries against the EHR warehouse and print key findings.
This is the "story" layer — surface insights for a portfolio write-up.
"""
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent.parent / "data" / "ehr_warehouse.db"


def get_conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError("Run load_to_sqlite.py first.")
    return sqlite3.connect(DB_PATH)


def condition_prevalence(conn) -> pd.DataFrame:
    return pd.read_sql_query(
        """
        SELECT condition_display,
               COUNT(DISTINCT patient_id) AS patients_affected,
               ROUND(COUNT(DISTINCT patient_id) * 100.0 /
                     (SELECT COUNT(*) FROM patients), 1) AS prevalence_pct
        FROM conditions
        WHERE condition_display IS NOT NULL
        GROUP BY condition_display
        ORDER BY patients_affected DESC
        LIMIT 10
        """,
        conn,
    )


def encounter_volume_by_year(conn) -> pd.DataFrame:
    return pd.read_sql_query(
        """
        SELECT SUBSTR(encounter_start, 1, 4) AS year,
               encounter_class,
               COUNT(*) AS encounter_count
        FROM encounters
        WHERE encounter_start IS NOT NULL
        GROUP BY year, encounter_class
        ORDER BY year, encounter_count DESC
        """,
        conn,
    )


def avg_labs_by_condition(conn) -> pd.DataFrame:
    """Average A1c and Glucose for patients with Diabetes vs. without."""
    return pd.read_sql_query(
        """
        SELECT
            CASE WHEN c.patient_id IS NOT NULL THEN 'Diabetic' ELSE 'Non-diabetic' END AS group_,
            o.lab_display,
            ROUND(AVG(o.value), 2) AS avg_value,
            o.unit,
            COUNT(*) AS n
        FROM observations o
        LEFT JOIN (
            SELECT DISTINCT patient_id FROM conditions
            WHERE condition_display LIKE '%Diabetes%'
        ) c ON o.patient_id = c.patient_id
        WHERE o.lab_display IN ('Hemoglobin A1c', 'Glucose')
        GROUP BY group_, o.lab_display, o.unit
        ORDER BY o.lab_display, group_
        """,
        conn,
    )


def encounter_rate_by_condition(conn) -> pd.DataFrame:
    return pd.read_sql_query(
        """
        SELECT c.condition_display,
               ROUND(AVG(enc_counts.n_encounters), 2) AS avg_encounters_per_patient
        FROM conditions c
        JOIN (
            SELECT patient_id, COUNT(*) AS n_encounters
            FROM encounters
            GROUP BY patient_id
        ) enc_counts ON c.patient_id = enc_counts.patient_id
        GROUP BY c.condition_display
        ORDER BY avg_encounters_per_patient DESC
        LIMIT 8
        """,
        conn,
    )


def demographic_breakdown(conn) -> pd.DataFrame:
    return pd.read_sql_query(
        """
        SELECT race,
               gender,
               COUNT(*) AS n,
               ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM patients), 1) AS pct
        FROM patients
        GROUP BY race, gender
        ORDER BY n DESC
        """,
        conn,
    )


def main():
    conn = get_conn()

    print("\n=== Top 10 Condition Prevalence ===")
    print(condition_prevalence(conn).to_string(index=False))

    print("\n=== Encounter Volume by Year & Class ===")
    pivot = (
        encounter_volume_by_year(conn)
        .pivot_table(index="year", columns="encounter_class", values="encounter_count", fill_value=0)
    )
    print(pivot.to_string())

    print("\n=== Avg Labs: Diabetic vs Non-diabetic ===")
    print(avg_labs_by_condition(conn).to_string(index=False))

    print("\n=== Avg Encounter Rate by Condition ===")
    print(encounter_rate_by_condition(conn).to_string(index=False))

    print("\n=== Patient Demographic Breakdown ===")
    print(demographic_breakdown(conn).to_string(index=False))

    conn.close()


if __name__ == "__main__":
    main()
