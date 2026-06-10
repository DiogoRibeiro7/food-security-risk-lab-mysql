"""Normalization of real-world source data into the raw staging schema.

The downloaders in this package fetch raw bytes without making assumptions about
the analytical schema. This module is the deliberate boundary where heterogeneous
external data (World Bank JSON, FAOSTAT bulk CSV, rainfall summaries) is turned
into the exact country-year tables the MySQL staging layer expects.

Two principles guide the code here:

1. **Baselines are computed, not invented.** The synthetic generator fakes a
   baseline column. For real data we compute a reference-period baseline per
   country (or per country/group) and express each observation as a percentage
   anomaly from that baseline. The reference period is explicit and configurable.
2. **Country harmonization is out of scope for v0.2.** ISO3 codes are taken
   verbatim where the source provides them (World Bank), or resolved through an
   explicit caller-supplied map (FAOSTAT). Unmapped rows are dropped and reported
   rather than silently guessed. Full harmonization is v0.3.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pandas as pd


@dataclass(frozen=True)
class CountryRef:
    """An ISO3 code and display name for a source-specific country entry."""

    iso3: str
    name: str


# Minimal FAOSTAT-area to ISO3 map covering the countries used elsewhere in this
# prototype. It is intentionally small and explicit: complete, audited country
# harmonization is the v0.3 milestone, not a guess buried in the ingestion code.
DEFAULT_FAOSTAT_COUNTRY_MAP: dict[str, CountryRef] = {
    "Kenya": CountryRef("KEN", "Kenya"),
    "Ethiopia": CountryRef("ETH", "Ethiopia"),
    "Nigeria": CountryRef("NGA", "Nigeria"),
    "Somalia": CountryRef("SOM", "Somalia"),
    "Mozambique": CountryRef("MOZ", "Mozambique"),
    "Bangladesh": CountryRef("BGD", "Bangladesh"),
}


def compute_baseline_anomaly(
    frame: pd.DataFrame,
    *,
    value_col: str,
    baseline_col: str,
    anomaly_col: str,
    group_cols: Iterable[str],
    baseline_years: tuple[int, int] | None = None,
    year_col: str = "year",
) -> pd.DataFrame:
    """Add a per-group baseline column and a percentage anomaly column.

    The baseline is the mean of ``value_col`` over the rows of each group whose
    year falls within ``baseline_years`` (inclusive). When ``baseline_years`` is
    ``None`` the baseline is the mean over every available year for the group.

    The anomaly is ``(value / baseline - 1) * 100``. Groups whose baseline is
    zero or missing receive a missing (``NaN``) anomaly rather than an infinity,
    so downstream consumers can treat it as missingness.

    Parameters
    ----------
    frame:
        Tidy country-year frame. Not mutated in place.
    value_col:
        Column holding the observed value.
    baseline_col:
        Name of the baseline column to create.
    anomaly_col:
        Name of the anomaly-percentage column to create.
    group_cols:
        Columns identifying a series (e.g. ``["country_code"]`` or
        ``["country_code", "crop_group"]``).
    baseline_years:
        Inclusive ``(first, last)`` reference window. ``None`` uses all years.
    year_col:
        Name of the year column.

    Returns
    -------
    pandas.DataFrame
        A copy of ``frame`` with ``baseline_col`` and ``anomaly_col`` added.
    """

    group_cols = list(group_cols)
    if not group_cols:
        raise ValueError("group_cols must contain at least one column.")
    missing = {value_col, year_col, *group_cols}.difference(frame.columns)
    if missing:
        raise ValueError(f"frame is missing columns: {', '.join(sorted(missing))}")

    result = frame.copy()

    if baseline_years is not None:
        first, last = baseline_years
        if first > last:
            raise ValueError("baseline_years must be (first, last) with first <= last.")
        window = result[(result[year_col] >= first) & (result[year_col] <= last)]
        baseline = window.groupby(group_cols)[value_col].mean()
    else:
        baseline = result.groupby(group_cols)[value_col].mean()

    baseline = baseline.rename(baseline_col)
    result = result.merge(baseline, left_on=group_cols, right_index=True, how="left")

    safe_baseline = result[baseline_col].where(result[baseline_col] != 0.0)
    result[anomaly_col] = (result[value_col] / safe_baseline - 1.0) * 100.0
    return cast(pd.DataFrame, result)


# --------------------------------------------------------------------------- #
# World Bank
# --------------------------------------------------------------------------- #


def parse_world_bank_response(payload: object) -> pd.DataFrame:
    """Parse a World Bank API v2 indicator response into a tidy long frame.

    The World Bank API returns a two-element JSON array: ``[metadata, records]``.
    Each record carries an ``indicator``, a ``country``, an ISO3 code, a date,
    and a value. This accepts either the already-decoded object, a JSON string,
    or raw ``bytes``.

    Rows without a numeric value or without an ISO3 code are dropped: the API
    emits aggregate rows (regions, income groups) whose ``countryiso3code`` is
    blank, and those are not country observations.

    Returns
    -------
    pandas.DataFrame
        Columns: ``indicator_code``, ``country_code``, ``country_name``,
        ``year``, ``value``.
    """

    if isinstance(payload, (bytes, bytearray)):
        payload = json.loads(payload.decode("utf-8"))
    elif isinstance(payload, str):
        payload = json.loads(payload)

    if not isinstance(payload, list) or len(payload) < 2:
        message = payload[0].get("message") if isinstance(payload, list) and payload else None
        raise ValueError(f"Unexpected World Bank response shape; message={message!r}")

    records = payload[1] or []
    rows: list[dict[str, object]] = []
    for record in records:
        iso3 = (record.get("countryiso3code") or "").strip()
        value = record.get("value")
        if not iso3 or value is None:
            continue
        rows.append(
            {
                "indicator_code": (record.get("indicator") or {}).get("id"),
                "country_code": iso3,
                "country_name": (record.get("country") or {}).get("value"),
                "year": int(record["date"]),
                "value": float(value),
            }
        )

    columns = ["indicator_code", "country_code", "country_name", "year", "value"]
    frame = pd.DataFrame(rows, columns=columns)
    sorted_frame = frame.sort_values(["country_code", "year"]).reset_index(drop=True)
    return cast(pd.DataFrame, sorted_frame)


def normalize_world_bank_affordability(
    payload: object,
    *,
    baseline_years: tuple[int, int] | None = None,
    source_dataset: str = "world_bank",
) -> pd.DataFrame:
    """Normalize a World Bank affordability indicator into the staging schema.

    The indicator value is interpreted as the cost of a healthy diet in PPP terms
    (``healthy_diet_cost_ppp``). The affordability ratio is derived from that cost
    relative to its own country baseline, so a value of ``1.0`` means cost is at
    the reference-period level and values above ``1.0`` mean a less affordable
    diet than baseline. Baseline and anomaly columns are computed per country.

    Returns a frame matching ``raw_food_affordability_country_year``.
    """

    long = parse_world_bank_response(payload)
    if long.empty:
        return _empty_affordability_frame()

    frame = long.rename(columns={"value": "healthy_diet_cost_ppp"})[
        ["country_code", "country_name", "year", "healthy_diet_cost_ppp"]
    ]

    if baseline_years is not None:
        first, last = baseline_years
        window = frame[(frame["year"] >= first) & (frame["year"] <= last)]
        cost_baseline = window.groupby("country_code")["healthy_diet_cost_ppp"].mean()
    else:
        cost_baseline = frame.groupby("country_code")["healthy_diet_cost_ppp"].mean()

    frame = frame.merge(
        cost_baseline.rename("_cost_baseline"),
        left_on="country_code",
        right_index=True,
        how="left",
    )
    safe = frame["_cost_baseline"].where(frame["_cost_baseline"] != 0.0)
    frame["affordability_ratio"] = frame["healthy_diet_cost_ppp"] / safe

    frame = compute_baseline_anomaly(
        frame,
        value_col="affordability_ratio",
        baseline_col="affordability_baseline_ratio",
        anomaly_col="affordability_anomaly_pct",
        group_cols=["country_code"],
        baseline_years=baseline_years,
    )
    frame["source_dataset"] = source_dataset
    affordability = frame[
        [
            "country_code",
            "country_name",
            "year",
            "healthy_diet_cost_ppp",
            "affordability_ratio",
            "affordability_baseline_ratio",
            "affordability_anomaly_pct",
            "source_dataset",
        ]
    ].reset_index(drop=True)
    return cast(pd.DataFrame, affordability)


def _empty_affordability_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "country_code",
            "country_name",
            "year",
            "healthy_diet_cost_ppp",
            "affordability_ratio",
            "affordability_baseline_ratio",
            "affordability_anomaly_pct",
            "source_dataset",
        ]
    )


# --------------------------------------------------------------------------- #
# FAOSTAT
# --------------------------------------------------------------------------- #

# FAOSTAT bulk "Production" downloads use these long-format column names.
_FAOSTAT_AREA_COL = "Area"
_FAOSTAT_AREA_CODE_COL = "Area Code"
_FAOSTAT_ELEMENT_COL = "Element"
_FAOSTAT_YEAR_COL = "Year"
_FAOSTAT_VALUE_COL = "Value"
_FAOSTAT_UNIT_COL = "Unit"


def normalize_faostat_production(
    frame: pd.DataFrame,
    *,
    country_map: Mapping[str, CountryRef],
    crop_group: str,
    baseline_years: tuple[int, int] | None = None,
    element: str = "Production",
    source_dataset: str = "faostat",
) -> tuple[pd.DataFrame, list[str]]:
    """Normalize a FAOSTAT bulk production frame into the staging schema.

    FAOSTAT identifies countries by ``Area`` name (and M49 ``Area Code``), not by
    ISO3. Because country harmonization is a later milestone, the caller supplies
    an explicit ``country_map`` keyed by FAOSTAT ``Area`` name. Areas absent from
    the map are dropped and returned in the second element so the caller can log
    or fail on unmapped coverage rather than silently losing data.

    Production rows are summed across items within ``crop_group`` per country-year
    (FAOSTAT bulk files list one row per item), then a per-country baseline and
    anomaly are computed.

    Parameters
    ----------
    frame:
        Raw FAOSTAT long-format frame (one row per area/item/element/year).
    country_map:
        Mapping from FAOSTAT ``Area`` name to :class:`CountryRef`.
    crop_group:
        Label written to the ``crop_group`` column (e.g. ``"cereals"``).
    baseline_years:
        Reference window for the baseline; ``None`` uses all years.
    element:
        FAOSTAT element to keep (default ``"Production"``).
    source_dataset:
        Provenance tag written to ``source_dataset``.

    Returns
    -------
    tuple[pandas.DataFrame, list[str]]
        The staging frame and a sorted list of unmapped FAOSTAT area names.
    """

    required = {_FAOSTAT_AREA_COL, _FAOSTAT_ELEMENT_COL, _FAOSTAT_YEAR_COL, _FAOSTAT_VALUE_COL}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"FAOSTAT frame is missing columns: {', '.join(sorted(missing))}")

    production = frame[frame[_FAOSTAT_ELEMENT_COL] == element].copy()

    present_areas = set(production[_FAOSTAT_AREA_COL].unique())
    unmapped = sorted(present_areas.difference(country_map.keys()))

    production = production[production[_FAOSTAT_AREA_COL].isin(country_map.keys())]
    if production.empty:
        return _empty_crop_frame(), unmapped

    production["country_code"] = production[_FAOSTAT_AREA_COL].map(lambda a: country_map[a].iso3)
    production["country_name"] = production[_FAOSTAT_AREA_COL].map(lambda a: country_map[a].name)
    production["year"] = production[_FAOSTAT_YEAR_COL].astype(int)
    production["production_tonnes"] = pd.to_numeric(production[_FAOSTAT_VALUE_COL], errors="coerce")

    grouped = production.groupby(
        ["country_code", "country_name", "year"], as_index=False
    )["production_tonnes"].sum()
    grouped["crop_group"] = crop_group

    grouped = compute_baseline_anomaly(
        grouped,
        value_col="production_tonnes",
        baseline_col="production_baseline_tonnes",
        anomaly_col="production_anomaly_pct",
        group_cols=["country_code", "crop_group"],
        baseline_years=baseline_years,
    )
    grouped["source_dataset"] = source_dataset
    staging = grouped[
        [
            "country_code",
            "country_name",
            "year",
            "crop_group",
            "production_tonnes",
            "production_baseline_tonnes",
            "production_anomaly_pct",
            "source_dataset",
        ]
    ].sort_values(["country_code", "year"]).reset_index(drop=True)
    return cast(pd.DataFrame, staging), unmapped


def _empty_crop_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "country_code",
            "country_name",
            "year",
            "crop_group",
            "production_tonnes",
            "production_baseline_tonnes",
            "production_anomaly_pct",
            "source_dataset",
        ]
    )


# --------------------------------------------------------------------------- #
# Rainfall
# --------------------------------------------------------------------------- #

_RAINFALL_INPUT_REQUIRED = {"country_code", "country_name", "year", "rainfall_mm"}


def normalize_rainfall_summary(
    frame: pd.DataFrame,
    *,
    baseline_years: tuple[int, int] | None = None,
    source_dataset: str = "chirps",
) -> pd.DataFrame:
    """Normalize a country-year rainfall summary into the staging schema.

    The input contract is intentionally small: a tidy frame with
    ``country_code``, ``country_name``, ``year``, and ``rainfall_mm`` (e.g. a
    CHIRPS country-year summary). A per-country baseline and anomaly are computed.
    Gridded rainfall aggregation is deferred to a later milestone.

    Returns a frame matching ``raw_rainfall_country_year``.
    """

    missing = _RAINFALL_INPUT_REQUIRED.difference(frame.columns)
    if missing:
        raise ValueError(f"rainfall summary is missing columns: {', '.join(sorted(missing))}")

    result = frame[["country_code", "country_name", "year", "rainfall_mm"]].copy()
    result["year"] = result["year"].astype(int)
    result["rainfall_mm"] = pd.to_numeric(result["rainfall_mm"], errors="coerce")

    result = compute_baseline_anomaly(
        result,
        value_col="rainfall_mm",
        baseline_col="rainfall_baseline_mm",
        anomaly_col="rainfall_anomaly_pct",
        group_cols=["country_code"],
        baseline_years=baseline_years,
    )
    result["source_dataset"] = source_dataset
    rainfall = result[
        [
            "country_code",
            "country_name",
            "year",
            "rainfall_mm",
            "rainfall_baseline_mm",
            "rainfall_anomaly_pct",
            "source_dataset",
        ]
    ].sort_values(["country_code", "year"]).reset_index(drop=True)
    return cast(pd.DataFrame, rainfall)


_RAINFALL_MONTH_REQUIRED = {"country_code", "country_name", "year", "month", "rainfall_mm"}


def normalize_rainfall_country_month(
    frame: pd.DataFrame,
    *,
    source_dataset: str = "chirps",
) -> pd.DataFrame:
    """Normalize a monthly rainfall table into the raw monthly staging schema.

    Unlike the country-year normalizer, no baseline is computed here: monthly
    baselines are *seasonal* (per calendar month) and belong in the country-month
    mart, not in the raw staging table. This keeps the raw layer a faithful copy
    of the source observations.

    Returns a frame matching ``raw_rainfall_country_month``.
    """

    missing = _RAINFALL_MONTH_REQUIRED.difference(frame.columns)
    if missing:
        raise ValueError(f"monthly rainfall is missing columns: {', '.join(sorted(missing))}")

    result = frame[["country_code", "country_name", "year", "month", "rainfall_mm"]].copy()
    result["country_code"] = result["country_code"].astype(str).str.upper().str.strip()
    result["year"] = result["year"].astype(int)
    result["month"] = result["month"].astype(int)
    if not result["month"].between(1, 12).all():
        raise ValueError("month values must be in 1..12.")
    result["rainfall_mm"] = pd.to_numeric(result["rainfall_mm"], errors="coerce")
    result["source_dataset"] = source_dataset

    ordered = result.sort_values(["country_code", "year", "month"]).reset_index(drop=True)
    return cast(pd.DataFrame, ordered)


def write_normalized_csv(frame: pd.DataFrame, output_path: Path) -> Path:
    """Write a normalized staging frame to CSV, creating parent directories."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False)
    return output_path
