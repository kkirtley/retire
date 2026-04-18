from pathlib import Path

import yaml

from retireplan.io import load_scenario


def test_load_baseline_scenario_and_collect_warnings():
    scenario_path = Path(__file__).resolve().parents[1] / "scenarios" / "baseline_v1.0.1.yaml"

    loaded = load_scenario(scenario_path)

    assert loaded.scenario.metadata.version == "1.1.0"
    assert loaded.scenario.household.husband.label == "Husband"
    assert any("filename version" in warning for warning in loaded.warnings)
    assert any("household.wife.current_age" in warning for warning in loaded.warnings)
    assert any(
        "modeled_death is enabled but death_year is null" in warning for warning in loaded.warnings
    )
    assert loaded.scenario.assumptions.rmd_uniform_lifetime_table[75] == 24.6


def test_loader_applies_shared_defaults_when_scenario_omits_policy_table(tmp_path: Path):
    scenario_path = Path(__file__).resolve().parents[1] / "scenarios" / "baseline_v1.0.1.yaml"
    payload = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    payload["assumptions"].pop("rmd_uniform_lifetime_table", None)
    payload.pop("federal_tax", None)
    payload.pop("medicare", None)
    payload.pop("taxes", None)

    temp_path = tmp_path / "shared-defaults.yaml"
    temp_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    loaded = load_scenario(temp_path)

    assert loaded.scenario.assumptions.rmd_uniform_lifetime_table[75] == 24.6
    assert loaded.scenario.federal_tax.standard_deduction.mfj == 30000.0
    assert loaded.scenario.medicare.part_b.base_premium_monthly == 174.7
    assert loaded.scenario.taxes.conversion_tax_payment.treatment == "annual_cash_outflow_same_year"
