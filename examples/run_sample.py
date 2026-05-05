"""Run the offline sample workflow."""

from __future__ import annotations

from pathlib import Path

from food_security_risk.pipeline import run_sample_pipeline


if __name__ == "__main__":
    outputs = run_sample_pipeline(Path("."), start_year=2010, end_year=2024, seed=42)
    for name, path in outputs.items():
        print(f"{name}: {path}")
