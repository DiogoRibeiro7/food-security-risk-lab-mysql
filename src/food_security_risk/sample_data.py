"""Synthetic food-security data generation.

The generated data has the same columns expected by the MySQL staging tables.
It is not meant to be realistic enough for research. It exists to make the
workflow reproducible without downloading external datasets.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SampleCountry:
    """Country metadata used by the sample generator."""

    code: str
    name: str
    rainfall_baseline_mm: float
    production_baseline_tonnes: float
    affordability_baseline_ratio: float


COUNTRIES: tuple[SampleCountry, ...] = (
    SampleCountry("KEN", "Kenya", 650.0, 4_200_000.0, 0.54),
    SampleCountry("ETH", "Ethiopia", 780.0, 7_500_000.0, 0.61),
    SampleCountry("NGA", "Nigeria", 1_050.0, 12_000_000.0, 0.48),
    SampleCountry("SOM", "Somalia", 300.0, 900_000.0, 0.73),
    SampleCountry("MOZ", "Mozambique", 920.0, 2_800_000.0, 0.57),
    SampleCountry("BGD", "Bangladesh", 2_100.0, 36_000_000.0, 0.43),
)


def _validate_year_range(start_year: int, end_year: int) -> None:
    """Validate the year range passed by the user."""

    if start_year > end_year:
        raise ValueError("start_year must be less than or equal to end_year.")
    if start_year < 1980:
        raise ValueError("start_year is unexpectedly old for this sample generator.")


def generate_sample_tables(
    start_year: int = 2010,
    end_year: int = 2024,
    seed: int = 42,
) -> dict[str, pd.DataFrame]:
    """Generate synthetic country-year tables.

    Parameters
    ----------
    start_year:
        First year to generate.
    end_year:
        Last year to generate.
    seed:
        Random seed for reproducibility.

    Returns
    -------
    dict[str, pandas.DataFrame]
        DataFrames keyed by logical table name.
    """

    _validate_year_range(start_year=start_year, end_year=end_year)
    rng = np.random.default_rng(seed)
    years = list(range(start_year, end_year + 1))

    rainfall_rows: list[dict[str, object]] = []
    crop_rows: list[dict[str, object]] = []
    affordability_rows: list[dict[str, object]] = []

    for country in COUNTRIES:
        trend = rng.normal(loc=-0.006, scale=0.005)
        affordability_trend = rng.normal(loc=0.015, scale=0.006)

        for idx, year in enumerate(years):
            is_drought = country.code in {"KEN", "SOM", "ETH"} and year in {2016, 2017, 2022}
            drought_shock = -0.28 if is_drought else 0.0
            rainfall_noise = rng.normal(loc=0.0, scale=0.11)
            rainfall_factor = max(0.35, 1.0 + trend * idx + rainfall_noise + drought_shock)
            rainfall_mm = country.rainfall_baseline_mm * rainfall_factor
            rainfall_anomaly_pct = ((rainfall_mm / country.rainfall_baseline_mm) - 1.0) * 100.0

            crop_noise = rng.normal(loc=0.0, scale=0.08)
            crop_factor = max(0.25, 1.0 + 0.45 * (rainfall_factor - 1.0) + crop_noise)
            production_tonnes = country.production_baseline_tonnes * crop_factor
            production_anomaly_pct = (
                (production_tonnes / country.production_baseline_tonnes) - 1.0
            ) * 100.0

            affordability_noise = rng.normal(loc=0.0, scale=0.04)
            affordability_factor = max(
                0.2,
                1.0 + affordability_trend * idx - 0.25 * (crop_factor - 1.0) + affordability_noise,
            )
            affordability_ratio = country.affordability_baseline_ratio * affordability_factor
            affordability_anomaly_pct = (
                (affordability_ratio / country.affordability_baseline_ratio) - 1.0
            ) * 100.0

            rainfall_rows.append(
                {
                    "country_code": country.code,
                    "country_name": country.name,
                    "year": year,
                    "rainfall_mm": round(rainfall_mm, 2),
                    "rainfall_baseline_mm": country.rainfall_baseline_mm,
                    "rainfall_anomaly_pct": round(rainfall_anomaly_pct, 3),
                    "source_dataset": "synthetic",
                }
            )
            crop_rows.append(
                {
                    "country_code": country.code,
                    "country_name": country.name,
                    "year": year,
                    "crop_group": "cereals",
                    "production_tonnes": round(production_tonnes, 2),
                    "production_baseline_tonnes": country.production_baseline_tonnes,
                    "production_anomaly_pct": round(production_anomaly_pct, 3),
                    "source_dataset": "synthetic",
                }
            )
            affordability_rows.append(
                {
                    "country_code": country.code,
                    "country_name": country.name,
                    "year": year,
                    "healthy_diet_cost_ppp": round(3.0 * affordability_factor, 3),
                    "affordability_ratio": round(affordability_ratio, 4),
                    "affordability_baseline_ratio": country.affordability_baseline_ratio,
                    "affordability_anomaly_pct": round(affordability_anomaly_pct, 3),
                    "source_dataset": "synthetic",
                }
            )

    return {
        "rainfall_country_year": pd.DataFrame(rainfall_rows),
        "crop_production_country_year": pd.DataFrame(crop_rows),
        "food_affordability_country_year": pd.DataFrame(affordability_rows),
    }


def write_sample_tables(
    output_dir: Path,
    start_year: int = 2010,
    end_year: int = 2024,
    seed: int = 42,
) -> dict[str, Path]:
    """Generate and write sample CSV files.

    Parameters
    ----------
    output_dir:
        Directory where CSV files will be written.
    start_year:
        First sample year.
    end_year:
        Last sample year.
    seed:
        Random seed.

    Returns
    -------
    dict[str, pathlib.Path]
        Written file paths keyed by logical table name.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    tables = generate_sample_tables(start_year=start_year, end_year=end_year, seed=seed)
    paths: dict[str, Path] = {}

    for name, frame in tables.items():
        path = output_dir / f"{name}.csv"
        frame.to_csv(path, index=False)
        paths[name] = path

    return paths


# A simple seasonal rainfall shape (share of annual rainfall by calendar month).
# It is a generic bimodal-ish profile, not a specific climate; it just gives the
# monthly mart a realistic seasonal signal to compute anomalies against.
_MONTHLY_SEASONAL_SHAPE: tuple[float, ...] = (
    0.02, 0.03, 0.06, 0.12, 0.16, 0.13, 0.08, 0.06, 0.07, 0.11, 0.10, 0.06,
)


def generate_monthly_rainfall(
    start_year: int = 2018,
    end_year: int = 2024,
    seed: int = 7,
) -> pd.DataFrame:
    """Generate synthetic monthly rainfall with seasonality and a drought episode.

    The series follows a fixed seasonal shape scaled by each country's annual
    baseline, with multiplicative noise. A multi-month drought is injected for a
    subset of countries so the rolling-deficit and deterioration signals in the
    country-month mart have something to detect.

    Returns a frame matching ``raw_rainfall_country_month`` (minus provenance).
    """

    _validate_year_range(start_year=start_year, end_year=end_year)
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []

    for country in COUNTRIES:
        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                seasonal_share = _MONTHLY_SEASONAL_SHAPE[month - 1]
                expected_mm = country.rainfall_baseline_mm * seasonal_share
                noise = rng.normal(loc=1.0, scale=0.15)
                drought = (
                    0.45
                    if (country.code in {"KEN", "SOM", "ETH"} and year == 2022 and 3 <= month <= 8)
                    else 1.0
                )
                rainfall_mm = max(0.0, expected_mm * noise * drought)
                rows.append(
                    {
                        "country_code": country.code,
                        "country_name": country.name,
                        "year": year,
                        "month": month,
                        "rainfall_mm": round(rainfall_mm, 2),
                    }
                )

    return pd.DataFrame(rows)
