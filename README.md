# Food Security Risk Lab — MySQL Edition

Local MySQL data platform for transparent food-security early-warning analytics.

This repository downloads or ingests public food-security datasets, stores them in a local MySQL database, builds analytical tables, computes transparent country-year and country-month risk indicators, and generates reproducible reports.

The project is designed for responsible decision support. It does **not** claim to predict famine, replace humanitarian assessment, or make operational declarations. It produces interpretable warning indicators that can help analysts explore where conditions may be deteriorating.

## Why MySQL?

This version is MySQL-first. The goal is to practise real relational data modelling and local analytical workflows:

- raw staging tables with explicit DDL (primary keys, types, defaults)
- normalized analytical tables
- repeatable, idempotent SQL build scripts
- local Docker Compose database
- Python loaders that preserve the SQL-defined schema (loads clear rows and append; they never drop tables)
- notebook analysis on top of MySQL

## Scope

The country-year prototype scores three core dimensions:

1. rainfall anomalies
2. crop-production declines
3. food-affordability pressure

The final score is transparent:

```text
food_security_risk_score =
    0.30 * rainfall_deficit_score
  + 0.25 * food_affordability_pressure_score
  + 0.20 * crop_production_decline_score
  + 0.15 * volatility_score
  + 0.10 * recent_deterioration_score
```

On top of that, the repo includes:

- **Real-data ingestion** for World Bank indicators, FAOSTAT bulk production files, and CHIRPS-style rainfall summaries, with a provenance manifest (see `docs/real_data_sources.md`).
- **Country harmonization** of source country names to ISO3 with explicit quality flags — ambiguous names are reported, never guessed (see `docs/country_harmonization.md`).
- **A monthly early-warning mart** with seasonal baselines, rolling 3/6-month anomalies, and explicit missingness handling (see `docs/monthly_early_warning.md`).
- **A FEWS NET / IPC context layer** joined to risk outputs as reference context, never as a training label (see `docs/fewsnet_context.md`).

## Repository layout

```text
food-security-risk-lab-mysql/
├── README.md
├── ROADMAP.md
├── CITATION.cff
├── LICENSE
├── pyproject.toml
├── docker-compose.yml
├── .env.example
├── Makefile
├── setup.sh
├── sql/
│   ├── 00_init_database.sql
│   ├── 01_raw_tables.sql
│   ├── 03_analytics_tables.sql
│   ├── 04_score_tables.sql
│   ├── 05_country_dim.sql
│   ├── 06_monthly_tables.sql
│   └── 07_context_tables.sql
├── docs/
│   ├── data_model.md
│   ├── methodology.md
│   ├── real_data_sources.md
│   ├── country_harmonization.md
│   ├── monthly_early_warning.md
│   ├── fewsnet_context.md
│   ├── mysql_workflow.md
│   └── responsible_use.md
├── notebooks/
│   └── 01_food_security_mysql_workflow.ipynb
├── examples/
│   └── run_sample.py
├── src/food_security_risk/
│   ├── ingestion/        # downloaders, normalization, provenance manifest
│   ├── database/         # engine, config, schema-preserving loaders, SQL runner
│   ├── geography/        # ISO3 reference data and country harmonization
│   ├── climate/          # rainfall input validation
│   ├── agriculture/      # crop input validation
│   ├── affordability/    # affordability input validation
│   ├── features/         # country-year and country-month marts
│   ├── context/          # FEWS NET / IPC reference context
│   ├── risk/             # transparent scoring
│   ├── reporting/        # Markdown reports
│   ├── visualization/    # charts
│   ├── sample_data.py
│   ├── pipeline.py
│   └── cli.py
├── tests/
└── reports/sample_run/   # committed sample outputs
```

## Requirements

- Python 3.10–3.12
- Poetry
- Docker and Docker Compose
- MySQL 8.4, provided by `docker-compose.yml`

## Quick start

```bash
poetry install --with dev
cp .env.example .env
docker compose up -d mysql adminer
```

Generate synthetic sample data:

```bash
poetry run food-risk sample-data \
  --output-dir data/raw \
  --start-year 2010 \
  --end-year 2024
```

Initialize MySQL tables (idempotent — safe to re-run):

```bash
poetry run food-risk init-mysql
```

Load CSV files into MySQL raw tables:

```bash
poetry run food-risk load-mysql --raw-dir data/raw
```

Build analytical tables:

```bash
poetry run food-risk build-analytics-mysql
```

Compute scores from MySQL:

```bash
poetry run food-risk score-from-mysql \
  --output reports/sample_run/food_security_scores.csv \
  --write-back
```

Generate a Markdown report:

```bash
poetry run food-risk report \
  --scores reports/sample_run/food_security_scores.csv \
  --output reports/sample_run/food_security_report.md \
  --title "Food Security Risk Report"
```

## Monthly early-warning workflow

A developing drought shows up as several below-normal rainfall months before it shows up in an annual total. The monthly mart measures anomalies against a *seasonal* baseline and keeps gaps visible:

```bash
poetry run food-risk sample-monthly                 # or ingest-rainfall-monthly for real data
poetry run food-risk load-rainfall-monthly
poetry run food-risk build-monthly-mart --write-back
```

See `docs/monthly_early_warning.md` for the design decisions (seasonality, missingness, forward-fill of annual indicators).

## Humanitarian context workflow

FEWS NET / IPC phases can be attached to any risk output as reference context under a `context_` prefix. They are never used as a target for the score:

```bash
poetry run food-risk sample-context                 # or ingest-context for real data
poetry run food-risk load-context
poetry run food-risk join-context \
  --risk-csv reports/sample_run/food_security_scores.csv \
  --level year
```

## CLI command reference

Run `poetry run food-risk --help` for full options. Commands by area:

| Area | Commands |
| --- | --- |
| Synthetic data | `sample-data`, `sample-monthly`, `sample-context` |
| Real-data ingestion | `ingest-world-bank`, `ingest-faostat`, `ingest-rainfall`, `ingest-rainfall-monthly`, `ingest-context`, `download-faostat` |
| Country harmonization | `build-country-dim`, `map-source-countries` |
| MySQL | `init-mysql`, `load-mysql`, `load-rainfall-monthly`, `load-context`, `build-analytics-mysql`, `build-monthly-mart` |
| Scoring and reporting | `score-from-mysql`, `score-local`, `report`, `join-context` |

## Offline sample workflow

The pure-Python sample pipeline does not require MySQL. It is useful for tests and quick validation.

```bash
poetry run python examples/run_sample.py
```

## MySQL access

Adminer is exposed at:

```text
http://localhost:8080
```

Default credentials from `.env.example`:

```text
System: MySQL
Server: mysql
User: food_user
Password: food_password
Database: food_security_risk
```

## Data model

Raw staging tables:

```text
raw_rainfall_country_year
raw_crop_production_country_year
raw_food_affordability_country_year
raw_rainfall_country_month
```

Reference tables:

```text
dim_country
country_source_mapping
fewsnet_context
```

Analytical tables:

```text
mart_country_year_food_security
mart_country_month_food_security
food_security_risk_score
```

See `docs/data_model.md` for column-level documentation.

## Development

```bash
make test        # pytest
make lint        # ruff check
make typecheck   # mypy (strict)
make format      # ruff format
```

CI runs lint, type check, and tests on every push and pull request.

## Responsible use

This project creates warning indicators, not final humanitarian classifications. Any operational use must be validated with domain experts, local knowledge, conflict data, market access data, household surveys, and humanitarian assessment frameworks. See `docs/responsible_use.md`.

## GitHub topics

Suggested topics:

```text
mysql, food-security, humanitarian-data, climate-risk, faostat, chirps, analytics-engineering, early-warning
```
