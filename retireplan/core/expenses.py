"""Stage 2 expense calculations for annual projection periods."""

from __future__ import annotations

from datetime import date

from retireplan.core.timeline_builder import TimelinePeriod, year_fraction_for_dates
from retireplan.mortgage import AnnualMortgageSummary
from retireplan.scenario import RetirementScenario


def build_expenses(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    mortgage_summary: AnnualMortgageSummary | None = None,
) -> dict[str, float]:
    expenses = {
        "base_living": inflated_amount_for_period(
            scenario.expenses.base_living.amount_annual,
            scenario.expenses.base_living.inflation_rate,
            scenario.simulation.start_date.year,
            period,
        ),
        "travel": inflated_amount_for_period(
            scenario.expenses.travel.amount_annual,
            scenario.expenses.travel.inflation_rate,
            scenario.simulation.start_date.year,
            period,
        ),
        "property_tax": dated_inflated_amount_for_period(
            scenario.expenses.housing.property_tax.amount_annual,
            scenario.expenses.housing.property_tax.inflation_rate,
            scenario.expenses.housing.property_tax.start_date,
            period,
            scenario,
        ),
        "homeowners_insurance": dated_inflated_amount_for_period(
            scenario.expenses.housing.homeowners_insurance.amount_annual,
            scenario.expenses.housing.homeowners_insurance.inflation_rate,
            scenario.expenses.housing.homeowners_insurance.start_date,
            period,
            scenario,
        ),
        "mortgage_payment": mortgage_payment_for_period(scenario, period, mortgage_summary),
    }

    if period.survivor_phase and scenario.household.expense_stepdown_after_husband_death.enabled:
        ratio = scenario.household.expense_stepdown_after_husband_death.surviving_expense_ratio
        return {name: amount * ratio for name, amount in expenses.items()}

    return expenses


def inflated_amount_for_period(
    amount: float,
    inflation_rate: float,
    start_year: int,
    period: TimelinePeriod,
) -> float:
    if period.year < start_year:
        return 0.0
    years_since_start = period.year - start_year
    return round(amount * ((1 + inflation_rate) ** years_since_start) * period.fraction_of_year, 2)


def dated_inflated_amount_for_period(
    amount: float,
    inflation_rate: float,
    start_date: date,
    period: TimelinePeriod,
    scenario: RetirementScenario,
) -> float:
    if period.year < start_date.year:
        return 0.0
    years_since_start = period.year - start_date.year
    return round(
        amount
        * ((1 + inflation_rate) ** years_since_start)
        * year_fraction_for_dates(period, start_date, None, scenario),
        2,
    )


def mortgage_payment_for_period(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    mortgage_summary: AnnualMortgageSummary | None = None,
) -> float:
    if not scenario.mortgage.enabled:
        return 0.0
    if mortgage_summary is not None:
        return round(mortgage_summary.total_payment, 2)
    return 0.0
