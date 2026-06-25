"""
Parse FHIR R4 NDJSON bundles into flat pandas DataFrames.
Handles Patient, Condition, Encounter, and Observation resources.
"""
import json
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def _ref_id(ref: str | None) -> str | None:
    """Extract bare UUID from a FHIR reference like 'Patient/abc-123'."""
    if ref is None:
        return None
    return ref.split("/")[-1]


def parse_bundles(ndjson_path: Path) -> dict[str, list]:
    rows: dict[str, list] = {
        "patients": [],
        "conditions": [],
        "encounters": [],
        "observations": [],
    }

    with open(ndjson_path) as f:
        for line in f:
            bundle = json.loads(line)
            for entry in bundle.get("entry", []):
                res = entry.get("resource", {})
                rtype = res.get("resourceType")

                if rtype == "Patient":
                    race_ext = next(
                        (
                            e.get("valueString")
                            for e in res.get("extension", [])
                            if "race" in e.get("url", "")
                        ),
                        None,
                    )
                    rows["patients"].append(
                        {
                            "patient_id": res["id"],
                            "gender": res.get("gender"),
                            "birth_date": res.get("birthDate"),
                            "race": race_ext,
                            "postal_code": (res.get("address") or [{}])[0].get("postalCode"),
                        }
                    )

                elif rtype == "Condition":
                    coding = (res.get("code") or {}).get("coding") or [{}]
                    status_coding = (res.get("clinicalStatus") or {}).get("coding") or [{}]
                    rows["conditions"].append(
                        {
                            "condition_id": res["id"],
                            "patient_id": _ref_id(res.get("subject", {}).get("reference")),
                            "snomed_code": coding[0].get("code"),
                            "condition_display": coding[0].get("display"),
                            "onset_date": res.get("onsetDateTime", "")[:10] or None,
                            "clinical_status": status_coding[0].get("code"),
                        }
                    )

                elif rtype == "Encounter":
                    period = res.get("period") or {}
                    rows["encounters"].append(
                        {
                            "encounter_id": res["id"],
                            "patient_id": _ref_id(res.get("subject", {}).get("reference")),
                            "encounter_class": (res.get("class") or {}).get("code"),
                            "encounter_start": (period.get("start") or "")[:10] or None,
                            "status": res.get("status"),
                        }
                    )

                elif rtype == "Observation":
                    coding = (res.get("code") or {}).get("coding") or [{}]
                    vq = res.get("valueQuantity") or {}
                    rows["observations"].append(
                        {
                            "observation_id": res["id"],
                            "patient_id": _ref_id(res.get("subject", {}).get("reference")),
                            "encounter_id": _ref_id(
                                (res.get("encounter") or {}).get("reference")
                            ),
                            "loinc_code": coding[0].get("code"),
                            "lab_display": coding[0].get("display"),
                            "value": vq.get("value"),
                            "unit": vq.get("unit"),
                            "effective_date": (res.get("effectiveDateTime") or "")[:10] or None,
                            "status": res.get("status"),
                        }
                    )

    return {k: pd.DataFrame(v) for k, v in rows.items()}


def save_processed(dfs: dict[str, pd.DataFrame]):
    for name, df in dfs.items():
        out = PROCESSED_DIR / f"{name}.parquet"
        df.to_parquet(out, index=False)
        print(f"  {name}: {len(df):,} rows → {out.name}")


def main():
    src = RAW_DIR / "synthea_fhir_bundles.ndjson"
    if not src.exists():
        raise FileNotFoundError(f"Run generate_data.py first. Expected: {src}")

    print("Parsing FHIR bundles...")
    dfs = parse_bundles(src)
    print("Saving processed parquet files...")
    save_processed(dfs)
    print("Done.")
    return dfs


if __name__ == "__main__":
    main()
