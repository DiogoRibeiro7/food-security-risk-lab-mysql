# Monthly early-warning mart (v0.4)

Country-year indicators are fine for a retrospective view, but early warning
needs finer granularity. A developing drought shows up as several below-normal
rainfall months long before it shows up in an annual total. This mart adds a
country-month layer built from monthly rainfall.

Built by
[`build_country_month_mart`](../src/food_security_risk/features/monthly.py);
the output table is `mart_country_month_food_security`.

## What it computes

| Column group | Columns | Notes |
| --- | --- | --- |
| Keys | `country_code`, `country_name`, `year`, `month` | One row per country-month. |
| Level | `rainfall_mm`, `seasonal_baseline_mm` | Baseline is per **calendar month**. |
| Anomaly | `rainfall_anomaly_pct` | `(rainfall / seasonal_baseline - 1) * 100`. |
| Rolling | `rainfall_3m_sum`, `rainfall_3m_anomaly_pct`, `rainfall_6m_sum`, `rainfall_6m_anomaly_pct` | Windowed sums vs. summed seasonal baselines. |
| Missingness | `rainfall_observed`, `months_observed_3m`, `months_observed_6m` | How much of each window was actually observed. |
| Lags | `rainfall_anomaly_pct_lag1`, `rainfall_anomaly_pct_lag3` | For deterioration detection. |
| Flags | `severe_3m_deficit_flag`, `deteriorating_flag` | Early-warning signals. |

## Design choices

### Seasonality
Anomalies are measured against a **seasonal** baseline — the mean rainfall for
that calendar month over a reference window (`baseline_years`) — not a flat
annual mean. A dry month in the dry season is normal; a dry month in the wet
season is a signal. Using a flat baseline would raise false alarms every dry
season and miss real wet-season failures.

### Missingness is visible, not silent
The mart is built on a **complete month grid** per country (every month between
the first and last observation), so gaps appear as rows with
`rainfall_observed = 0` rather than vanishing. Rolling windows use
`min_periods = window`, so a 3- or 6-month window that spans a gap yields a
**missing** anomaly instead of a misleadingly small sum. `months_observed_3m` /
`months_observed_6m` make the coverage of each window explicit.

### Lower-frequency indicators are opt-in
Annual indicators (affordability, production) can be attached via
`annual_indicators`. They are joined on `country_code` + `year`, so every month
of a year gets that year's value. Carrying a value into a year that has **no**
annual observation only happens when `forward_fill_annual=True`; the synthesized
months are then marked with `annual_indicator_filled = 1` so the imputation is
auditable.

## Workflow

```bash
# Reproducible synthetic monthly rainfall (with an injected 2022 drought)
poetry run food-risk sample-monthly --output data/raw/rainfall_country_month.csv

# Or normalize a real monthly summary (country_code,country_name,year,month,rainfall_mm)
poetry run food-risk ingest-rainfall-monthly --input-csv path/to/monthly.csv

# Build the mart locally (no MySQL) ...
poetry run food-risk build-monthly-mart --source csv \
    --input-csv data/raw/rainfall_country_month.csv \
    --output reports/sample_run/country_month_mart.csv

# ... or through MySQL
poetry run food-risk load-rainfall-monthly
poetry run food-risk build-monthly-mart --source mysql --write-back
```
