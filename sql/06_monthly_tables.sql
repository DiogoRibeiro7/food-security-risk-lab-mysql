USE food_security_risk;

CREATE TABLE IF NOT EXISTS raw_rainfall_country_month (
    country_code VARCHAR(3) NOT NULL,
    country_name VARCHAR(128) NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    rainfall_mm DOUBLE NULL,
    source_dataset VARCHAR(128) DEFAULT 'synthetic',
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (country_code, year, month)
);

CREATE INDEX idx_raw_rainfall_month_country
    ON raw_rainfall_country_month (country_code, year, month);
