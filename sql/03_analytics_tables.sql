USE food_security_risk;

DROP TABLE IF EXISTS mart_country_year_food_security;

CREATE TABLE mart_country_year_food_security AS
SELECT
    r.country_code,
    r.country_name,
    r.year,
    r.rainfall_mm,
    r.rainfall_baseline_mm,
    r.rainfall_anomaly_pct,
    c.crop_group,
    c.production_tonnes,
    c.production_baseline_tonnes,
    c.production_anomaly_pct,
    a.healthy_diet_cost_ppp,
    a.affordability_ratio,
    a.affordability_baseline_ratio,
    a.affordability_anomaly_pct,
    CASE
        WHEN r.rainfall_anomaly_pct < -20 THEN 1
        ELSE 0
    END AS severe_rainfall_deficit_flag,
    CASE
        WHEN c.production_anomaly_pct < -15 THEN 1
        ELSE 0
    END AS severe_crop_decline_flag,
    CASE
        WHEN a.affordability_anomaly_pct > 15 THEN 1
        ELSE 0
    END AS severe_affordability_pressure_flag
FROM raw_rainfall_country_year r
INNER JOIN raw_crop_production_country_year c
    ON r.country_code = c.country_code
   AND r.year = c.year
INNER JOIN raw_food_affordability_country_year a
    ON r.country_code = a.country_code
   AND r.year = a.year;

ALTER TABLE mart_country_year_food_security
    ADD INDEX idx_mart_country_year (country_code, year),
    ADD INDEX idx_mart_year (year),
    ADD INDEX idx_mart_crop_group (crop_group);
