# Food Security Risk Lab — MySQL Edition

Local MySQL data platform for transparent food-security early-warning analytics.

This repository downloads or ingests public food-security datasets, stores them in a local MySQL database, builds analytical tables, computes transparent country-year risk indicators, and generates reproducible reports.

The project is designed for responsible decision support. It does **not** claim to predict famine, replace humanitarian assessment, or make operational declarations. It produces interpretable warning indicators that can help analysts explore where conditions may be deteriorating.

## Why MySQL?

This version is MySQL-first. The goal is to practise real relational data modelling and local analytical workflows:

- raw staging tables
- normalized analytical tables
- repeatable SQL build scripts
- local Docker Compose database
- Python loaders and scoring code
- notebook analysis on top of MySQL

## v0.1 scope

The first version implements a country-year early-warning prototype with three core dimensions:

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

## Repository layout

```text
food-security-risk-lab/
├── README.md
├── ROADMAP.md
├── AGENTS.md
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
│   ├── 02_indexes.sql
│   ├── 03_analytics_tables.sql
│   └── 04_score_tables.sql
├── docs/
│   ├── data_model.md
│   ├── methodology.md
│   ├── real_data_sources.md
│   ├── mysql_workflow.md
│   └── responsible_use.md
├── notebooks/
│   └── 01_food_security_mysql_workflow.ipynb
├── prompts/
│   └── next_agent_prompts.md
├── examples/
│   └── run_sample.py
├── src/food_security_risk/
│   ├── ingestion/
│   ├── database/
│   ├── climate/
│   ├── agriculture/
│   ├── affordability/
│   ├── features/
│   ├── risk/
│   ├── reporting/
│   ├── visualization/
│   ├── sample_data.py
│   ├── pipeline.py
│   └── cli.py
├── tests/
└── reports/sample_run/
```

## Requirements

- Python 3.10+
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

Initialize MySQL tables:

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

Raw tables:

```text
raw_rainfall_country_year
raw_crop_production_country_year
raw_food_affordability_country_year
```

Analytical tables:

```text
mart_country_year_food_security
food_security_risk_score
```

## Responsible use

This project creates warning indicators, not final humanitarian classifications. Any operational use must be validated with domain experts, local knowledge, conflict data, market access data, household surveys, and humanitarian assessment frameworks.

## GitHub topics

Suggested topics:

```text
mysql, food-security, humanitarian-data, climate-risk, faostat, chirps, analytics-engineering, early-warning
```
