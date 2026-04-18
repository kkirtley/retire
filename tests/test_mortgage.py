from datetime import date
from pathlib import Path

from retireplan.io import load_scenario
from retireplan.mortgage import build_mortgage_schedule


def _baseline_scenario():
    scenario_path = Path(__file__).resolve().parents[1] / "scenarios" / "baseline_v1.0.1.yaml"
    return load_scenario(scenario_path).scenario


def test_mortgage_schedule_builds_annual_summaries_with_extra_principal():
    scenario = _baseline_scenario()

    schedule = build_mortgage_schedule(scenario)

    assert schedule.payment_monthly == 3527.79
    assert schedule.extra_payment_monthly == 0.0
    assert schedule.payoff_date is not None
    assert schedule.payoff_date.year == 2032
    assert schedule.payoff_date.month == 11

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

    payoff_year = scenario.mortgage.payoff_by_age.target_date.year
    assert schedule.payoff_date is not None
    assert schedule.payoff_date.year <= payoff_year
    assert schedule.annual_summaries[schedule.payoff_date.year].ending_balance == 0.0
    assert 2033 not in schedule.annual_summaries


def test_mortgage_schedule_uses_scheduled_payment_when_target_solver_not_needed():
    scenario = _baseline_scenario()
    scenario.mortgage.scheduled_payment_monthly = 5700.0
    scenario.mortgage.payoff_by_age.enabled = False

    schedule = build_mortgage_schedule(scenario)

    assert schedule.payment_monthly == 5700.0
    assert schedule.extra_payment_monthly == 0.0
    assert schedule.payoff_date is not None
    assert schedule.payoff_date.year == 2030
    assert schedule.payoff_date.month == 3


def test_mortgage_schedule_solves_monthly_payment_to_retirement_horizon_when_unset():
    scenario = _baseline_scenario()
    scenario.mortgage.scheduled_payment_monthly = None
    scenario.mortgage.payoff_by_age.enabled = False

    schedule = build_mortgage_schedule(scenario)

    assert schedule.payment_monthly == 3490.7
    assert schedule.payoff_date is not None
    assert schedule.payoff_date.year == 2032
    assert schedule.payoff_date.month == 12


def test_mortgage_schedule_prefers_specific_target_date_over_retirement_date():
    scenario = _baseline_scenario()
    scenario.mortgage.scheduled_payment_monthly = None
    scenario.mortgage.payoff_by_age.target_date = date(2031, 12, 1)

    schedule = build_mortgage_schedule(scenario)

    assert schedule.payment_monthly == 4063.02
    assert schedule.payoff_date is not None
    assert schedule.payoff_date.year == 2031
    assert schedule.payoff_date.month == 11
