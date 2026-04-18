from pathlib import Path

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
