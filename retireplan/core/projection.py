"""Deterministic annual projection engine for the currently implemented Stage 2 scope."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from retireplan.core.account_flow import (
    apply_account_returns,
    apply_contributions,
    liquid_resources_total,
    settle_net_cash_flow,
)
from retireplan.core.expenses import build_expenses
from retireplan.core.income import build_income
from retireplan.core.timeline_builder import build_timeline
from retireplan.medicare import calculate_medicare_summary
from retireplan.mortgage import build_mortgage_schedule
from retireplan.scenario import RetirementScenario
from retireplan.tax import TaxSummary, calculate_tax_summary


@dataclass(frozen=True)
class ProjectionRow:
    year: int
    husband_age: int
    wife_age: int
    husband_alive: bool
    wife_alive: bool
    filing_status: str
    income: dict[str, float]
    taxes: dict[str, float]
    medicare: dict[str, float]
    expenses: dict[str, float]
    mortgage: dict[str, float]
    contributions: dict[str, float]
    withdrawals: dict[str, float]
    alerts: tuple[str, ...]
    net_cash_flow: float
    account_balances_end: dict[str, float]
    liquid_resources_end: float
    success: bool


@dataclass(frozen=True)
class ProjectionResult:
    scenario_name: str
    version: str
    warnings: list[str]
    ledger: list[ProjectionRow]
    success: bool
    failure_year: int | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def project_scenario(
    scenario: RetirementScenario,
    scenario_warnings: Iterable[str] | None = None,
) -> ProjectionResult:
    """Run a Stage 3 annual projection using the richer scenario file as input."""

    balances = {account.name: float(account.starting_balance) for account in scenario.accounts}
    mortgage_schedule = build_mortgage_schedule(scenario)
    ledger: list[ProjectionRow] = []
    failure_year: int | None = None
    warnings = list(scenario_warnings or [])
    warnings.extend(_stage_limit_warnings(scenario))
    tax_history: dict[int, TaxSummary] = {}
    filing_status_history: dict[int, str] = {}
    previous_irmaa_tier: int | None = None

    for period in build_timeline(scenario):
        year = period.year
        income = build_income(scenario, period)
        mortgage_summary = mortgage_schedule.annual_summaries.get(year)
        lookback_year = year - scenario.medicare.irmaa.lookback_years
        lookback_tax = tax_history.get(lookback_year)
        medicare_summary = calculate_medicare_summary(
            scenario,
            period,
            lookback_magi=None if lookback_tax is None else lookback_tax.adjusted_gross_income,
            lookback_filing_status=filing_status_history.get(lookback_year),
            previous_irmaa_tier=previous_irmaa_tier,
        )
        expenses = build_expenses(scenario, period, mortgage_summary)
        expenses.update(
            {
                "medicare_part_b": medicare_summary.part_b_base + medicare_summary.irmaa_part_b,
                "medicare_part_d": medicare_summary.part_d_base + medicare_summary.irmaa_part_d,
            }
        )
        earned_income = {
            "husband": income["earned_income_husband"],
            "wife": income["earned_income_wife"],
        }
        contributions = apply_contributions(scenario, period, balances, earned_income)

        total_income = sum(income.values())
        total_expenses = sum(expenses.values())
        total_contributions = sum(contributions.values())
        balances_after_contributions = dict(balances)
        tax_summary, withdrawals, net_cash_flow, failed, balances = _settle_period_cash_flow(
            scenario,
            period.filing_status,
            income,
            total_income,
            total_expenses,
            total_contributions,
            balances_after_contributions,
        )
        if failed and failure_year is None:
            failure_year = year

        tax_history[year] = tax_summary
        filing_status_history[year] = period.filing_status
        previous_irmaa_tier = medicare_summary.irmaa_tier

        apply_account_returns(scenario, period, balances)

        liquid_resources = liquid_resources_total(scenario, balances)
        success = failure_year is None

        ledger.append(
            ProjectionRow(
                year=year,
                husband_age=period.husband_age,
                wife_age=period.wife_age,
                husband_alive=period.husband_alive,
                wife_alive=period.wife_alive,
                filing_status=period.filing_status,
                income=_rounded_values(income),
                taxes=_rounded_values(tax_summary.ledger_values()),
                medicare=_rounded_values(medicare_summary.ledger_values()),
                expenses=_rounded_values(expenses),
                mortgage=_rounded_values(_mortgage_ledger_values(mortgage_summary)),
                contributions=_rounded_values(contributions),
                withdrawals=_rounded_values(withdrawals),
                alerts=medicare_summary.alerts,
                net_cash_flow=round(net_cash_flow, 2),
                account_balances_end=_rounded_values(balances),
                liquid_resources_end=round(liquid_resources, 2),
                success=success,
            )
        )

    return ProjectionResult(
        scenario_name=scenario.metadata.scenario_name,
        version=scenario.metadata.version,
        warnings=warnings,
        ledger=ledger,
        success=failure_year is None,
        failure_year=failure_year,
    )


def _stage_limit_warnings(scenario: RetirementScenario) -> list[str]:
    warnings = [
        "Projection applies Stage 6 Medicare, survivor, mortgage, and tax modeling, but RMDs, QCDs, and Roth conversion logic are still validated but not yet applied in cashflow results.",
    ]
    return warnings


def _settle_period_cash_flow(
    scenario: RetirementScenario,
    filing_status: str,
    income: dict[str, float],
    total_income: float,
    total_expenses: float,
    total_contributions: float,
    starting_balances: dict[str, float],
) -> tuple[TaxSummary, dict[str, float], float, int, dict[str, float]]:
    withdrawals: dict[str, float] = {}
    tax_summary = calculate_tax_summary(scenario, filing_status, income, withdrawals)
    final_balances = dict(starting_balances)
    settled_net_cash_flow = 0.0
    failed = 0

    for _ in range(6):
        tax_summary = calculate_tax_summary(scenario, filing_status, income, withdrawals)
        cash_flow_before_settlement = (
            total_income - total_expenses - total_contributions - tax_summary.total_tax
        )
        trial_balances = dict(starting_balances)
        next_withdrawals, settled_net_cash_flow, failed = settle_net_cash_flow(
            scenario,
            trial_balances,
            cash_flow_before_settlement,
        )
        if next_withdrawals == withdrawals:
            final_balances = trial_balances
            break
        withdrawals = next_withdrawals
        final_balances = trial_balances

    return tax_summary, withdrawals, settled_net_cash_flow, failed, final_balances


def _rounded_values(values: dict[str, float]) -> dict[str, float]:
    return {key: round(value, 2) for key, value in values.items()}


def _mortgage_ledger_values(mortgage_summary) -> dict[str, float]:
    if mortgage_summary is None:
        return {
            "scheduled_payment": 0.0,
            "extra_principal": 0.0,
            "total_payment": 0.0,
            "interest": 0.0,
            "principal": 0.0,
            "remaining_balance": 0.0,
        }
    return mortgage_summary.ledger_values()
