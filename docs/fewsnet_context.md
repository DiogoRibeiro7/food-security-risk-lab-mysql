# FEWS NET / IPC context layer (v0.5)

This layer adds a **contextual humanitarian reference**: FEWS NET-style IPC
classifications attached to the risk output for comparison. It is built by
[`food_security_risk.context.fewsnet`](../src/food_security_risk/context/fewsnet.py)
and stored in the `fewsnet_context` table.

## The important rule

> **Do not train models that blindly reproduce FEWS NET / IPC classifications**
> without understanding their methodology, spatial granularity, and temporal
> scope.

The risk score in this project is a *transparent function* of rainfall, crop,
and affordability indicators. It is intentionally **not** fitted to reproduce
IPC phases. This layer exists so an analyst can put the two side by side, not so
one becomes a label for the other. To keep that boundary obvious:

- Context is stored and joined separately from scoring; the scorer never reads it.
- Join helpers attach context under a `context_` prefix, so any downstream table
  makes it visually clear those columns are reference context, not model I/O.

## IPC phases

| Phase | Label |
| --- | --- |
| 1 | Minimal |
| 2 | Stressed |
| 3 | Crisis |
| 4 | Emergency |
| 5 | Famine |

A `classification_type` distinguishes a `current` assessment from a `projected`
one. Narratives are stored as optional free text.

## Why these phases are not ground truth here

- **Methodology.** IPC classification is an expert consensus process combining
  evidence on food consumption, livelihoods, nutrition, and mortality. It is not
  a direct function of the few indicators modelled here.
- **Spatial granularity.** IPC areas are often sub-national livelihood zones,
  not whole countries. Aggregating them to a country to join against a
  country-level score loses information; the join keeps the **worst** phase and
  a record count so that aggregation is visible, not hidden.
- **Temporal scope.** Assessments are periodic (and projections are forward
  looking). A country-year or country-month join is an approximation of when a
  classification applied.

Treat agreement between the risk score and the context as *corroboration*, and
disagreement as a prompt to investigate — never as model error to be trained
away.

## Schema

`fewsnet_context`: `country_code`, `country_name`, `area_name`, `year`, `month`,
`ipc_phase`, `ipc_phase_label`, `classification_type`, `narrative`, `source`,
`as_of_date`.

The join (`join_context_to_risk`) aggregates context to the risk grain and adds:
`context_ipc_phase` (worst observed), `context_ipc_phase_label`,
`context_n_records`, `context_has_projection`, `context_narrative`.

## Workflow

```bash
# Reproducible synthetic context aligned with the sample drought
poetry run food-risk sample-context --output data/raw/fewsnet_context.csv

# Or normalize a real FEWS NET / IPC-style export
poetry run food-risk ingest-context --input-csv path/to/ipc_export.csv

# Compare context against a risk output (year or month grain) — context only
poetry run food-risk join-context --risk-csv reports/sample_run/food_security_scores.csv \
    --level year --context-source csv --output reports/sample_run/risk_with_context.csv
```
