USE food_security_risk;

CREATE TABLE IF NOT EXISTS dim_country (
    iso3 VARCHAR(3) NOT NULL,
    iso2 VARCHAR(2) NOT NULL,
    m49 INT NOT NULL,
    country_name VARCHAR(128) NOT NULL,
    region VARCHAR(64) NOT NULL,
    PRIMARY KEY (iso3)
);

CREATE TABLE IF NOT EXISTS country_source_mapping (
    source VARCHAR(64) NOT NULL,
    source_name VARCHAR(128) NOT NULL,
    iso3 VARCHAR(3) NULL,
    country_name VARCHAR(128) NULL,
    quality_flag VARCHAR(16) NOT NULL,
    note VARCHAR(255) NULL,
    candidates VARCHAR(128) NULL,
    mapped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source, source_name)
);

CREATE OR REPLACE VIEW country_mapping_quality_report AS
SELECT
    source,
    quality_flag,
    COUNT(*) AS name_count
FROM country_source_mapping
GROUP BY source, quality_flag;
