"""Canonical country reference and source-specific name aliases.

Food-security datasets disagree on country names, ISO codes, and historical
entities. This module holds the small, explicit reference data that the
harmonization layer joins against. It is intentionally curated rather than
exhaustive: it covers the countries used elsewhere in this prototype plus a set
of well-known difficult cases (Congo ambiguity, Côte d'Ivoire spellings,
Eswatini/Swaziland renames, dissolved historical entities).

Everything here is embedded Python so the harmonization layer works offline,
consistent with the rest of the project. Replacing this with an authoritative
M49/ISO reference table is a documented extension point.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Country:
    """A canonical country with its standard codes and region."""

    iso3: str
    iso2: str
    m49: int
    name: str
    region: str


# Canonical reference. ISO3/ISO2/M49 follow UN M49 and ISO 3166-1. The list is
# deliberately scoped to countries this prototype works with, plus neighbours
# that commonly collide in naming.
CANONICAL_COUNTRIES: tuple[Country, ...] = (
    Country("KEN", "KE", 404, "Kenya", "Eastern Africa"),
    Country("ETH", "ET", 231, "Ethiopia", "Eastern Africa"),
    Country("SOM", "SO", 706, "Somalia", "Eastern Africa"),
    Country("UGA", "UG", 800, "Uganda", "Eastern Africa"),
    Country("TZA", "TZ", 834, "United Republic of Tanzania", "Eastern Africa"),
    Country("RWA", "RW", 646, "Rwanda", "Eastern Africa"),
    Country("SSD", "SS", 728, "South Sudan", "Eastern Africa"),
    Country("SDN", "SD", 729, "Sudan", "Northern Africa"),
    Country("NGA", "NG", 566, "Nigeria", "Western Africa"),
    Country("NER", "NE", 562, "Niger", "Western Africa"),
    Country("MLI", "ML", 466, "Mali", "Western Africa"),
    Country("CIV", "CI", 384, "Côte d'Ivoire", "Western Africa"),
    Country("BFA", "BF", 854, "Burkina Faso", "Western Africa"),
    Country("COD", "CD", 180, "Democratic Republic of the Congo", "Middle Africa"),
    Country("COG", "CG", 178, "Congo", "Middle Africa"),
    Country("MOZ", "MZ", 508, "Mozambique", "Eastern Africa"),
    Country("MWI", "MW", 454, "Malawi", "Eastern Africa"),
    Country("ZWE", "ZW", 716, "Zimbabwe", "Eastern Africa"),
    Country("SWZ", "SZ", 748, "Eswatini", "Southern Africa"),
    Country("CPV", "CV", 132, "Cabo Verde", "Western Africa"),
    Country("BGD", "BD", 50, "Bangladesh", "Southern Asia"),
    Country("IND", "IN", 356, "India", "Southern Asia"),
    Country("PAK", "PK", 586, "Pakistan", "Southern Asia"),
    Country("YEM", "YE", 887, "Yemen", "Western Asia"),
    Country("AFG", "AF", 4, "Afghanistan", "Southern Asia"),
    Country("KOR", "KR", 410, "Republic of Korea", "Eastern Asia"),
    Country("PRK", "KP", 408, "Democratic People's Republic of Korea", "Eastern Asia"),
)


# Source-specific aliases mapping an observed source name to a canonical ISO3.
# Keys are matched case-insensitively after whitespace normalization. The same
# alias may legitimately appear from several sources; we keep one table because
# the mappings do not currently conflict across sources. When a single spelling
# is genuinely ambiguous (e.g. "Congo"), it is omitted here and handled by
# AMBIGUOUS_NAMES so the harmonizer can flag it rather than guess.
NAME_ALIASES: dict[str, str] = {
    # FAOSTAT / World Bank spellings
    "tanzania": "TZA",
    "tanzania, united rep. of": "TZA",
    "united republic of tanzania": "TZA",
    "cote d'ivoire": "CIV",
    "côte d'ivoire": "CIV",
    "ivory coast": "CIV",
    "democratic republic of the congo": "COD",
    "dem. rep. of the congo": "COD",
    "congo, dem. rep.": "COD",
    "dr congo": "COD",
    "republic of the congo": "COG",
    "congo, rep.": "COG",
    "swaziland": "SWZ",
    "eswatini": "SWZ",
    "cape verde": "CPV",
    "cabo verde": "CPV",
    "korea, rep.": "KOR",
    "republic of korea": "KOR",
    "south korea": "KOR",
    "korea, dem. people's rep.": "PRK",
    "democratic people's republic of korea": "PRK",
    "north korea": "PRK",
    "gambia, the": "GMB",  # resolves to an ISO3 with no canonical row -> reported
}


# Names that are genuinely ambiguous and must never be silently resolved. Each
# maps to the candidate ISO3 codes so the harmonizer can report the conflict.
AMBIGUOUS_NAMES: dict[str, tuple[str, ...]] = {
    "congo": ("COD", "COG"),
    "korea": ("KOR", "PRK"),
    "sudan (former)": ("SDN", "SSD"),
}


# Dissolved or historical entities with no single modern ISO3. They are flagged
# as historical so analysts see them rather than losing the rows silently.
HISTORICAL_NAMES: frozenset[str] = frozenset(
    {
        "ussr",
        "czechoslovakia",
        "yugoslav sfr",
        "ethiopia pdr",
        "netherlands antilles",
        "serbia and montenegro",
    }
)
