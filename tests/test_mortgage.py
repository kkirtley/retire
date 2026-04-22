from datetime import date

from retireplan.mortgage import build_mortgage_schedule


def test_mortgage_schedule_builds_annual_summaries_with_extra_principal(golden_scenario):
    scenario = golden_scenario

    schedule = build_mortgage_schedule(scenario)

    assert schedule.payment_monthly == 1898.68
    assert schedule.extra_payment_monthly == 1629.11
    assert schedule.payoff_date is not None
    assert schedule.payoff_date.year == 2032
    assert schedule.payoff_date.month == 11

    first_year = schedule.annual_summaries[2026]
    assert first_year.scheduled_payment == 11392.07
    assert first_year.extra_principal == 9774.69
    assert first_year.total_payment == round(
        first_year.scheduled_payment + first_year.extra_principal,
        2,
    )
    assert first_year.interest > 0.0
    assert first_year.principal > first_year.extra_principal


def test_mortgage_schedule_pays_off_by_target_age_year(golden_scenario):
    scenario = golden_scenario

    schedule = build_mortgage_schedule(scenario)

    payoff_year = scenario.mortgage.payoff_by_age.target_date.year
    assert schedule.payoff_date is not None
    assert schedule.payoff_date.year <= payoff_year
    assert schedule.annual_summaries[schedule.payoff_date.year].ending_balance == 0.0
    assert 2033 not in schedule.annual_summaries


def test_mortgage_schedule_uses_scheduled_payment_when_target_solver_not_needed(golden_scenario):
    scenario = golden_scenario
    scenario.mortgage.scheduled_payment_monthly = 5700.0
    scenario.mortgage.payoff_by_age.enabled = False

    schedule = build_mortgage_schedule(scenario)

    assert schedule.payment_monthly == 5700.0
    assert schedule.extra_payment_monthly == 0.0
    assert schedule.payoff_date is not None
    assert schedule.payoff_date.year == 2030
    assert schedule.payoff_date.month == 3


def test_mortgage_schedule_solves_monthly_payment_to_retirement_horizon_when_unset(golden_scenario):
    scenario = golden_scenario
    scenario.mortgage.scheduled_payment_monthly = None
    scenario.mortgage.payoff_by_age.enabled = False

    schedule = build_mortgage_schedule(scenario)

    assert schedule.payment_monthly == 1898.68
    assert schedule.extra_payment_monthly == 0.0
    assert schedule.payoff_date is not None
    assert schedule.payoff_date.year == 2041
    assert schedule.payoff_date.month == 6


def test_mortgage_schedule_prefers_specific_target_date_over_retirement_date(golden_scenario):
    scenario = golden_scenario
    scenario.mortgage.scheduled_payment_monthly = None
    scenario.mortgage.payoff_by_age.target_date = date(2031, 12, 1)

    schedule = build_mortgage_schedule(scenario)

    assert schedule.payment_monthly == 1898.68
    assert schedule.extra_payment_monthly == 2164.35
    assert schedule.payoff_date is not None
    assert schedule.payoff_date.year == 2031
    assert schedule.payoff_date.month == 11


def test_mortgage_schedule_can_derive_payoff_target_from_husband_age(golden_scenario):
    scenario = golden_scenario
    scenario.mortgage.scheduled_payment_monthly = None
    scenario.mortgage.payoff_by_age.target_date = None

    schedule = build_mortgage_schedule(scenario)

    assert schedule.payment_monthly == 1898.68
    assert schedule.extra_payment_monthly == 1830.22
    assert schedule.payoff_date is not None
    assert schedule.payoff_date.year == 2032
    assert schedule.payoff_date.month == 6
