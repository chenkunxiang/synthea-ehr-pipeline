#!/usr/bin/env python3
"""
End-to-end pipeline runner.
Usage:
    python run_pipeline.py              # 200 patients (default)
    python run_pipeline.py --patients 500
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import generate_data
import parse_fhir
import data_quality
import load_to_sqlite
import analytics


def main():
    parser = argparse.ArgumentParser(description="Synthea EHR Data Pipeline")
    parser.add_argument("--patients", type=int, default=200, help="Number of synthetic patients")
    parser.add_argument("--skip-generate", action="store_true", help="Skip data generation step")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("SYNTHEA EHR DATA PIPELINE")
    print("=" * 60)

    if not args.skip_generate:
        print("\n[1/4] Generating synthetic FHIR data...")
        generate_data.main(args.patients)
    else:
        print("\n[1/4] Skipping data generation (--skip-generate)")

    print("\n[2/4] Parsing FHIR bundles → parquet...")
    parse_fhir.main()

    print("\n[3/4] Running data quality checks...")
    data_quality.main()

    print("\n[4/4] Loading to SQLite warehouse...")
    load_to_sqlite.main()

    print("\n[5/5] Running analytics...")
    analytics.main()

    print("\n" + "=" * 60)
    print("Pipeline complete.")
    print("  Database:       data/ehr_warehouse.db")
    print("  Quality report: data/quality_reports/quality_report.json")
    print("  Processed data: data/processed/*.parquet")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
