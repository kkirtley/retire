# Scenario Layout

This directory now has three distinct scenario roles:

- `baseline_canonical.yaml`: curated source of truth for deterministic annual planning
- `test_baseline_minimal.yaml`: stable standalone scenario for tests and fixture-style validation
- `scenario_*.yaml`: scenario deltas that inherit from `baseline_canonical.yaml`

## Rules

- `baseline_canonical.yaml` is a full scenario document.
- `test_baseline_minimal.yaml` is also a full scenario document.
- `scenario_*.yaml` files are not full standalone scenarios. They may define only:
  - `metadata`
  - `overrides`
- The loader automatically merges `overrides` from a `scenario_*.yaml` file onto the sibling `baseline_canonical.yaml`.
- Object values merge deeply.
- Lists replace the baseline list entirely.

## Why This Layout Exists

- The household baseline remains curated and deterministic.
- Tests do not depend on the live household baseline.
- Scenario variants stay small and avoid copy-paste drift.

## Current Files

- `baseline_canonical.yaml`: canonical deterministic baseline
- `test_baseline_minimal.yaml`: stable test fixture scenario
- `scenario_high_inflation.yaml`: inflation stress delta
- `scenario_historical_analysis.yaml`: historical-analysis opt-in delta
- `scenario_experimental_analytics.yaml`: experimental analytics opt-in delta