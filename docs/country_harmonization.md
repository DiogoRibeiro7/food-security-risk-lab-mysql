# Country harmonization (v0.3)

Food-security datasets disagree on how they name countries. FAOSTAT, the World
Bank, and humanitarian sources use different spellings, different code systems
(ISO2, ISO3, UN M49), and sometimes refer to entities that no longer exist. If
these names are joined naively, rows are silently dropped or — worse — attached
to the wrong country.

This layer makes every country join **explicit and auditable**. It resolves
source names to canonical ISO3 codes and records *how confident* each match is,
so a reviewer can see exactly which rows were trusted and which need attention.

## Components

| Output | Built by | Purpose |
| --- | --- | --- |
| `dim_country` | `CountryHarmonizer.dim_country_frame` | Canonical ISO3/ISO2/M49/name/region reference. |
| `country_source_mapping` | `CountryHarmonizer.build_source_mapping` | One row per source name with its resolution and quality flag. |
| `country_mapping_quality_report` | SQL view / `CountryHarmonizer.quality_report` | Counts of names per quality flag per source. |

Reference data lives in
[`src/food_security_risk/geography/reference.py`](../src/food_security_risk/geography/reference.py).
It is curated and embedded so harmonization works offline, consistent with the
rest of the project. Swapping in an authoritative UN M49 / ISO 3166 table is a
documented extension point.

## Quality flags

| Flag | Meaning | Used in joins? |
| --- | --- | --- |
| `exact` | Source name matches a canonical name (or is a known ISO3 code). | Yes |
| `alias` | Resolved through a known spelling/alias to a canonical country. | Yes (only if the ISO3 exists in `dim_country`) |
| `ambiguous` | Name maps to more than one country; candidates are recorded. | No |
| `historical` | Dissolved or historical entity with no single modern ISO3. | No |
| `unresolved` | No canonical match or alias. | No |

Only `exact` and `alias` (with a canonical row) are treated as confident and
allowed into downstream joins. Everything else is preserved in the mapping
report rather than guessed.

## Resolution order

Ambiguous and historical names are checked **before** alias/exact matching, so a
problematic spelling can never slip through to a confident mapping.

1. Ambiguous (`Congo`, `Korea`, `Sudan (former)`) → flag with candidates.
2. Historical (`USSR`, `Czechoslovakia`, `Ethiopia PDR`) → flag as historical.
3. Exact canonical name, or a bare ISO3 code.
4. Known alias (`Ivory Coast` → `CIV`, `Swaziland` → `SWZ`).
5. Otherwise unresolved.

## Known unresolved / difficult cases

- **`Congo`** — genuinely ambiguous between the Democratic Republic of the Congo
  (`COD`) and the Republic of the Congo (`COG`). Sources must use a qualified
  name (`Congo, Dem. Rep.` / `Congo, Rep.`) to resolve.
- **`Korea`** — ambiguous between `KOR` and `PRK`; qualified names resolve.
- **`Sudan (former)`** — pre-2011 Sudan spans modern `SDN` and `SSD`; left
  ambiguous because a single mapping would misattribute history.
- **Dissolved states** (`USSR`, `Czechoslovakia`, `Yugoslav SFR`, etc.) — flagged
  `historical`; mapping them to a successor state is a modelling decision left to
  the analyst.
- **Aliases to ISO3 codes not yet in `dim_country`** (e.g. `Gambia, the` → `GMB`)
  — resolved to an ISO3 but **not** marked confident until the country is added
  to the canonical reference, preventing dangling joins.

## Workflow

```bash
# Build and load the canonical dimension
poetry run food-risk build-country-dim

# Audit how a source's country names resolve before trusting a join
poetry run food-risk map-source-countries \
    --input-csv data/raw/faostat_production.csv --column Area --source faostat
```

FAOSTAT ingestion (`food-risk ingest-faostat`) uses this layer automatically:
it harmonizes area names, writes a mapping report, and normalizes only the
confidently resolved areas.
