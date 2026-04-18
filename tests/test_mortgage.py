from pathlib import Path

from retireplan.io import load_scenario
from retireplan.mortgage import build_mortgage_schedule


def _baseline_scenario():
    scenario_path = Path(__file__).resolve().parents[1] / "scenarios" / "baseline_v1.0.1.yaml"
    return load_scenario(scenario_path).scenario


def test_mortgage_schedule_builds_annual_summaries_with_extra_principal():
    scenario = _baseline_scenario()

    schedule = build_mortgage_schedule(scenario)

    assert schedule.extra_payment_monthly == 0.0
    assert schedule.payoff_date is not None
    assert schedule.payoff_date.year == 2030
    assert schedule.payoff_date.month == 3

    first_year = schedule.annual_summaries[2026]
    assert first_year.total_payment == round(
        first_year.scheduled_payment + first_year.extra_principal,
        2,
    )
    assert first_year.interest > 0.0
    assert first_year.principal > first_year.extra_principal


def test_mortgage_schedule_pays_off_by_target_age_year():
    scenario = _baseline_scenario()

    schedule = build_mortgage_schedule(scenario)

    payoff_year = scenario.household.husband.birth_year + scenario.mortgage.payoff_by_age.target_age
    assert schedule.payoff_date is not None
    assert schedule.payoff_date.year <= payoff_year
    assert schedule.annual_summaries[schedule.payoff_date.year].ending_balance == 0.0
    assert 2033 not in schedule.annual_summaries


def test_mortgage_schedule_uses_scheduled_payment_when_target_solver_not_needed():
    scenario = _baseline_scenario()
    scenario.mortgage.payoff_by_age.enabled = False

    schedule = build_mortgage_schedule(scenario)

    assert schedule.extra_payment_monthly == 0.0
    assert schedule.payoff_date is not None
    assert schedule.payoff_date.year == 2030
    assert schedule.payoff_date.month == 3
