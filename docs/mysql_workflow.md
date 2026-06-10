# MySQL workflow

## 1. Start the database

```bash
docker compose up -d mysql adminer
```

## 2. Initialize schema

```bash
poetry run food-risk init-mysql
```

This executes, in order:

- `sql/00_init_database.sql`
- `sql/01_raw_tables.sql`
- `sql/04_score_tables.sql`
- `sql/05_country_dim.sql`
- `sql/06_monthly_tables.sql`
- `sql/07_context_tables.sql`

All scripts are idempotent: `init-mysql` can be re-run safely. Secondary
indexes are declared inside the `CREATE TABLE` statements because MySQL has no
`CREATE INDEX IF NOT EXISTS`.

## 3. Load raw files

```bash
poetry run food-risk load-mysql --raw-dir data/raw
```

Expected files:

- `rainfall_country_year.csv`
- `crop_production_country_year.csv`
- `food_affordability_country_year.csv`

## 4. Build analytical mart

```bash
poetry run food-risk build-analytics-mysql
```

This executes `sql/03_analytics_tables.sql`.

## 5. Score from MySQL

```bash
poetry run food-risk score-from-mysql --output reports/sample_run/food_security_scores.csv --write-back
```

When `--write-back` is used, the score table rows are replaced with the current
scores. Loads never drop tables: the schema defined in `sql/` (primary keys,
types, defaults, indexes) stays authoritative, and a replace load deletes rows
and re-appends instead.
