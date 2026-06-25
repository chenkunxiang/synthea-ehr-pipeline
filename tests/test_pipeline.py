"""
Unit tests for FHIR parsing and data quality checks.
Run with: python -m pytest tests/ -v
"""
import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

# Allow imports from src/
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from parse_fhir import parse_bundles, _ref_id
from data_quality import (
    check_completeness,
    check_referential_integrity,
    check_duplicate_keys,
    check_value_ranges,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _write_ndjson(bundles: list[dict], path: Path):
    with open(path, "w") as f:
        for b in bundles:
            f.write(json.dumps(b) + "\n")


def _minimal_bundle(patient_id="p1") -> dict:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": patient_id,
                    "gender": "female",
                    "birthDate": "1985-04-12",
                    "extension": [
                        {
                            "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race",
                            "valueString": "asian",
                        }
                    ],
                    "address": [{"postalCode": "10001"}],
                }
            },
            {
                "resource": {
                    "resourceType": "Condition",
                    "id": "c1",
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "code": {
                        "coding": [
                            {"system": "http://snomed.info/sct", "code": "44054006", "display": "Diabetes mellitus type 2"}
                        ]
                    },
                    "onsetDateTime": "2020-01-15",
                    "clinicalStatus": {"coding": [{"code": "active"}]},
                }
            },
            {
                "resource": {
                    "resourceType": "Encounter",
                    "id": "e1",
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "class": {"code": "ambulatory"},
                    "period": {"start": "2021-06-01T09:00:00"},
                    "status": "finished",
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "o1",
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "encounter": {"reference": "Encounter/e1"},
                    "code": {
                        "coding": [{"system": "http://loinc.org", "code": "4548-4", "display": "Hemoglobin A1c"}]
                    },
                    "valueQuantity": {"value": 7.2, "unit": "%"},
                    "effectiveDateTime": "2021-06-01",
                    "status": "final",
                }
            },
        ],
    }


# ── parse_fhir tests ──────────────────────────────────────────────────────────

class TestRefId:
    def test_bare_id(self):
        assert _ref_id("Patient/abc-123") == "abc-123"

    def test_none(self):
        assert _ref_id(None) is None

    def test_no_slash(self):
        assert _ref_id("abc") == "abc"


class TestParseBundles:
    def test_counts(self, tmp_path):
        ndjson = tmp_path / "test.ndjson"
        _write_ndjson([_minimal_bundle()], ndjson)
        dfs = parse_bundles(ndjson)

        assert len(dfs["patients"]) == 1
        assert len(dfs["conditions"]) == 1
        assert len(dfs["encounters"]) == 1
        assert len(dfs["observations"]) == 1

    def test_patient_fields(self, tmp_path):
        ndjson = tmp_path / "test.ndjson"
        _write_ndjson([_minimal_bundle("p99")], ndjson)
        dfs = parse_bundles(ndjson)

        row = dfs["patients"].iloc[0]
        assert row["patient_id"] == "p99"
        assert row["gender"] == "female"
        assert row["race"] == "asian"

    def test_observation_value(self, tmp_path):
        ndjson = tmp_path / "test.ndjson"
        _write_ndjson([_minimal_bundle()], ndjson)
        dfs = parse_bundles(ndjson)

        obs = dfs["observations"].iloc[0]
        assert obs["value"] == pytest.approx(7.2)
        assert obs["loinc_code"] == "4548-4"

    def test_multiple_bundles(self, tmp_path):
        ndjson = tmp_path / "test.ndjson"
        _write_ndjson([_minimal_bundle("p1"), _minimal_bundle("p2")], ndjson)
        dfs = parse_bundles(ndjson)
        assert len(dfs["patients"]) == 2

    def test_empty_bundle(self, tmp_path):
        ndjson = tmp_path / "test.ndjson"
        _write_ndjson([{"resourceType": "Bundle", "type": "collection", "entry": []}], ndjson)
        dfs = parse_bundles(ndjson)
        assert len(dfs["patients"]) == 0


# ── data_quality tests ────────────────────────────────────────────────────────

def _make_dfs(n_patients=5):
    patients = pd.DataFrame(
        [{"patient_id": f"p{i}", "gender": "male", "birth_date": "1970-01-01", "race": "white", "postal_code": "10001"} for i in range(n_patients)]
    )
    conditions = pd.DataFrame(
        [{"condition_id": f"c{i}", "patient_id": f"p{i % n_patients}", "snomed_code": "44054006", "condition_display": "Diabetes", "onset_date": "2020-01-01", "clinical_status": "active"} for i in range(n_patients)]
    )
    encounters = pd.DataFrame(
        [{"encounter_id": f"e{i}", "patient_id": f"p{i % n_patients}", "encounter_class": "ambulatory", "encounter_start": "2021-01-01", "status": "finished"} for i in range(n_patients)]
    )
    observations = pd.DataFrame(
        [{"observation_id": f"o{i}", "patient_id": f"p{i % n_patients}", "encounter_id": f"e{i % n_patients}", "loinc_code": "4548-4", "lab_display": "Hemoglobin A1c", "value": 6.5 + i * 0.1, "unit": "%", "effective_date": "2021-01-01", "status": "final"} for i in range(n_patients)]
    )
    return {"patients": patients, "conditions": conditions, "encounters": encounters, "observations": observations}


class TestCompleteness:
    def test_no_nulls_pass(self):
        dfs = _make_dfs()
        result = check_completeness(dfs)
        for table_result in result.values():
            for col_result in table_result.values():
                assert col_result["status"] == "PASS"

    def test_null_column_fails(self):
        dfs = _make_dfs()
        dfs["patients"]["gender"] = None
        result = check_completeness(dfs)
        assert result["patients"]["gender"]["status"] == "FAIL"


class TestReferentialIntegrity:
    def test_clean_refs_pass(self):
        dfs = _make_dfs()
        result = check_referential_integrity(dfs)
        for v in result.values():
            assert v["status"] == "PASS"

    def test_orphan_detected(self):
        dfs = _make_dfs()
        orphan_row = pd.DataFrame([{
            "condition_id": "c_orphan",
            "patient_id": "p_nonexistent",
            "snomed_code": "111",
            "condition_display": "X",
            "onset_date": "2020-01-01",
            "clinical_status": "active",
        }])
        dfs["conditions"] = pd.concat([dfs["conditions"], orphan_row], ignore_index=True)
        result = check_referential_integrity(dfs)
        assert result["conditions"]["orphan_records"] >= 1


class TestDuplicateKeys:
    def test_no_dupes_pass(self):
        dfs = _make_dfs()
        result = check_duplicate_keys(dfs)
        for v in result.values():
            assert v["status"] == "PASS"

    def test_dupe_detected(self):
        dfs = _make_dfs()
        dfs["patients"] = pd.concat([dfs["patients"], dfs["patients"].iloc[[0]]], ignore_index=True)
        result = check_duplicate_keys(dfs)
        assert result["patients"]["status"] == "FAIL"
