# Data model

## Raw staging tables

### `raw_rainfall_country_year`

Country-year rainfall summaries.

Key columns:

- `country_code`
- `country_name`
- `year`
- `rainfall_mm`
- `rainfall_baseline_mm`
- `rainfall_anomaly_pct`

### `raw_crop_production_country_year`

Country-year crop-production indicators.

Key columns:

- `country_code`
- `country_name`
- `year`
- `crop_group`
- `production_tonnes`
- `production_baseline_tonnes`
- `production_anomaly_pct`

### `raw_food_affordability_country_year`

Country-year food-affordability indicators.

Key columns:

- `country_code`
- `country_name`
- `year`
- `healthy_diet_cost_ppp`
- `affordability_ratio`
- `affordability_baseline_ratio`
- `affordability_anomaly_pct`

## Analytical table

### `mart_country_year_food_security`

This table joins rainfall, crop production, and affordability indicators into one country-year mart. It is the main input for scoring.

## Score table

### `food_security_risk_score`

Stores the final risk score, component scores, risk band, and main textual drivers.

## Later additions

Tables added after the country-year prototype are documented in their own
design notes:

- `raw_rainfall_country_month` and `mart_country_month_food_security` — see
  [monthly_early_warning.md](monthly_early_warning.md)
- `dim_country` and `country_source_mapping` — see
  [country_harmonization.md](country_harmonization.md)
- `fewsnet_context` — see [fewsnet_context.md](fewsnet_context.md)
