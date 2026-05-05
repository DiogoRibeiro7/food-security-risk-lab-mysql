USE food_security_risk;

CREATE INDEX idx_rainfall_country_year ON raw_rainfall_country_year (country_code, year);
CREATE INDEX idx_crop_country_year ON raw_crop_production_country_year (country_code, year);
CREATE INDEX idx_affordability_country_year ON raw_food_affordability_country_year (country_code, year);
CREATE INDEX idx_crop_group ON raw_crop_production_country_year (crop_group);
