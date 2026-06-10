"""Command-line interface for Food Security Risk Lab."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import typer
from rich.console import Console

from food_security_risk.affordability.validation import validate_affordability_country_year
from food_security_risk.agriculture.validation import validate_crop_production_country_year
from food_security_risk.climate.validation import (
    validate_rainfall_country_month,
    validate_rainfall_country_year,
)
from food_security_risk.context.fewsnet import (
    join_context_to_risk,
    normalize_fewsnet_context,
)
from food_security_risk.database.engine import create_mysql_engine
from food_security_risk.database.loader import (
    load_country_dimension,
    load_fewsnet_context,
    load_rainfall_country_month,
    load_raw_csvs,
    load_source_mapping,
    read_fewsnet_context,
    read_mart,
    read_rainfall_country_month,
    write_country_month_mart,
    write_scores,
)
from food_security_risk.database.sql_runner import execute_sql_file
from food_security_risk.features.monthly import build_country_month_mart
from food_security_risk.geography.harmonization import CountryHarmonizer
from food_security_risk.ingestion.faostat import download_url
from food_security_risk.ingestion.manifest import build_entry, update_manifest
from food_security_risk.ingestion.normalize import (
    normalize_faostat_production,
    normalize_rainfall_country_month,
    normalize_rainfall_summary,
    normalize_world_bank_affordability,
    write_normalized_csv,
)
from food_security_risk.ingestion.world_bank import download_world_bank_indicator
from food_security_risk.reporting.markdown import write_markdown_report
from food_security_risk.risk.scoring import score_food_security_risk
from food_security_risk.sample_data import (
    generate_fewsnet_context,
    generate_monthly_rainfall,
    write_sample_tables,
)

app = typer.Typer(help="Food-security early-warning analytics with local MySQL.")
console = Console()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = PROJECT_ROOT / "sql"


@app.command("sample-data")
def sample_data(
    output_dir: Path = typer.Option(
        Path("data/raw"), help="Directory where sample CSVs are written."
    ),
    start_year: int = typer.Option(2010, help="First sample year."),
    end_year: int = typer.Option(2024, help="Last sample year."),
    seed: int = typer.Option(42, help="Random seed."),
) -> None:
    """Generate synthetic food-security source data."""

    paths = write_sample_tables(
        output_dir=output_dir, start_year=start_year, end_year=end_year, seed=seed
    )
    for name, path in paths.items():
        console.print(f"[green]wrote[/green] {name}: {path}")


@app.command("init-mysql")
def init_mysql() -> None:
    """Create MySQL raw, analytical, and score tables."""

    engine = create_mysql_engine()
    for sql_file in [
        "00_init_database.sql",
        "01_raw_tables.sql",
        "04_score_tables.sql",
        "05_country_dim.sql",
        "06_monthly_tables.sql",
        "07_context_tables.sql",
    ]:
        execute_sql_file(engine, SQL_DIR / sql_file)
        console.print(f"[green]executed[/green] {sql_file}")


@app.command("load-mysql")
def load_mysql(
    raw_dir: Path = typer.Option(
        Path("data/raw"), help="Directory containing normalized raw CSVs."
    ),
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
    output: Path = typer.Option(
        Path("reports/sample_run/food_security_scores.csv"), help="Output CSV."
    ),
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
    raw_dir: Path = typer.Option(
        Path("data/raw"), help="Directory containing normalized raw CSVs."
    ),
    output: Path = typer.Option(
        Path("reports/sample_run/food_security_scores.csv"), help="Output CSV."
    ),
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
    scores: Path = typer.Option(
        Path("reports/sample_run/food_security_scores.csv"), help="Input scores CSV."
    ),
    output: Path = typer.Option(
        Path("reports/sample_run/food_security_report.md"), help="Output report."
    ),
    title: str = typer.Option("Food Security Risk Report", help="Report title."),
) -> None:
    """Generate a Markdown report from score CSV."""

    frame = pd.read_csv(scores)
    write_markdown_report(scores=frame, output_path=output, title=title)
    console.print(f"[green]wrote[/green] report: {output}")


def _parse_baseline_years(value: str | None) -> tuple[int, int] | None:
    """Parse a ``"FIRST-LAST"`` reference window, or ``None`` for all years."""

    if value is None or not value.strip():
        return None
    parts = value.split("-")
    if len(parts) != 2:
        raise typer.BadParameter("baseline-years must look like '2015-2020'.")
    first, last = int(parts[0]), int(parts[1])
    if first > last:
        raise typer.BadParameter("baseline-years first must not exceed last.")
    return first, last


@app.command("ingest-world-bank")
def ingest_world_bank(
    indicator: str = typer.Option(..., help="World Bank indicator code (cost of a healthy diet)."),
    output: Path = typer.Option(
        Path("data/raw/food_affordability_country_year.csv"),
        help="Normalized affordability CSV output.",
    ),
    raw_dir: Path = typer.Option(
        Path("data/raw"), help="Directory for the manifest and raw payload."
    ),
    baseline_years: str = typer.Option(
        None, help="Reference window 'FIRST-LAST'; default uses all years."
    ),
    version: str = typer.Option("v2", help="Source version recorded in the manifest."),
) -> None:
    """Download a World Bank indicator and normalize it into affordability staging."""

    raw_payload_path = raw_dir / "world_bank" / f"{indicator}.json"
    download_world_bank_indicator(indicator, raw_payload_path)
    console.print(f"[green]downloaded[/green] world bank payload: {raw_payload_path}")

    payload = raw_payload_path.read_bytes()
    frame = normalize_world_bank_affordability(
        payload, baseline_years=_parse_baseline_years(baseline_years)
    )
    validate_affordability_country_year(frame)
    write_normalized_csv(frame, output)
    console.print(f"[green]wrote[/green] {len(frame)} rows: {output}")

    entry = build_entry(
        dataset="food_affordability_country_year",
        source="World Bank Indicators API",
        version=version,
        downloaded_at=datetime.now(timezone.utc).isoformat(),
        file_path=output,
        manifest_dir=raw_dir,
        source_url=f"https://api.worldbank.org/v2/country/all/indicator/{indicator}",
    )
    update_manifest(raw_dir / "manifest.json", entry)
    console.print("[green]recorded[/green] manifest entry: food_affordability_country_year")


@app.command("ingest-faostat")
def ingest_faostat(
    input_csv: Path = typer.Option(..., help="Raw FAOSTAT bulk production CSV (long format)."),
    crop_group: str = typer.Option("cereals", help="Crop-group label for the staging rows."),
    output: Path = typer.Option(
        Path("data/raw/crop_production_country_year.csv"),
        help="Normalized crop-production CSV output.",
    ),
    raw_dir: Path = typer.Option(Path("data/raw"), help="Directory for the manifest."),
    baseline_years: str = typer.Option(
        None, help="Reference window 'FIRST-LAST'; default uses all years."
    ),
    mapping_report: Path = typer.Option(
        Path("data/raw/faostat_country_mapping.csv"),
        help="Where to write the country-name harmonization report.",
    ),
    version: str = typer.Option("bulk", help="Source version recorded in the manifest."),
) -> None:
    """Normalize a downloaded FAOSTAT bulk production file into crop staging.

    Country names are harmonized to ISO3 through the geography layer. Only
    confidently resolved areas are normalized; ambiguous, historical, and
    unresolved areas are written to the mapping report instead of being guessed.
    """

    raw = pd.read_csv(input_csv)
    harmonizer = CountryHarmonizer()
    areas = raw["Area"].astype(str).tolist() if "Area" in raw.columns else []
    country_map, mapping = harmonizer.build_country_map(areas)

    write_normalized_csv(mapping, mapping_report)
    flagged = mapping[mapping["quality_flag"] != "exact"]
    if not flagged.empty:
        console.print(
            f"[yellow]{len(flagged)} FAOSTAT areas need review[/yellow] "
            f"(see {mapping_report})"
        )

    frame, unmapped = normalize_faostat_production(
        raw,
        country_map=country_map,
        crop_group=crop_group,
        baseline_years=_parse_baseline_years(baseline_years),
    )
    if unmapped:
        console.print(
            f"[yellow]dropped {len(unmapped)} unresolved FAOSTAT areas[/yellow]: "
            f"{', '.join(unmapped)}"
        )
    validate_crop_production_country_year(frame)
    write_normalized_csv(frame, output)
    console.print(f"[green]wrote[/green] {len(frame)} rows: {output}")

    entry = build_entry(
        dataset="crop_production_country_year",
        source="FAOSTAT bulk download",
        version=version,
        downloaded_at=datetime.now(timezone.utc).isoformat(),
        file_path=output,
        manifest_dir=raw_dir,
    )
    update_manifest(raw_dir / "manifest.json", entry)
    console.print("[green]recorded[/green] manifest entry: crop_production_country_year")


@app.command("ingest-rainfall")
def ingest_rainfall(
    input_csv: Path = typer.Option(..., help="Country-year rainfall summary CSV (CHIRPS-style)."),
    output: Path = typer.Option(
        Path("data/raw/rainfall_country_year.csv"),
        help="Normalized rainfall CSV output.",
    ),
    raw_dir: Path = typer.Option(Path("data/raw"), help="Directory for the manifest."),
    baseline_years: str = typer.Option(
        None, help="Reference window 'FIRST-LAST'; default uses all years."
    ),
    version: str = typer.Option("summary", help="Source version recorded in the manifest."),
) -> None:
    """Normalize a country-year rainfall summary into rainfall staging."""

    raw = pd.read_csv(input_csv)
    frame = normalize_rainfall_summary(raw, baseline_years=_parse_baseline_years(baseline_years))
    validate_rainfall_country_year(frame)
    write_normalized_csv(frame, output)
    console.print(f"[green]wrote[/green] {len(frame)} rows: {output}")

    entry = build_entry(
        dataset="rainfall_country_year",
        source="CHIRPS country-year summary",
        version=version,
        downloaded_at=datetime.now(timezone.utc).isoformat(),
        file_path=output,
        manifest_dir=raw_dir,
    )
    update_manifest(raw_dir / "manifest.json", entry)
    console.print("[green]recorded[/green] manifest entry: rainfall_country_year")


@app.command("download-faostat")
def download_faostat(
    url: str = typer.Option(..., help="FAOSTAT bulk file URL."),
    output: Path = typer.Option(
        Path("data/raw/faostat/production.zip"),
        help="Destination for the raw download.",
    ),
) -> None:
    """Download a raw FAOSTAT bulk file without normalizing it."""

    path = download_url(url, output)
    console.print(f"[green]downloaded[/green] {path}")


@app.command("build-country-dim")
def build_country_dim(
    output: Path = typer.Option(
        Path("data/raw/dim_country.csv"),
        help="Where to also write the country dimension as CSV.",
    ),
    load: bool = typer.Option(True, help="Load the dimension into MySQL dim_country."),
) -> None:
    """Build the canonical country dimension and optionally load it into MySQL."""

    harmonizer = CountryHarmonizer()
    frame = harmonizer.dim_country_frame()
    write_normalized_csv(frame, output)
    console.print(f"[green]wrote[/green] {len(frame)} countries: {output}")

    if load:
        engine = create_mysql_engine()
        rows = load_country_dimension(engine, frame)
        console.print(f"[green]loaded[/green] {rows} rows into dim_country")


@app.command("map-source-countries")
def map_source_countries(
    input_csv: Path = typer.Option(..., help="CSV containing a country-name column."),
    column: str = typer.Option("Area", help="Column holding source country names."),
    source: str = typer.Option(..., help="Source label, e.g. 'faostat' or 'world_bank'."),
    output: Path = typer.Option(
        Path("data/raw/country_source_mapping.csv"),
        help="Where to write the source mapping report.",
    ),
    load: bool = typer.Option(False, help="Load the mapping into MySQL."),
) -> None:
    """Harmonize a source's country names and report mapping quality."""

    raw = pd.read_csv(input_csv)
    if column not in raw.columns:
        raise typer.BadParameter(f"column '{column}' not found in {input_csv}")

    harmonizer = CountryHarmonizer()
    names = raw[column].astype(str).tolist()
    mapping = harmonizer.build_source_mapping(names, source=source)
    write_normalized_csv(mapping, output)

    report = harmonizer.quality_report(mapping)
    for _, row in report.iterrows():
        console.print(f"  {row['quality_flag']}: {row['name_count']}")
    console.print(f"[green]wrote[/green] mapping for {len(mapping)} names: {output}")

    if load:
        engine = create_mysql_engine()
        rows = load_source_mapping(engine, mapping)
        console.print(f"[green]loaded[/green] {rows} rows into country_source_mapping")


@app.command("sample-monthly")
def sample_monthly(
    output: Path = typer.Option(
        Path("data/raw/rainfall_country_month.csv"),
        help="Where to write synthetic monthly rainfall.",
    ),
    start_year: int = typer.Option(2018, help="First sample year."),
    end_year: int = typer.Option(2024, help="Last sample year."),
    seed: int = typer.Option(7, help="Random seed."),
) -> None:
    """Generate synthetic monthly rainfall with seasonality and a drought episode."""

    frame = generate_monthly_rainfall(start_year=start_year, end_year=end_year, seed=seed)
    frame = normalize_rainfall_country_month(frame, source_dataset="synthetic")
    write_normalized_csv(frame, output)
    console.print(f"[green]wrote[/green] {len(frame)} rows: {output}")


@app.command("ingest-rainfall-monthly")
def ingest_rainfall_monthly(
    input_csv: Path = typer.Option(..., help="Monthly rainfall CSV (country_code,year,month,...)."),
    output: Path = typer.Option(
        Path("data/raw/rainfall_country_month.csv"),
        help="Normalized monthly rainfall output.",
    ),
    raw_dir: Path = typer.Option(Path("data/raw"), help="Directory for the manifest."),
    version: str = typer.Option("summary", help="Source version recorded in the manifest."),
) -> None:
    """Normalize a monthly rainfall summary into the raw monthly staging schema."""

    raw = pd.read_csv(input_csv)
    frame = normalize_rainfall_country_month(raw)
    validate_rainfall_country_month(frame)
    write_normalized_csv(frame, output)
    console.print(f"[green]wrote[/green] {len(frame)} rows: {output}")

    entry = build_entry(
        dataset="rainfall_country_month",
        source="CHIRPS monthly summary",
        version=version,
        downloaded_at=datetime.now(timezone.utc).isoformat(),
        file_path=output,
        manifest_dir=raw_dir,
    )
    update_manifest(raw_dir / "manifest.json", entry)
    console.print("[green]recorded[/green] manifest entry: rainfall_country_month")


@app.command("load-rainfall-monthly")
def load_rainfall_monthly(
    input_csv: Path = typer.Option(
        Path("data/raw/rainfall_country_month.csv"),
        help="Normalized monthly rainfall CSV.",
    ),
    append: bool = typer.Option(False, help="Append instead of replacing the staging table."),
) -> None:
    """Load monthly rainfall into the MySQL raw_rainfall_country_month table."""

    engine = create_mysql_engine()
    frame = pd.read_csv(input_csv)
    rows = load_rainfall_country_month(engine, frame, replace=not append)
    console.print(f"[green]loaded[/green] {rows} rows into raw_rainfall_country_month")


@app.command("build-monthly-mart")
def build_monthly_mart(
    source: str = typer.Option("mysql", help="Read rainfall from 'mysql' or a local 'csv'."),
    input_csv: Path = typer.Option(
        Path("data/raw/rainfall_country_month.csv"),
        help="Monthly rainfall CSV when --source=csv.",
    ),
    output: Path = typer.Option(
        Path("reports/sample_run/country_month_mart.csv"),
        help="Where to write the country-month mart CSV.",
    ),
    baseline_years: str = typer.Option(
        None, help="Seasonal baseline window 'FIRST-LAST'; default uses all years."
    ),
    write_back: bool = typer.Option(False, help="Write the mart back to MySQL."),
) -> None:
    """Build the country-month early-warning mart from monthly rainfall."""

    if source == "mysql":
        engine = create_mysql_engine()
        rainfall = read_rainfall_country_month(engine)
    elif source == "csv":
        rainfall = pd.read_csv(input_csv)
    else:
        raise typer.BadParameter("source must be 'mysql' or 'csv'.")

    mart = build_country_month_mart(rainfall, baseline_years=_parse_baseline_years(baseline_years))
    write_normalized_csv(mart, output)
    console.print(f"[green]wrote[/green] {len(mart)} country-month rows: {output}")

    if write_back:
        engine = create_mysql_engine()
        rows = write_country_month_mart(engine, mart)
        console.print(f"[green]wrote[/green] {rows} rows to mart_country_month_food_security")


@app.command("sample-context")
def sample_context(
    output: Path = typer.Option(
        Path("data/raw/fewsnet_context.csv"),
        help="Where to write synthetic FEWS NET/IPC context.",
    ),
    start_year: int = typer.Option(2021, help="First sample year."),
    end_year: int = typer.Option(2023, help="Last sample year."),
) -> None:
    """Generate synthetic FEWS NET/IPC context aligned with the sample drought."""

    frame = generate_fewsnet_context(start_year=start_year, end_year=end_year)
    frame = normalize_fewsnet_context(frame, source_dataset="synthetic")
    write_normalized_csv(frame, output)
    console.print(f"[green]wrote[/green] {len(frame)} context rows: {output}")


@app.command("ingest-context")
def ingest_context(
    input_csv: Path = typer.Option(..., help="FEWS NET/IPC-style context CSV."),
    output: Path = typer.Option(
        Path("data/raw/fewsnet_context.csv"),
        help="Normalized context output.",
    ),
    raw_dir: Path = typer.Option(Path("data/raw"), help="Directory for the manifest."),
    version: str = typer.Option("context", help="Source version recorded in the manifest."),
) -> None:
    """Normalize a FEWS NET/IPC-style context table into the staging schema."""

    raw = pd.read_csv(input_csv)
    frame = normalize_fewsnet_context(raw)
    write_normalized_csv(frame, output)
    console.print(f"[green]wrote[/green] {len(frame)} context rows: {output}")

    entry = build_entry(
        dataset="fewsnet_context",
        source="FEWS NET / IPC context",
        version=version,
        downloaded_at=datetime.now(timezone.utc).isoformat(),
        file_path=output,
        manifest_dir=raw_dir,
    )
    update_manifest(raw_dir / "manifest.json", entry)
    console.print("[green]recorded[/green] manifest entry: fewsnet_context")


@app.command("load-context")
def load_context(
    input_csv: Path = typer.Option(
        Path("data/raw/fewsnet_context.csv"),
        help="Normalized context CSV.",
    ),
    append: bool = typer.Option(False, help="Append instead of replacing the table."),
) -> None:
    """Load FEWS NET/IPC context into the MySQL fewsnet_context table."""

    engine = create_mysql_engine()
    frame = pd.read_csv(input_csv)
    rows = load_fewsnet_context(engine, frame, replace=not append)
    console.print(f"[green]loaded[/green] {rows} rows into fewsnet_context")


@app.command("join-context")
def join_context(
    risk_csv: Path = typer.Option(..., help="Risk output CSV (scores or monthly mart)."),
    output: Path = typer.Option(
        Path("reports/sample_run/risk_with_context.csv"),
        help="Where to write the context-annotated risk output.",
    ),
    level: str = typer.Option("year", help="Join grain: 'year' or 'month'."),
    context_source: str = typer.Option("mysql", help="Read context from 'mysql' or 'csv'."),
    context_csv: Path = typer.Option(
        Path("data/raw/fewsnet_context.csv"),
        help="Context CSV when --context-source=csv.",
    ),
) -> None:
    """Attach FEWS NET/IPC context to a risk output as reference (never a label)."""

    risk = pd.read_csv(risk_csv)
    if context_source == "mysql":
        engine = create_mysql_engine()
        context = read_fewsnet_context(engine)
    elif context_source == "csv":
        context = pd.read_csv(context_csv)
    else:
        raise typer.BadParameter("context-source must be 'mysql' or 'csv'.")

    annotated = join_context_to_risk(risk, context, level=level)
    write_normalized_csv(annotated, output)
    matched = int(annotated["context_ipc_phase"].notna().sum())
    console.print(
        f"[green]wrote[/green] {len(annotated)} rows ({matched} with context): {output}"
    )


if __name__ == "__main__":
    app()
