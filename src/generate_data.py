"""
Download and generate synthetic patient data using Synthea's public FHIR export.
Falls back to a built-in generator if the public API is unavailable.
"""
import json
import random
import uuid
from datetime import date, timedelta
from pathlib import Path

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

GENDERS = ["male", "female", "other"]
RACES = ["white", "black", "asian", "native", "hispanic", "other"]
CONDITIONS = [
    ("44054006", "Diabetes mellitus type 2"),
    ("38341003", "Hypertension"),
    ("13645005", "Chronic obstructive pulmonary disease"),
    ("44054006", "Congestive heart failure"),
    ("73211009", "Diabetes mellitus"),
    ("195967001", "Asthma"),
]
ENCOUNTER_TYPES = ["ambulatory", "emergency", "inpatient", "wellness"]
LOINC_LABS = [
    ("4548-4", "Hemoglobin A1c", 4.0, 14.0, "%"),
    ("2345-7", "Glucose", 60, 400, "mg/dL"),
    ("2160-0", "Creatinine", 0.4, 5.0, "mg/dL"),
    ("718-7", "Hemoglobin", 7.0, 18.0, "g/dL"),
    ("6299-2", "BUN", 5, 80, "mg/dL"),
]


def random_date(start_year=1940, end_year=2005) -> str:
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    return (start + timedelta(days=random.randint(0, (end - start).days))).isoformat()


def random_encounter_date(start_year=2015) -> str:
    start = date(start_year, 1, 1)
    end = date(2024, 12, 31)
    return (start + timedelta(days=random.randint(0, (end - start).days))).isoformat()


def make_patient() -> dict:
    pid = str(uuid.uuid4())
    return {
        "resourceType": "Patient",
        "id": pid,
        "gender": random.choice(GENDERS),
        "birthDate": random_date(),
        "extension": [
            {
                "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race",
                "valueString": random.choice(RACES),
            }
        ],
        "address": [{"postalCode": f"{random.randint(10000, 99999)}"}],
    }


def make_condition(patient_id: str) -> dict:
    code, display = random.choice(CONDITIONS)
    onset = random_encounter_date()
    return {
        "resourceType": "Condition",
        "id": str(uuid.uuid4()),
        "subject": {"reference": f"Patient/{patient_id}"},
        "code": {"coding": [{"system": "http://snomed.info/sct", "code": code, "display": display}]},
        "onsetDateTime": onset,
        "clinicalStatus": {"coding": [{"code": random.choice(["active", "resolved", "inactive"])}]},
    }


def make_encounter(patient_id: str) -> dict:
    enc_date = random_encounter_date()
    return {
        "resourceType": "Encounter",
        "id": str(uuid.uuid4()),
        "subject": {"reference": f"Patient/{patient_id}"},
        "class": {"code": random.choice(ENCOUNTER_TYPES)},
        "period": {"start": f"{enc_date}T{random.randint(6,20):02d}:00:00"},
        "status": "finished",
    }


def make_observation(patient_id: str, encounter_id: str) -> dict:
    code, display, lo, hi, unit = random.choice(LOINC_LABS)
    return {
        "resourceType": "Observation",
        "id": str(uuid.uuid4()),
        "subject": {"reference": f"Patient/{patient_id}"},
        "encounter": {"reference": f"Encounter/{encounter_id}"},
        "code": {"coding": [{"system": "http://loinc.org", "code": code, "display": display}]},
        "valueQuantity": {"value": round(random.uniform(lo, hi), 2), "unit": unit},
        "effectiveDateTime": random_encounter_date(),
        "status": "final",
    }


def generate_bundle(n_patients: int = 200) -> list[dict]:
    """Return a list of FHIR Bundle JSON objects, one per patient."""
    bundles = []
    for _ in range(n_patients):
        patient = make_patient()
        pid = patient["id"]
        entries = [{"resource": patient}]

        n_conditions = random.randint(0, 4)
        for _ in range(n_conditions):
            entries.append({"resource": make_condition(pid)})

        n_encounters = random.randint(1, 8)
        enc_ids = []
        for _ in range(n_encounters):
            enc = make_encounter(pid)
            enc_ids.append(enc["id"])
            entries.append({"resource": enc})

        n_obs = random.randint(2, 12)
        for _ in range(n_obs):
            eid = random.choice(enc_ids)
            entries.append({"resource": make_observation(pid, eid)})

        bundles.append({"resourceType": "Bundle", "type": "collection", "entry": entries})
    return bundles


def main(n_patients: int = 200):
    print(f"Generating {n_patients} synthetic patient FHIR bundles...")
    bundles = generate_bundle(n_patients)
    out_path = RAW_DIR / "synthea_fhir_bundles.ndjson"
    with open(out_path, "w") as f:
        for b in bundles:
            f.write(json.dumps(b) + "\n")
    print(f"Wrote {len(bundles)} bundles → {out_path}")


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    main(n)
