"""Command-line interface for Food Security Risk Lab."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import typer
from rich.console import Console

from food_security_risk.database.engine import create_mysql_engine
from food_security_risk.database.loader import load_raw_csvs, read_mart, write_scores
from food_security_risk.database.sql_runner import execute_sql_file
from food_security_risk.reporting.markdown import write_markdown_report
from food_security_risk.risk.scoring import score_food_security_risk
from food_security_risk.sample_data import write_sample_tables

app = typer.Typer(help="Food-security early-warning analytics with local MySQL.")
console = Console()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = PROJECT_ROOT / "sql"


@app.command("sample-data")
def sample_data(
    output_dir: Path = typer.Option(Path("data/raw"), help="Directory where sample CSVs are written."),
    start_year: int = typer.Option(2010, help="First sample year."),
    end_year: int = typer.Option(2024, help="Last sample year."),
    seed: int = typer.Option(42, help="Random seed."),
) -> None:
    """Generate synthetic food-security source data."""

    paths = write_sample_tables(output_dir=output_dir, start_year=start_year, end_year=end_year, seed=seed)
    for name, path in paths.items():
        console.print(f"[green]wrote[/green] {name}: {path}")


@app.command("init-mysql")
def init_mysql() -> None:
    """Create MySQL raw, analytical, and score tables."""

    engine = create_mysql_engine()
    for sql_file in [
        "00_init_database.sql",
        "01_raw_tables.sql",
        "02_indexes.sql",
        "04_score_tables.sql",
    ]:
        execute_sql_file(engine, SQL_DIR / sql_file)
        console.print(f"[green]executed[/green] {sql_file}")


@app.command("load-mysql")
def load_mysql(
    raw_dir: Path = typer.Option(Path("data/raw"), help="Directory containing normalized raw CSVs."),
    append: bool = typer.Option(False, help="Append instead of replacing raw staging tables."),
) -> None:
    """Load normalized raw CSVs into MySQL staging tables."""

    engine = create_mysql_engine()
    loaded = load_raw_csvs(engine=engine, raw_dir=raw_dir, replace=not append)
    for table, rows in loaded.items():
        console.print(f"[green]loaded[/green] {rows} rows into {table}")


@app.command("build-analytics-mysql")
def build_analytics_mysql() -> None:
    """Build MySQL analytical mart from raw staging tables."""

    engine = create_mysql_engine()
    execute_sql_file(engine, SQL_DIR / "03_analytics_tables.sql")
    console.print("[green]built[/green] mart_country_year_food_security")


@app.command("score-from-mysql")
def score_from_mysql(
    output: Path = typer.Option(Path("reports/sample_run/food_security_scores.csv"), help="Output CSV."),
    write_back: bool = typer.Option(False, help="Write scores back to MySQL table."),
) -> None:
    """Read the analytical mart from MySQL and compute risk scores."""

    engine = create_mysql_engine()
    mart = read_mart(engine)
    scores = score_food_security_risk(mart)
    output.parent.mkdir(parents=True, exist_ok=True)
    scores.to_csv(output, index=False)
    console.print(f"[green]wrote[/green] scores: {output}")
    if write_back:
        write_scores(engine=engine, scores=scores, replace=True)
        console.print("[green]wrote[/green] scores to food_security_risk_score")


@app.command("score-local")
def score_local(
    raw_dir: Path = typer.Option(Path("data/raw"), help="Directory containing normalized raw CSVs."),
    output: Path = typer.Option(Path("reports/sample_run/food_security_scores.csv"), help="Output CSV."),
) -> None:
    """Compute scores from local CSV files without MySQL."""

    from food_security_risk.features.mart import build_country_year_mart

    rainfall = pd.read_csv(raw_dir / "rainfall_country_year.csv")
    crop = pd.read_csv(raw_dir / "crop_production_country_year.csv")
    affordability = pd.read_csv(raw_dir / "food_affordability_country_year.csv")
    mart = build_country_year_mart(rainfall=rainfall, crop=crop, affordability=affordability)
    scores = score_food_security_risk(mart)
    output.parent.mkdir(parents=True, exist_ok=True)
    scores.to_csv(output, index=False)
    console.print(f"[green]wrote[/green] scores: {output}")


@app.command("report")
def report(
    scores: Path = typer.Option(Path("reports/sample_run/food_security_scores.csv"), help="Input scores CSV."),
    output: Path = typer.Option(Path("reports/sample_run/food_security_report.md"), help="Output report."),
    title: str = typer.Option("Food Security Risk Report", help="Report title."),
) -> None:
    """Generate a Markdown report from score CSV."""

    frame = pd.read_csv(scores)
    write_markdown_report(scores=frame, output_path=output, title=title)
    console.print(f"[green]wrote[/green] report: {output}")


if __name__ == "__main__":
    app()
