# Roadmap

This roadmap is intentionally detailed. The goal is to make the repository useful for continued development by a human engineer or a coding agent.

## Vision

Build a local, reproducible, MySQL-first platform for food-security early-warning analytics.

The project should help analysts combine rainfall, crop-production, affordability, and contextual indicators into transparent risk signals. The final system should not claim to predict famine. It should provide evidence, traceability, and explainability.

---

## v0.1 — MySQL local prototype

**Status:** implemented in this scaffold.

### Goals

- Create a runnable MySQL-backed prototype.
- Generate synthetic country-year food-security data.
- Store raw indicators in MySQL staging tables.
- Build an analytical country-year mart.
- Compute transparent risk scores.
- Generate Markdown reports.

### Deliverables

- Docker Compose with MySQL and Adminer.
- Raw MySQL tables for rainfall, crop production, and affordability.
- Analytical MySQL mart.
- Python loaders for CSV-to-MySQL ingestion.
- Python scoring module.
- Report generator.
- Notebook workflow.
- Tests for parsing, feature construction, scoring, and reports.

### Acceptance criteria

- `poetry run food-risk sample-data` creates the sample files.
- `poetry run food-risk init-mysql` creates the database schema.
- `poetry run food-risk load-mysql` loads all sample files.
- `poetry run food-risk build-analytics-mysql` creates the analytical mart.
- `poetry run food-risk score-from-mysql` writes risk scores to CSV.
- Tests pass without requiring a running MySQL server.

---

## v0.2 — Real-data ingestion layer

### Goals

Replace synthetic inputs with documented downloaders and validated raw datasets.

### Tasks

1. **FAOSTAT crop production downloader**
   - Add configurable FAOSTAT domain/item/element filters.
   - Support cereals, maize, wheat, rice, sorghum, millet, and roots/tubers.
   - Store raw responses under `data/raw/faostat/`.
   - Preserve metadata such as source URL, download timestamp, and query parameters.

2. **World Bank food affordability downloader**
   - Add indicator-code configuration.
   - Store raw downloaded CSV or JSON.
   - Normalize country code, year, indicator name, and value.

3. **Rainfall ingestion**
   - Start with country-year CHIRPS summary CSVs.
   - Add a clear validation contract for columns.
   - Later support gridded rainfall aggregation.

4. **Metadata manifest**
   - Create `data/raw/manifest.json`.
   - Record dataset name, source, version, download date, file hash, and row count.

### Acceptance criteria

- Real downloaders write raw files without modifying the database.
- Normalizers produce stable CSVs matching the raw MySQL staging schema.
- Every normalized file has a manifest entry.

---

## v0.3 — Country-code and geography harmonization

### Problem

Food-security datasets often disagree on country names, ISO codes, administrative boundaries, and historical entities.

### Goals

- Build a robust country harmonization layer.
- Make joins explicit and auditable.

### Tasks

1. Add `dim_country` table.
2. Add source-specific country-name mapping tables.
3. Add ISO2, ISO3, M49, and region columns.
4. Add quality flags for ambiguous mappings.
5. Create tests for common difficult cases.
6. Add documentation for unresolved country-code issues.

### Analytical output

- `dim_country`
- `country_source_mapping`
- `country_mapping_quality_report`

---

## v0.4 — Monthly early-warning mart

### Motivation

Country-year indicators are useful for a prototype, but early warning often needs monthly or seasonal granularity.

### Goals

- Add a country-month analytical mart.
- Support rainfall seasonality and recent deterioration detection.

### Tasks

1. Add `raw_rainfall_country_month` table.
2. Add `mart_country_month_food_security` table.
3. Compute 1-month, 3-month, and 6-month rainfall anomalies.
4. Compute seasonal baseline anomalies.
5. Add lagged features.
6. Add missingness quality indicators.

### Acceptance criteria

- A monthly mart can be built from rainfall data and lower-frequency indicators.
- Low-frequency indicators are forward-filled only when explicitly configured.
- Missingness is visible in the output.

---

## v0.5 — FEWS NET context layer

### Goals

Add contextual humanitarian reference layers without treating them as ground truth labels.

### Tasks

1. Add table for FEWS NET country or region context.
2. Add IPC-style classification fields where available.
3. Add report narratives as optional text metadata.
4. Support joins to risk outputs by country/date.
5. Add responsible-use documentation.

### Important rule

Do not train models that blindly reproduce FEWS NET classifications without understanding methodology, spatial granularity, and temporal scope.

---

## v0.6 — Baseline and anomaly improvements

### Goals

Improve the statistical quality of the risk components.

### Tasks

1. Replace min-max normalization with robust scaling.
2. Add rolling historical baselines by country.
3. Add drought severity metrics.
4. Add crop-production z-scores.
5. Add affordability z-scores.
6. Add confidence intervals or uncertainty bands.
7. Add anomaly reason codes.

### Candidate methods

- rolling median and median absolute deviation
- empirical quantile ranks
- exponentially weighted baselines
- Bayesian partial pooling by region

---

## v0.7 — Shock decomposition

### Goals

Separate different drivers of food-security risk.

### Risk dimensions

- climate shock
- crop-production shock
- affordability shock
- volatility shock
- persistence shock
- compounding shock

### Tasks

1. Add component-level reports.
2. Add contribution waterfall charts.
3. Add shock labels.
4. Add rules for compound stress.
5. Add tests for component decomposition.

---

## v0.8 — Validation and backtesting

### Goals

Evaluate whether risk scores would have been useful historically.

### Tasks

1. Create historical backtesting splits.
2. Add comparison against known food-security deterioration periods.
3. Add calibration plots.
4. Add precision/recall at top-k risk countries.
5. Add lead-time analysis.
6. Add false-positive review workflow.

### Caution

Validation must be careful because humanitarian outcomes are under-reported, spatially heterogeneous, and affected by conflict, access, policy, and market systems.

---

## v0.9 — Reporting automation

### Goals

Move from a single report to repeatable country and regional risk briefs.

### Tasks

1. Generate country risk profiles.
2. Generate regional summaries.
3. Add comparison against previous report period.
4. Add chart export.
5. Add HTML report option.
6. Add scheduled GitHub Action for data refresh.

---

## v1.0 — Stable MySQL food-security analytics platform

### Goals

Release a stable local platform.

### Required features

- documented MySQL schema
- stable CLI
- reproducible ingestion workflow
- real-data examples
- tests for all scoring components
- responsible-use guide
- notebook examples
- backtesting module
- report generation

### Quality gates

- 85%+ test coverage on pure-Python modules
- MySQL integration test in CI service container
- linting with Ruff
- type checking with MyPy
- notebook smoke test

---

## v1.1+ — Advanced extensions

### Geospatial extension

- Add admin-1 and admin-2 level data.
- Add geospatial joins.
- Add drought polygon overlays.
- Add map visualizations.

### Advanced modelling extension

- Bayesian hierarchical risk model.
- Temporal state-space model.
- Graph model for spillover risk between neighbouring countries.
- Causal sensitivity analysis for shocks.

### Operational extension

- API service for risk scores.
- Dashboard.
- Scheduled data refresh.
- Alerts for newly deteriorating regions.

### LLM extension

- Generate careful analyst briefs from structured risk drivers.
- Enforce responsible-use templates.
- Prevent causal overclaiming.
- Cite underlying data sources in generated narratives.

---

## Agent-ready task backlog

### Task A — Add FAOSTAT real downloader

Implement a downloader under `src/food_security_risk/ingestion/faostat.py` that downloads crop-production data using configurable filters. The function should write a raw file, a normalized CSV, and a manifest entry. Add tests with mocked HTTP responses.

### Task B — Add MySQL integration tests

Create a GitHub Actions job with a MySQL service container. Run `init-mysql`, `load-mysql`, `build-analytics-mysql`, and `score-from-mysql` against generated sample data.

### Task C — Add country harmonization

Create `dim_country` and a mapping module. Add tests for country-code joins and unmatched-country reporting.

### Task D — Add monthly rainfall mart

Create a new raw monthly rainfall table and a country-month analytical mart. Add lagged rainfall anomaly features.

### Task E — Add report charts

Create chart exports for top risk countries, score components, and country trends. Keep charts deterministic and readable.
