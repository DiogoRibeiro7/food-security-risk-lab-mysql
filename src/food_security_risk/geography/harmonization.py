"""Country-name harmonization with explicit, auditable quality flags.

The harmonizer turns heterogeneous source country names into canonical ISO3
codes. Crucially, it never guesses: a name either resolves cleanly (``exact`` or
``alias``), or it is flagged (``ambiguous``, ``historical``, ``unresolved``) and
excluded from the confident mapping. Every decision is recorded so a join can be
audited rather than trusted blindly.

The outputs mirror the v0.3 analytical tables:

- :meth:`CountryHarmonizer.dim_country_frame` -> ``dim_country``
- :meth:`CountryHarmonizer.build_source_mapping` -> ``country_source_mapping``
- :meth:`CountryHarmonizer.quality_report` -> ``country_mapping_quality_report``
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import cast

import pandas as pd

from food_security_risk.geography.reference import (
    AMBIGUOUS_NAMES,
    CANONICAL_COUNTRIES,
    HISTORICAL_NAMES,
    NAME_ALIASES,
    Country,
)
from food_security_risk.ingestion.normalize import CountryRef

_WHITESPACE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Normalize a country name for matching: lowercase, collapsed whitespace."""

    return _WHITESPACE.sub(" ", name.strip()).lower()


class MatchQuality(str, Enum):
    """How confidently a source name was resolved to an ISO3 code."""

    EXACT = "exact"
    ALIAS = "alias"
    AMBIGUOUS = "ambiguous"
    HISTORICAL = "historical"
    UNRESOLVED = "unresolved"


# Qualities that produce a usable, unambiguous ISO3 for joins.
_CONFIDENT = frozenset({MatchQuality.EXACT, MatchQuality.ALIAS})


@dataclass(frozen=True)
class Resolution:
    """The outcome of resolving a single source name."""

    source_name: str
    iso3: str | None
    country_name: str | None
    quality: MatchQuality
    note: str | None = None
    candidates: tuple[str, ...] = ()

    @property
    def is_confident(self) -> bool:
        """True when the name maps to a single canonical-reference country."""

        return (
            self.quality in _CONFIDENT
            and self.iso3 is not None
            and self.country_name is not None
        )


class CountryHarmonizer:
    """Resolves source country names to canonical ISO3 codes with quality flags."""

    def __init__(
        self,
        countries: tuple[Country, ...] = CANONICAL_COUNTRIES,
        aliases: dict[str, str] | None = None,
        ambiguous: dict[str, tuple[str, ...]] | None = None,
        historical: frozenset[str] | None = None,
    ) -> None:
        self._countries = countries
        self._aliases = aliases if aliases is not None else NAME_ALIASES
        self._ambiguous = ambiguous if ambiguous is not None else AMBIGUOUS_NAMES
        self._historical = historical if historical is not None else HISTORICAL_NAMES
        self._by_name = {normalize_name(c.name): c for c in countries}
        self._by_iso3 = {c.iso3: c for c in countries}

    def resolve(self, name: str) -> Resolution:
        """Resolve a single source name to a :class:`Resolution`.

        Resolution order is deliberate: ambiguous and historical names are caught
        before alias/exact matching so a problematic spelling can never slip
        through to a confident mapping.
        """

        norm = normalize_name(name)

        if norm in self._ambiguous:
            return Resolution(
                source_name=name,
                iso3=None,
                country_name=None,
                quality=MatchQuality.AMBIGUOUS,
                note="ambiguous source name; multiple candidates",
                candidates=self._ambiguous[norm],
            )

        if norm in self._historical:
            return Resolution(
                source_name=name,
                iso3=None,
                country_name=None,
                quality=MatchQuality.HISTORICAL,
                note="dissolved or historical entity with no single modern ISO3",
            )

        if norm in self._by_name:
            country = self._by_name[norm]
            return Resolution(name, country.iso3, country.name, MatchQuality.EXACT)

        # A bare ISO3 code passed as the source name also counts as exact.
        if name.strip().upper() in self._by_iso3:
            country = self._by_iso3[name.strip().upper()]
            return Resolution(name, country.iso3, country.name, MatchQuality.EXACT)

        if norm in self._aliases:
            iso3 = self._aliases[norm]
            alias_country = self._by_iso3.get(iso3)
            if alias_country is None:
                return Resolution(
                    source_name=name,
                    iso3=iso3,
                    country_name=None,
                    quality=MatchQuality.ALIAS,
                    note="alias resolves to an ISO3 outside the canonical reference",
                )
            return Resolution(name, alias_country.iso3, alias_country.name, MatchQuality.ALIAS)

        return Resolution(
            source_name=name,
            iso3=None,
            country_name=None,
            quality=MatchQuality.UNRESOLVED,
            note="no canonical match or alias",
        )

    def resolve_many(self, names: list[str]) -> list[Resolution]:
        """Resolve a list of source names, preserving order and duplicates."""

        return [self.resolve(name) for name in names]

    def dim_country_frame(self) -> pd.DataFrame:
        """Return the canonical country dimension as a frame (``dim_country``)."""

        rows = [
            {
                "iso3": c.iso3,
                "iso2": c.iso2,
                "m49": c.m49,
                "country_name": c.name,
                "region": c.region,
            }
            for c in self._countries
        ]
        return pd.DataFrame(rows, columns=["iso3", "iso2", "m49", "country_name", "region"])

    def build_source_mapping(self, names: list[str], source: str) -> pd.DataFrame:
        """Build a ``country_source_mapping`` frame for unique source names.

        Duplicate names collapse to one row. ``candidates`` is rendered as a
        comma-joined string so the frame maps cleanly to a SQL column.
        """

        unique_names = list(dict.fromkeys(names))
        rows = []
        for name in unique_names:
            resolution = self.resolve(name)
            rows.append(
                {
                    "source": source,
                    "source_name": name,
                    "iso3": resolution.iso3,
                    "country_name": resolution.country_name,
                    "quality_flag": resolution.quality.value,
                    "note": resolution.note,
                    "candidates": ",".join(resolution.candidates) or None,
                }
            )
        columns = [
            "source",
            "source_name",
            "iso3",
            "country_name",
            "quality_flag",
            "note",
            "candidates",
        ]
        return pd.DataFrame(rows, columns=columns)

    @staticmethod
    def quality_report(mapping: pd.DataFrame) -> pd.DataFrame:
        """Summarize a source-mapping frame as counts per source and quality flag."""

        if mapping.empty:
            return pd.DataFrame(columns=["source", "quality_flag", "name_count"])
        report = (
            mapping.groupby(["source", "quality_flag"], as_index=False)
            .size()
            .rename(columns={"size": "name_count"})
            .sort_values(["source", "quality_flag"])
            .reset_index(drop=True)
        )
        return cast(pd.DataFrame, report)

    def build_country_map(self, names: list[str]) -> tuple[dict[str, CountryRef], pd.DataFrame]:
        """Build a confident name->:class:`CountryRef` map plus the full mapping.

        Only confidently resolved names (exact/alias with a canonical country)
        enter the returned map; ambiguous, historical, and unresolved names are
        present in the mapping frame for reporting but excluded from the map so
        they cannot pollute a join.
        """

        country_map: dict[str, CountryRef] = {}
        for name in dict.fromkeys(names):
            resolution = self.resolve(name)
            if resolution.is_confident:
                assert resolution.iso3 is not None and resolution.country_name is not None
                country_map[name] = CountryRef(resolution.iso3, resolution.country_name)
        mapping = self.build_source_mapping(names, source="ingest")
        return country_map, mapping
