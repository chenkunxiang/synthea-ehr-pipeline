"""
Data quality checks on the processed FHIR tables.
Produces a JSON report and a human-readable summary.
"""
import json
from datetime import date
from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
REPORT_DIR = Path(__file__).parent.parent / "data" / "quality_reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# (table, column, valid_values_or_None_for_range, min_val, max_val)
RANGE_CHECKS = {
    "observations": [
        ("Hemoglobin A1c", 4.0, 14.0),
        ("Glucose", 60, 400),
        ("Creatinine", 0.4, 5.0),
        ("Hemoglobin", 7.0, 18.0),
        ("BUN", 5, 80),
    ]
}

COMPLETENESS_TARGETS = {
    "patients": ["patient_id", "gender", "birth_date"],
    "conditions": ["patient_id", "snomed_code", "onset_date"],
    "encounters": ["patient_id", "encounter_class", "encounter_start"],
    "observations": ["patient_id", "loinc_code", "value", "effective_date"],
}


def load_all() -> dict[str, pd.DataFrame]:
    dfs = {}
    for p in PROCESSED_DIR.glob("*.parquet"):
        dfs[p.stem] = pd.read_parquet(p)
    return dfs


def check_completeness(dfs: dict[str, pd.DataFrame]) -> dict:
    results = {}
    for table, cols in COMPLETENESS_TARGETS.items():
        df = dfs.get(table, pd.DataFrame())
        table_result = {}
        for col in cols:
            if col not in df.columns:
                table_result[col] = {"null_count": None, "null_pct": None, "status": "MISSING_COLUMN"}
                continue
            null_n = int(df[col].isna().sum())
            null_pct = round(null_n / max(len(df), 1) * 100, 2)
            table_result[col] = {
                "null_count": null_n,
                "null_pct": null_pct,
                "status": "PASS" if null_pct < 5 else "WARN" if null_pct < 20 else "FAIL",
            }
        results[table] = table_result
    return results


def check_referential_integrity(dfs: dict[str, pd.DataFrame]) -> dict:
    results = {}
    patient_ids = set(dfs.get("patients", pd.DataFrame()).get("patient_id", pd.Series()))

    for table in ["conditions", "encounters", "observations"]:
        df = dfs.get(table, pd.DataFrame())
        if "patient_id" not in df.columns:
            results[table] = {"status": "MISSING_COLUMN"}
            continue
        orphan_n = int((~df["patient_id"].isin(patient_ids)).sum())
        orphan_pct = round(orphan_n / max(len(df), 1) * 100, 2)
        results[table] = {
            "orphan_records": orphan_n,
            "orphan_pct": orphan_pct,
            "status": "PASS" if orphan_pct == 0 else "WARN" if orphan_pct < 1 else "FAIL",
        }
    return results


def check_value_ranges(dfs: dict[str, pd.DataFrame]) -> dict:
    results = {}
    obs = dfs.get("observations", pd.DataFrame())
    if obs.empty or "lab_display" not in obs.columns:
        return {}

    for display, lo, hi in RANGE_CHECKS.get("observations", []):
        mask = obs["lab_display"].str.contains(display, case=False, na=False)
        sub = obs[mask]
        if sub.empty:
            continue
        out_of_range = int(((sub["value"] < lo) | (sub["value"] > hi)).sum())
        oor_pct = round(out_of_range / max(len(sub), 1) * 100, 2)
        results[display] = {
            "expected_range": f"{lo}–{hi}",
            "n_checked": len(sub),
            "out_of_range": out_of_range,
            "oor_pct": oor_pct,
            "status": "PASS" if oor_pct == 0 else "WARN" if oor_pct < 2 else "FAIL",
        }
    return results


def check_duplicate_keys(dfs: dict[str, pd.DataFrame]) -> dict:
    id_cols = {
        "patients": "patient_id",
        "conditions": "condition_id",
        "encounters": "encounter_id",
        "observations": "observation_id",
    }
    results = {}
    for table, col in id_cols.items():
        df = dfs.get(table, pd.DataFrame())
        if col not in df.columns:
            results[table] = {"status": "MISSING_COLUMN"}
            continue
        dup_n = int(df[col].duplicated().sum())
        results[table] = {
            "duplicate_ids": dup_n,
            "status": "PASS" if dup_n == 0 else "FAIL",
        }
    return results


def build_report(dfs: dict[str, pd.DataFrame]) -> dict:
    return {
        "generated_at": date.today().isoformat(),
        "row_counts": {k: len(v) for k, v in dfs.items()},
        "completeness": check_completeness(dfs),
        "referential_integrity": check_referential_integrity(dfs),
        "value_ranges": check_value_ranges(dfs),
        "duplicate_keys": check_duplicate_keys(dfs),
    }


def print_summary(report: dict):
    print(f"\n{'='*60}")
    print("DATA QUALITY REPORT")
    print(f"Generated: {report['generated_at']}")
    print(f"{'='*60}\n")

    print("Row Counts:")
    for t, n in report["row_counts"].items():
        print(f"  {t:<20} {n:>8,}")

    print("\nCompleteness:")
    for table, cols in report["completeness"].items():
        for col, info in cols.items():
            status = info["status"]
            pct = info.get("null_pct", "N/A")
            flag = "" if status == "PASS" else " ⚠" if status == "WARN" else " ✗"
            print(f"  {table}.{col:<30} null={pct}%  [{status}]{flag}")

    print("\nReferential Integrity:")
    for table, info in report["referential_integrity"].items():
        status = info["status"]
        flag = "" if status == "PASS" else " ✗"
        print(f"  {table:<25} orphans={info.get('orphan_pct', '?')}%  [{status}]{flag}")

    print("\nValue Range Checks:")
    for lab, info in report["value_ranges"].items():
        status = info["status"]
        flag = "" if status == "PASS" else " ⚠"
        print(f"  {lab:<35} oor={info['oor_pct']}%  [{status}]{flag}")

    print("\nDuplicate Key Checks:")
    for table, info in report["duplicate_keys"].items():
        status = info["status"]
        flag = "" if status == "PASS" else " ✗"
        print(f"  {table:<25} dupes={info.get('duplicate_ids', '?')}  [{status}]{flag}")

    all_statuses = []
    for section in ["completeness", "referential_integrity", "value_ranges", "duplicate_keys"]:
        for item in report[section].values():
            if isinstance(item, dict):
                s = item.get("status")
                if s:
                    all_statuses.append(s)
    fails = all_statuses.count("FAIL")
    warns = all_statuses.count("WARN")
    print(f"\nOverall: {fails} FAIL, {warns} WARN, {all_statuses.count('PASS')} PASS\n")


def main():
    dfs = load_all()
    if not dfs:
        raise FileNotFoundError("No processed parquet files found. Run parse_fhir.py first.")
    report = build_report(dfs)
    out = REPORT_DIR / "quality_report.json"
    out.write_text(json.dumps(report, indent=2))
    print_summary(report)
    print(f"Full report saved → {out}")
    return report


if __name__ == "__main__":
    main()
