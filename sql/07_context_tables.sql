USE food_security_risk;

-- FEWS NET / IPC-style humanitarian context. This is reference context, NOT a
-- ground-truth label: it is never used as a target for the risk score.
CREATE TABLE IF NOT EXISTS fewsnet_context (
    country_code VARCHAR(3) NOT NULL,
    country_name VARCHAR(128) NOT NULL,
    area_name VARCHAR(128) NULL,
    year INT NOT NULL,
    month INT NULL,
    ipc_phase INT NULL,
    ipc_phase_label VARCHAR(32) NULL,
    classification_type VARCHAR(16) NOT NULL,
    narrative TEXT NULL,
    source VARCHAR(128) DEFAULT 'fewsnet',
    as_of_date VARCHAR(32) NULL,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_fewsnet_context_country_period
    ON fewsnet_context (country_code, year, month);
