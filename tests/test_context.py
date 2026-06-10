from __future__ import annotations

import pandas as pd
import pytest

from food_security_risk.context.fewsnet import (
    IPC_PHASE_LABELS,
    ipc_phase_label,
    join_context_to_risk,
    normalize_fewsnet_context,
    validate_fewsnet_context,
)
from food_security_risk.sample_data import generate_fewsnet_context


def _context_input() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "country_code": ["ken", "KEN", "ETH"],
            "country_name": ["Kenya", "Kenya", "Ethiopia"],
            "year": [2022, 2022, 2022],
            "month": [4, 7, 4],
            "ipc_phase": [3, 4, 2],
            "classification_type": ["Current", "current", "projected"],
            "narrative": ["dry", "worse", None],
        }
    )


def test_ipc_phase_label_lookup() -> None:
    assert ipc_phase_label(3) == "Crisis"
    assert ipc_phase_label(5) == IPC_PHASE_LABELS[5] == "Famine"
    assert ipc_phase_label(None) is None
    assert ipc_phase_label(99) is None


def test_normalize_uppercases_codes_and_adds_labels() -> None:
    frame = normalize_fewsnet_context(_context_input())
    validate_fewsnet_context(frame)
    assert set(frame["country_code"]) == {"KEN", "ETH"}
    assert frame.loc[frame["ipc_phase"] == 4, "ipc_phase_label"].iloc[0] == "Emergency"
    # classification_type is lowercased.
    assert set(frame["classification_type"]) <= {"current", "projected"}


def test_normalize_fills_optional_columns() -> None:
    minimal = pd.DataFrame(
        {
            "country_code": ["KEN"],
            "country_name": ["Kenya"],
            "year": [2022],
            "ipc_phase": [3],
            "classification_type": ["current"],
        }
    )
    frame = normalize_fewsnet_context(minimal)
    for col in ("area_name", "month", "narrative", "as_of_date", "source"):
        assert col in frame.columns


def test_validate_rejects_bad_phase() -> None:
    bad = _context_input()
    bad.loc[0, "ipc_phase"] = 7
    # normalize validates internally, so the out-of-range phase is caught there.
    with pytest.raises(ValueError, match="ipc_phase"):
        normalize_fewsnet_context(bad)


def test_validate_rejects_bad_classification_type() -> None:
    frame = normalize_fewsnet_context(_context_input())
    frame.loc[0, "classification_type"] = "forecast"
    with pytest.raises(ValueError, match="classification_type"):
        validate_fewsnet_context(frame)


def test_join_year_level_keeps_worst_phase_and_preserves_risk_rows() -> None:
    context = normalize_fewsnet_context(_context_input())
    risk = pd.DataFrame(
        {
            "country_code": ["KEN", "ETH", "NGA"],
            "year": [2022, 2022, 2022],
            "food_security_risk_score": [70.0, 40.0, 10.0],
        }
    )
    joined = join_context_to_risk(risk, context, level="year")

    assert len(joined) == 3  # no risk rows dropped
    ken = joined[joined["country_code"] == "KEN"].iloc[0]
    assert ken["context_ipc_phase"] == 4  # worst of phases 3 and 4
    assert ken["context_ipc_phase_label"] == "Emergency"
    assert ken["context_n_records"] == 2
    # NGA has no context -> missing, not zero.
    nga = joined[joined["country_code"] == "NGA"].iloc[0]
    assert pd.isna(nga["context_ipc_phase"])


def test_join_month_level_uses_month_key() -> None:
    context = normalize_fewsnet_context(_context_input())
    risk = pd.DataFrame(
        {
            "country_code": ["KEN", "KEN"],
            "year": [2022, 2022],
            "month": [4, 7],
            "food_security_risk_score": [55.0, 80.0],
        }
    )
    joined = join_context_to_risk(risk, context, level="month")
    by_month = dict(zip(joined["month"], joined["context_ipc_phase"], strict=True))
    assert by_month[4] == 3
    assert by_month[7] == 4


def test_join_flags_projection() -> None:
    context = normalize_fewsnet_context(_context_input())
    risk = pd.DataFrame({"country_code": ["ETH"], "year": [2022]})
    joined = join_context_to_risk(risk, context, level="year")
    assert joined.iloc[0]["context_has_projection"] == 1


def test_sample_context_is_valid_and_flags_drought_countries() -> None:
    raw = generate_fewsnet_context(start_year=2021, end_year=2023)
    frame = normalize_fewsnet_context(raw, source_dataset="synthetic")
    validate_fewsnet_context(frame)

    # Kenya in 2022 should reach at least Crisis (phase 3) in the context.
    ken_2022 = frame[(frame["country_code"] == "KEN") & (frame["year"] == 2022)]
    assert ken_2022["ipc_phase"].max() >= 3
    # A non-drought country stays low.
    nga_2022 = frame[(frame["country_code"] == "NGA") & (frame["year"] == 2022)]
    assert nga_2022["ipc_phase"].max() <= 2
