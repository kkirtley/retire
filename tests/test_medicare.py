from copy import deepcopy
from pathlib import Path

from retireplan.core import build_timeline, project_scenario
from retireplan.io import load_scenario
from retireplan.medicare import calculate_medicare_summary


def _baseline_scenario():
    scenario_path = Path(__file__).resolve().parents[1] / "scenarios" / "baseline_v1.0.1.yaml"
    return load_scenario(scenario_path).scenario


def test_medicare_base_premiums_begin_at_age_sixty_five():
    scenario = _baseline_scenario()
    period = next(item for item in build_timeline(scenario) if item.year == 2032)

    summary = calculate_medicare_summary(
        scenario,
        period,
        lookback_magi=None,
        lookback_filing_status=None,
    )

    assert summary.covered_people == 2
    assert summary.part_b_base == 4192.8
    assert summary.part_d_base == 832.8
    assert summary.irmaa_tier == 0


def test_irmaa_uses_two_year_lookback_with_single_thresholds():
    scenario = _baseline_scenario()
    scenario.household.husband.modeled_death.enabled = True
    scenario.household.husband.modeled_death.death_year = 2034
    period = next(item for item in build_timeline(scenario) if item.year == 2037)

    summary = calculate_medicare_summary(
        scenario,
        period,
        lookback_magi=140000.0,
        lookback_filing_status="single",
        previous_irmaa_tier=0,
    )

    assert summary.covered_people == 1
    assert summary.irmaa_tier == 2
    assert summary.irmaa_part_b == 2096.4
    assert summary.irmaa_part_d == 378.0
    assert summary.alerts


def test_projection_adds_medicare_costs_and_irmaa_alerts():
    scenario = deepcopy(_baseline_scenario())

    result = project_scenario(scenario)
    rows = {row.year: row for row in result.ledger}

    pre_medicare = rows[2031]
    medicare_start = rows[2032]
    irmaa_reset_year = rows[2035]

    assert pre_medicare.medicare["total"] == 0.0
    assert medicare_start.medicare["covered_people"] == 2.0
    assert medicare_start.expenses["medicare_part_b"] > 0.0
    assert medicare_start.expenses["medicare_part_d"] > 0.0
    assert "IRMAA tier changed from 0 to 2 based on 2030 MAGI." in medicare_start.alerts
    assert irmaa_reset_year.medicare["irmaa_tier"] == 0.0
    assert "IRMAA tier changed from 2 to 0 based on 2033 MAGI." in irmaa_reset_year.alerts
