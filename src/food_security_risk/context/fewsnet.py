"""FEWS NET / IPC-style context layer.

This module adds a *contextual* humanitarian reference layer. It is deliberately
kept separate from scoring and is **not** a ground-truth label:

- The risk score in this project is a transparent function of rainfall, crop,
  and affordability indicators. It is intentionally not fitted to reproduce IPC
  or FEWS NET classifications.
- IPC phases reflect expert analysis with their own methodology, spatial
  granularity, and temporal scope. Joining them to the risk output lets an
  analyst *compare* the two; it does not make one a target for the other.

The join helpers therefore attach context columns under a ``context_`` prefix so
it is always visually obvious in a downstream table that those values are
reference context, not model inputs or outputs.
"""

from __future__ import annotations

from typing import cast

import pandas as pd

# IPC Acute Food Insecurity phase classification.
IPC_PHASE_LABELS: dict[int, str] = {
    1: "Minimal",
    2: "Stressed",
    3: "Crisis",
    4: "Emergency",
    5: "Famine",
}

VALID_CLASSIFICATION_TYPES: frozenset[str] = frozenset({"current", "projected"})

CONTEXT_COLUMNS: tuple[str, ...] = (
    "country_code",
    "country_name",
    "area_name",
    "year",
    "month",
    "ipc_phase",
    "ipc_phase_label",
    "classification_type",
    "narrative",
    "source",
    "as_of_date",
)

_REQUIRED_INPUT = {"country_code", "country_name", "year", "ipc_phase", "classification_type"}


def ipc_phase_label(phase: object) -> str | None:
    """Return the IPC label for a phase value, or ``None`` if unknown/missing."""

    if phase is None or (isinstance(phase, float) and pd.isna(phase)):
        return None
    if isinstance(phase, (int, float)):
        return IPC_PHASE_LABELS.get(int(phase))
    try:
        return IPC_PHASE_LABELS.get(int(str(phase)))
    except (TypeError, ValueError):
        return None


def validate_fewsnet_context(frame: pd.DataFrame) -> None:
    """Validate a normalized FEWS NET context frame."""

    missing = {
        "country_code",
        "country_name",
        "year",
        "ipc_phase",
        "classification_type",
    }.difference(frame.columns)
    if missing:
        raise ValueError(f"context data is missing columns: {', '.join(sorted(missing))}")

    phases = frame["ipc_phase"].dropna()
    if not phases.empty and not phases.astype(int).between(1, 5).all():
        raise ValueError("ipc_phase values must be in 1..5 (or missing).")

    bad_types = set(frame["classification_type"].dropna().unique()) - VALID_CLASSIFICATION_TYPES
    if bad_types:
        raise ValueError(
            f"classification_type must be one of {sorted(VALID_CLASSIFICATION_TYPES)}; "
            f"got {sorted(bad_types)}"
        )


def normalize_fewsnet_context(
    frame: pd.DataFrame,
    *,
    source_dataset: str = "fewsnet",
) -> pd.DataFrame:
    """Normalize a FEWS NET-style context table into the staging schema.

    Required input columns: ``country_code``, ``country_name``, ``year``,
    ``ipc_phase``, ``classification_type``. Optional: ``area_name``, ``month``,
    ``narrative``, ``as_of_date``. The phase label is derived from ``ipc_phase``.

    Returns a frame matching ``fewsnet_context``.
    """

    missing = _REQUIRED_INPUT.difference(frame.columns)
    if missing:
        raise ValueError(f"context input is missing columns: {', '.join(sorted(missing))}")

    result = frame.copy()
    result["country_code"] = result["country_code"].astype(str).str.upper().str.strip()
    result["year"] = result["year"].astype("int64")
    result["ipc_phase"] = pd.to_numeric(result["ipc_phase"], errors="coerce").astype("Int64")
    result["classification_type"] = (
        result["classification_type"].astype(str).str.strip().str.lower()
    )

    for optional in ("area_name", "month", "narrative", "as_of_date"):
        if optional not in result.columns:
            result[optional] = pd.NA
    result["month"] = pd.to_numeric(result["month"], errors="coerce").astype("Int64")
    result["ipc_phase_label"] = result["ipc_phase"].map(ipc_phase_label)
    result["source"] = source_dataset

    validate_fewsnet_context(result)

    ordered = (
        result[list(CONTEXT_COLUMNS)]
        .sort_values(["country_code", "year", "month", "classification_type"])
        .reset_index(drop=True)
    )
    return cast(pd.DataFrame, ordered)


def join_context_to_risk(
    risk: pd.DataFrame,
    context: pd.DataFrame,
    *,
    level: str = "year",
) -> pd.DataFrame:
    """Left-join humanitarian context onto a risk-output table by country/date.

    Context is aggregated to the grain of the risk table and attached under a
    ``context_`` prefix. The aggregation keeps the **worst** (maximum) IPC phase
    observed at that grain, the count of contributing records, and whether any
    record was a projection — enough to compare against the model output without
    pretending a single authoritative label exists.

    Parameters
    ----------
    risk:
        Risk output (e.g. scores or the monthly mart). Must contain
        ``country_code`` and ``year`` (and ``month`` when ``level="month"``).
    context:
        Normalized context frame (see :func:`normalize_fewsnet_context`).
    level:
        ``"year"`` joins on country and year; ``"month"`` joins on country,
        year, and month.

    Returns
    -------
    pandas.DataFrame
        ``risk`` with ``context_*`` columns added. Rows with no matching context
        keep missing context values; risk rows are never dropped.
    """

    if level not in {"year", "month"}:
        raise ValueError("level must be 'year' or 'month'.")
    keys = ["country_code", "year"] + (["month"] if level == "month" else [])

    for name, frame in (("risk", risk), ("context", context)):
        missing = set(keys).difference(frame.columns)
        if missing:
            raise ValueError(f"{name} is missing join keys: {', '.join(sorted(missing))}")

    ctx = context.copy()
    ctx["country_code"] = ctx["country_code"].astype(str).str.upper().str.strip()
    if level == "month":
        ctx = ctx[ctx["month"].notna()]

    def _first_narrative(series: pd.Series) -> object:
        non_null = series.dropna()
        return non_null.iloc[0] if not non_null.empty else pd.NA

    aggregated = ctx.groupby(keys, as_index=False).agg(
        context_ipc_phase=("ipc_phase", "max"),
        context_n_records=("ipc_phase", "size"),
        context_has_projection=(
            "classification_type",
            lambda s: int((s == "projected").any()),
        ),
        context_narrative=("narrative", _first_narrative),
    )
    aggregated["context_ipc_phase_label"] = aggregated["context_ipc_phase"].map(ipc_phase_label)

    out = risk.copy()
    out["country_code"] = out["country_code"].astype(str).str.upper().str.strip()
    merged = out.merge(aggregated, on=keys, how="left")
    return cast(pd.DataFrame, merged)
