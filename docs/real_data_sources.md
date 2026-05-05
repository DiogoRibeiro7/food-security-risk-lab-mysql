# Real data sources

This repo includes sample-data generation so that the full workflow can be tested locally. For real analysis, replace the synthetic files with validated source data.

## Rainfall

Recommended source: CHIRPS rainfall summaries.

Initial ingestion contract:

```text
country_code,country_name,year,rainfall_mm,rainfall_baseline_mm,rainfall_anomaly_pct
```

## Agriculture

Recommended source: FAOSTAT crop production data.

Initial ingestion contract:

```text
country_code,country_name,year,crop_group,production_tonnes,production_baseline_tonnes,production_anomaly_pct
```

## Food affordability

Recommended source: World Bank Food Prices for Nutrition indicators.

Initial ingestion contract:

```text
country_code,country_name,year,healthy_diet_cost_ppp,affordability_ratio,affordability_baseline_ratio,affordability_anomaly_pct
```

## Humanitarian context

FEWS NET and IPC-style outputs can be added as context layers. Do not treat them as simple ground-truth labels without understanding the methodology and spatial scale.
