-- Analytical views for the EHR warehouse

DROP VIEW IF EXISTS v_patient_summary;
CREATE VIEW v_patient_summary AS
SELECT
    p.patient_id,
    p.gender,
    p.birth_date,
    p.race,
    p.postal_code,
    COUNT(DISTINCT c.condition_id)  AS condition_count,
    COUNT(DISTINCT e.encounter_id)  AS encounter_count,
    COUNT(DISTINCT o.observation_id) AS lab_count
FROM patients p
LEFT JOIN conditions  c ON p.patient_id = c.patient_id
LEFT JOIN encounters  e ON p.patient_id = e.patient_id
LEFT JOIN observations o ON p.patient_id = o.patient_id
GROUP BY p.patient_id;

DROP VIEW IF EXISTS v_diabetes_cohort;
CREATE VIEW v_diabetes_cohort AS
SELECT DISTINCT patient_id
FROM conditions
WHERE condition_display LIKE '%Diabetes%';

DROP VIEW IF EXISTS v_a1c_trend;
CREATE VIEW v_a1c_trend AS
SELECT
    o.patient_id,
    o.effective_date,
    o.value AS a1c_value,
    CASE WHEN d.patient_id IS NOT NULL THEN 1 ELSE 0 END AS is_diabetic
FROM observations o
LEFT JOIN v_diabetes_cohort d ON o.patient_id = d.patient_id
WHERE o.loinc_code = '4548-4'
ORDER BY o.patient_id, o.effective_date;
