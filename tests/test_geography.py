from __future__ import annotations

import pandas as pd

from food_security_risk.geography.harmonization import CountryHarmonizer, MatchQuality
from food_security_risk.ingestion.normalize import normalize_faostat_production


def _harmonizer() -> CountryHarmonizer:
    return CountryHarmonizer()


def test_exact_match_by_canonical_name() -> None:
    res = _harmonizer().resolve("Kenya")
    assert res.iso3 == "KEN"
    assert res.quality is MatchQuality.EXACT
    assert res.is_confident


def test_exact_match_is_case_and_whitespace_insensitive() -> None:
    res = _harmonizer().resolve("  kEnYa  ")
    assert res.iso3 == "KEN"
    assert res.quality is MatchQuality.EXACT


def test_exact_match_by_iso3_code() -> None:
    res = _harmonizer().resolve("ETH")
    assert res.iso3 == "ETH"
    assert res.quality is MatchQuality.EXACT


def test_alias_spellings_resolve() -> None:
    harm = _harmonizer()
    assert harm.resolve("Ivory Coast").iso3 == "CIV"
    assert harm.resolve("Côte d'Ivoire").iso3 == "CIV"
    assert harm.resolve("Tanzania").iso3 == "TZA"
    assert harm.resolve("Swaziland").iso3 == "SWZ"
    assert harm.resolve("Congo, Dem. Rep.").iso3 == "COD"
    for name in ["Ivory Coast", "Tanzania", "Swaziland"]:
        assert harm.resolve(name).quality is MatchQuality.ALIAS


def test_ambiguous_name_is_flagged_not_guessed() -> None:
    res = _harmonizer().resolve("Congo")
    assert res.quality is MatchQuality.AMBIGUOUS
    assert res.iso3 is None
    assert set(res.candidates) == {"COD", "COG"}
    assert not res.is_confident


def test_historical_entity_is_flagged() -> None:
    res = _harmonizer().resolve("USSR")
    assert res.quality is MatchQuality.HISTORICAL
    assert res.iso3 is None
    assert not res.is_confident


def test_unresolved_name() -> None:
    res = _harmonizer().resolve("Atlantis")
    assert res.quality is MatchQuality.UNRESOLVED
    assert res.iso3 is None


def test_alias_to_iso3_outside_reference_is_not_confident() -> None:
    # "Gambia, the" maps to GMB, which has no canonical row in this prototype.
    res = _harmonizer().resolve("Gambia, the")
    assert res.iso3 == "GMB"
    assert res.quality is MatchQuality.ALIAS
    assert res.country_name is None
    assert not res.is_confident  # excluded from confident joins until dim added


def test_dim_country_frame_has_expected_schema() -> None:
    frame = _harmonizer().dim_country_frame()
    assert list(frame.columns) == ["iso3", "iso2", "m49", "country_name", "region"]
    assert (frame["iso3"].str.len() == 3).all()
    assert frame["iso3"].is_unique


def test_build_source_mapping_dedupes_and_flags() -> None:
    names = ["Kenya", "Kenya", "Congo", "Atlantis", "Ivory Coast"]
    mapping = _harmonizer().build_source_mapping(names, source="faostat")
    assert len(mapping) == 4  # Kenya collapsed
    flags = dict(zip(mapping["source_name"], mapping["quality_flag"], strict=True))
    assert flags["Kenya"] == "exact"
    assert flags["Congo"] == "ambiguous"
    assert flags["Atlantis"] == "unresolved"
    assert flags["Ivory Coast"] == "alias"


def test_quality_report_counts_by_flag() -> None:
    names = ["Kenya", "Ethiopia", "Congo", "Atlantis"]
    harm = _harmonizer()
    mapping = harm.build_source_mapping(names, source="faostat")
    report = harm.quality_report(mapping)
    counts = dict(zip(report["quality_flag"], report["name_count"], strict=True))
    assert counts["exact"] == 2
    assert counts["ambiguous"] == 1
    assert counts["unresolved"] == 1


def test_build_country_map_feeds_faostat_normalizer() -> None:
    raw = pd.DataFrame(
        {
            "Area": ["Ivory Coast", "Ivory Coast", "Congo"],
            "Item": ["Maize", "Maize", "Maize"],
            "Element": ["Production", "Production", "Production"],
            "Year": [2019, 2020, 2020],
            "Unit": ["t", "t", "t"],
            "Value": [100.0, 120.0, 50.0],
        }
    )
    harm = _harmonizer()
    country_map, mapping = harm.build_country_map(raw["Area"].tolist())

    # Ivory Coast resolves (alias -> CIV); Congo is ambiguous and excluded.
    assert "Ivory Coast" in country_map
    assert country_map["Ivory Coast"].iso3 == "CIV"
    assert "Congo" not in country_map

    frame, unmapped = normalize_faostat_production(
        raw, country_map=country_map, crop_group="cereals"
    )
    assert set(frame["country_code"]) == {"CIV"}
    assert unmapped == ["Congo"]
