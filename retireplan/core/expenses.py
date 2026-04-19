"""Stage 2 expense calculations for annual projection periods."""

from __future__ import annotations

from datetime import date

from retireplan.core.market_history import compound_growth_factor
from retireplan.core.timeline_builder import TimelinePeriod, year_fraction_for_dates
from retireplan.mortgage import AnnualMortgageSummary
from retireplan.scenario import ExpenseAdjustment, InflatingAnnualExpense, RetirementScenario


def build_expenses(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    mortgage_summary: AnnualMortgageSummary | None = None,
) -> dict[str, float]:
    expenses = {
        "base_living": annual_expense_amount_for_period(
            scenario.expenses.base_living,
            scenario.simulation.start_date.year,
            period,
            scenario,
        ),
        "travel": annual_expense_amount_for_period(
            scenario.expenses.travel,
            scenario.simulation.start_date.year,
            period,
            scenario,
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


def annual_expense_amount_for_period(
    expense: InflatingAnnualExpense,
    start_year: int,
    period: TimelinePeriod,
    scenario: RetirementScenario,
) -> float:
    adjustment = _active_expense_adjustment(expense.adjustments, period.year)
    amount = expense.amount_annual if adjustment is None else adjustment.amount_annual
    inflation_rate = (
        expense.inflation_rate
        if adjustment is None
        else float(
            adjustment.inflation_rate
            if adjustment.inflation_rate is not None
            else expense.inflation_rate
        )
    )
    inflation_start_year = start_year if adjustment is None else adjustment.start_year
    return inflated_amount_for_period(
        amount, inflation_rate, inflation_start_year, period, scenario
    )


def inflated_amount_for_period(
    amount: float,
    inflation_rate: float,
    start_year: int,
    period: TimelinePeriod,
    scenario: RetirementScenario,
) -> float:
    if period.year < start_year:
        return 0.0
    growth_factor = compound_growth_factor(
        scenario,
        start_year,
        period.year,
        inflation_rate,
        use_historical_inflation=scenario.historical_analysis.use_historical_inflation_for_expenses,
    )
    return round(amount * growth_factor * period.fraction_of_year, 2)


def _active_expense_adjustment(
    adjustments: list[ExpenseAdjustment],
    year: int,
) -> ExpenseAdjustment | None:
    for adjustment in adjustments:
        if adjustment.start_year <= year <= adjustment.end_year:
            return adjustment
    return None


def dated_inflated_amount_for_period(
    amount: float,
    inflation_rate: float,
    start_date: date,
    period: TimelinePeriod,
    scenario: RetirementScenario,
) -> float:
    if period.year < start_date.year:
        return 0.0
    growth_factor = compound_growth_factor(
        scenario,
        start_date.year,
        period.year,
        inflation_rate,
        use_historical_inflation=scenario.historical_analysis.use_historical_inflation_for_expenses,
    )
    return round(
        amount * growth_factor * year_fraction_for_dates(period, start_date, None, scenario),
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
