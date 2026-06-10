USE food_security_risk;

-- Secondary indexes live inside the CREATE TABLE statements so the whole
-- script stays idempotent (MySQL has no CREATE INDEX IF NOT EXISTS). The
-- primary keys already cover (country_code, year) lookups; the extra indexes
-- support cross-country scans by year and crop-group filters.

CREATE TABLE IF NOT EXISTS raw_rainfall_country_year (
    country_code VARCHAR(3) NOT NULL,
    country_name VARCHAR(128) NOT NULL,
    year INT NOT NULL,
    rainfall_mm DOUBLE NULL,
    rainfall_baseline_mm DOUBLE NULL,
    rainfall_anomaly_pct DOUBLE NULL,
    source_dataset VARCHAR(128) DEFAULT 'synthetic',
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (country_code, year),
    INDEX idx_rainfall_year (year)
);

CREATE TABLE IF NOT EXISTS raw_crop_production_country_year (
    country_code VARCHAR(3) NOT NULL,
    country_name VARCHAR(128) NOT NULL,
    year INT NOT NULL,
    crop_group VARCHAR(64) NOT NULL,
    production_tonnes DOUBLE NULL,
    production_baseline_tonnes DOUBLE NULL,
    production_anomaly_pct DOUBLE NULL,
    source_dataset VARCHAR(128) DEFAULT 'synthetic',
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (country_code, year, crop_group),
    INDEX idx_crop_year (year),
    INDEX idx_crop_group (crop_group)
);

CREATE TABLE IF NOT EXISTS raw_food_affordability_country_year (
    country_code VARCHAR(3) NOT NULL,
    country_name VARCHAR(128) NOT NULL,
    year INT NOT NULL,
    healthy_diet_cost_ppp DOUBLE NULL,
    affordability_ratio DOUBLE NULL,
    affordability_baseline_ratio DOUBLE NULL,
    affordability_anomaly_pct DOUBLE NULL,
    source_dataset VARCHAR(128) DEFAULT 'synthetic',
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (country_code, year),
    INDEX idx_affordability_year (year)
);
