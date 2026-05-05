# Methodology

## Risk interpretation

The project produces early-warning indicators. A high score means several observable indicators are deteriorating relative to simple baselines. It does not prove food insecurity, famine, or humanitarian emergency.

## Component scores

### Rainfall deficit score

Higher when rainfall is below the historical or configured baseline.

### Food affordability pressure score

Higher when the affordability ratio is above its baseline. This represents pressure, not direct household food insecurity.

### Crop-production decline score

Higher when crop production is below its baseline.

### Volatility score

Higher when several components have large deviations at the same time.

### Recent deterioration score

Higher when multiple severe flags appear in the same country-year observation.

## Final score

```text
food_security_risk_score =
    0.30 * rainfall_deficit_score
  + 0.25 * food_affordability_pressure_score
  + 0.20 * crop_production_decline_score
  + 0.15 * volatility_score
  + 0.10 * recent_deterioration_score
```

The weights are intentionally transparent and should be treated as configurable assumptions.
