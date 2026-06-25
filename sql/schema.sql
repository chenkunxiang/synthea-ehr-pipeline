-- EHR Warehouse Schema (FHIR-aligned flat tables)

CREATE TABLE IF NOT EXISTS patients (
    patient_id   TEXT PRIMARY KEY,
    gender       TEXT,
    birth_date   TEXT,   -- ISO 8601: YYYY-MM-DD
    race         TEXT,
    postal_code  TEXT
);

CREATE TABLE IF NOT EXISTS conditions (
    condition_id      TEXT PRIMARY KEY,
    patient_id        TEXT NOT NULL REFERENCES patients(patient_id),
    snomed_code       TEXT,
    condition_display TEXT,
    onset_date        TEXT,   -- YYYY-MM-DD
    clinical_status   TEXT    -- active | resolved | inactive
);

CREATE TABLE IF NOT EXISTS encounters (
    encounter_id    TEXT PRIMARY KEY,
    patient_id      TEXT NOT NULL REFERENCES patients(patient_id),
    encounter_class TEXT,   -- ambulatory | emergency | inpatient | wellness
    encounter_start TEXT,   -- YYYY-MM-DD
    status          TEXT    -- finished | in-progress | etc.
);

CREATE TABLE IF NOT EXISTS observations (
    observation_id TEXT PRIMARY KEY,
    patient_id     TEXT NOT NULL REFERENCES patients(patient_id),
    encounter_id   TEXT REFERENCES encounters(encounter_id),
    loinc_code     TEXT,
    lab_display    TEXT,
    value          REAL,
    unit           TEXT,
    effective_date TEXT,   -- YYYY-MM-DD
    status         TEXT    -- final | preliminary | etc.
);

CREATE INDEX IF NOT EXISTS idx_conditions_patient ON conditions(patient_id);
CREATE INDEX IF NOT EXISTS idx_encounters_patient ON encounters(patient_id);
CREATE INDEX IF NOT EXISTS idx_observations_patient ON observations(patient_id);
CREATE INDEX IF NOT EXISTS idx_observations_encounter ON observations(encounter_id);
CREATE INDEX IF NOT EXISTS idx_observations_loinc ON observations(loinc_code);
