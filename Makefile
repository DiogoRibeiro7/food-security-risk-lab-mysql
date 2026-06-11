.PHONY: install test test-integration lint format typecheck sample mysql-up mysql-down init-mysql load-mysql build-analytics score report

install:
	poetry install --with dev

test:
	poetry run pytest -q

# End-to-end test against a real MySQL server. Requires the Compose database
# (make mysql-up) and the MYSQL_* environment from .env.
test-integration:
	RUN_MYSQL_INTEGRATION=1 poetry run pytest -q -m integration

lint:
	poetry run ruff check .

format:
	poetry run ruff format .

typecheck:
	poetry run mypy src

sample:
	poetry run food-risk sample-data --output-dir data/raw --start-year 2010 --end-year 2024

mysql-up:
	docker compose up -d mysql adminer

mysql-down:
	docker compose down

init-mysql:
	poetry run food-risk init-mysql

load-mysql:
	poetry run food-risk load-mysql --raw-dir data/raw

build-analytics:
	poetry run food-risk build-analytics-mysql

score:
	poetry run food-risk score-from-mysql --output reports/sample_run/food_security_scores.csv --write-back

report:
	poetry run food-risk report --scores reports/sample_run/food_security_scores.csv --output reports/sample_run/food_security_report.md --title "Food Security Risk Report"
