USE food_security_risk;

CREATE TABLE IF NOT EXISTS food_security_risk_score (
    country_code VARCHAR(3) NOT NULL,
    country_name VARCHAR(128) NOT NULL,
    year INT NOT NULL,
    crop_group VARCHAR(64) NOT NULL,
    rainfall_deficit_score DOUBLE NOT NULL,
    food_affordability_pressure_score DOUBLE NOT NULL,
    crop_production_decline_score DOUBLE NOT NULL,
    volatility_score DOUBLE NOT NULL,
    recent_deterioration_score DOUBLE NOT NULL,
    food_security_risk_score DOUBLE NOT NULL,
    risk_band VARCHAR(32) NOT NULL,
    main_drivers TEXT NULL,
    scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (country_code, year, crop_group)
);
