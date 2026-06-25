-- Sample analytical queries for portfolio demonstration

-- 1. Condition prevalence across patient population
SELECT
    condition_display,
    COUNT(DISTINCT patient_id) AS patients_affected,
    ROUND(COUNT(DISTINCT patient_id) * 100.0 / (SELECT COUNT(*) FROM patients), 1) AS prevalence_pct
FROM conditions
WHERE condition_display IS NOT NULL
GROUP BY condition_display
ORDER BY patients_affected DESC;

-- 2. Emergency utilization rate by year
SELECT
    SUBSTR(encounter_start, 1, 4) AS year,
    COUNT(*) FILTER (WHERE encounter_class = 'emergency') AS ed_visits,
    COUNT(*) AS total_encounters,
    ROUND(COUNT(*) FILTER (WHERE encounter_class = 'emergency') * 100.0 / COUNT(*), 1) AS ed_rate_pct
FROM encounters
WHERE encounter_start IS NOT NULL
GROUP BY year
ORDER BY year;

-- 3. Patients with diabetes and their average A1c
SELECT
    ROUND(AVG(o.value), 2) AS avg_a1c,
    ROUND(MIN(o.value), 2) AS min_a1c,
    ROUND(MAX(o.value), 2) AS max_a1c,
    COUNT(DISTINCT o.patient_id) AS diabetic_patients_with_a1c
FROM observations o
JOIN v_diabetes_cohort d ON o.patient_id = d.patient_id
WHERE o.loinc_code = '4548-4';

-- 4. High-utilizer patients (top 10% by encounter count)
WITH enc_counts AS (
    SELECT patient_id, COUNT(*) AS n_encounters
    FROM encounters
    GROUP BY patient_id
),
pct90 AS (
    SELECT PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY n_encounters) AS threshold
    FROM enc_counts
)
SELECT e.patient_id, e.n_encounters, p.gender, p.race
FROM enc_counts e
JOIN patients p ON e.patient_id = p.patient_id
CROSS JOIN pct90
WHERE e.n_encounters >= pct90.threshold
ORDER BY e.n_encounters DESC
LIMIT 20;

-- 5. Lab result completeness by encounter type
SELECT
    enc.encounter_class,
    COUNT(DISTINCT enc.encounter_id) AS encounters,
    COUNT(DISTINCT obs.observation_id) AS labs_ordered,
    ROUND(COUNT(DISTINCT obs.observation_id) * 1.0 / COUNT(DISTINCT enc.encounter_id), 1) AS labs_per_encounter
FROM encounters enc
LEFT JOIN observations obs ON enc.encounter_id = obs.encounter_id
GROUP BY enc.encounter_class
ORDER BY labs_per_encounter DESC;
