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
from retireplan.core.strategy import conversion_tax_impact, execute_strategy
from retireplan.core.timeline_builder import build_timeline
from retireplan.medicare import calculate_medicare_summary
from retireplan.mortgage import build_mortgage_schedule
from retireplan.scenario import AccountType, RetirementScenario
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
    strategy: dict[str, float]
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
    summary: dict[str, float | int | None]
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
        balances_after_contributions = dict(balances)
        strategy_execution = execute_strategy(
            scenario,
            period,
            income,
            period.filing_status,
            balances_after_contributions,
        )
        if strategy_execution.taxable_giving > 0:
            expenses["charitable_giving"] = strategy_execution.taxable_giving

        total_income = sum(income.values())
        total_expenses = sum(expenses.values())
        total_contributions = sum(contributions.values())
        tax_summary, withdrawals, net_cash_flow, failed, balances = _settle_period_cash_flow(
            scenario,
            period.filing_status,
            income,
            total_income,
            total_expenses,
            total_contributions,
            balances_after_contributions,
            strategy_execution.cash_withdrawals,
            sum(strategy_execution.cash_withdrawals.values()),
            strategy_execution.conversion_ordinary_income,
        )
        if failed and failure_year is None:
            failure_year = year

        tax_history[year] = tax_summary
        filing_status_history[year] = period.filing_status
        previous_irmaa_tier = medicare_summary.irmaa_tier

        apply_account_returns(scenario, period, balances)

        liquid_resources = liquid_resources_total(scenario, balances)
        success = failure_year is None
        strategy_values = strategy_execution.ledger_values(
            conversion_tax_impact(
                scenario,
                period.filing_status,
                income,
                withdrawals,
                tax_summary,
                strategy_execution,
            )
        )

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
                strategy=_rounded_values(strategy_values),
                expenses=_rounded_values(expenses),
                mortgage=_rounded_values(_mortgage_ledger_values(mortgage_summary)),
                contributions=_rounded_values(contributions),
                withdrawals=_rounded_values(withdrawals),
                alerts=medicare_summary.alerts + strategy_execution.alerts,
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
        summary=_build_summary(scenario, ledger, failure_year),
        ledger=ledger,
        success=failure_year is None,
        failure_year=failure_year,
    )


def _stage_limit_warnings(scenario: RetirementScenario) -> list[str]:
    warnings = [
        "Projection covers Stage 8 engine reporting outputs; Stage 9 desktop UI and scenario-editing workflows remain in progress.",
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
    base_withdrawals: dict[str, float],
    base_cash_inflows: float,
    extra_ordinary_income: float,
) -> tuple[TaxSummary, dict[str, float], float, int, dict[str, float]]:
    withdrawals: dict[str, float] = dict(base_withdrawals)
    tax_summary = calculate_tax_summary(
        scenario,
        filing_status,
        income,
        withdrawals,
        extra_ordinary_income=extra_ordinary_income,
    )
    final_balances = dict(starting_balances)
    settled_net_cash_flow = 0.0
    failed = 0

    for _ in range(6):
        tax_summary = calculate_tax_summary(
            scenario,
            filing_status,
            income,
            withdrawals,
            extra_ordinary_income=extra_ordinary_income,
        )
        cash_flow_before_settlement = (
            total_income
            + base_cash_inflows
            - total_expenses
            - total_contributions
            - tax_summary.total_tax
        )
        trial_balances = dict(starting_balances)
        extra_withdrawals, settled_net_cash_flow, failed = settle_net_cash_flow(
            scenario,
            trial_balances,
            cash_flow_before_settlement,
        )
        next_withdrawals = dict(base_withdrawals)
        for account_name, amount in extra_withdrawals.items():
            next_withdrawals[account_name] = round(
                next_withdrawals.get(account_name, 0.0) + amount, 2
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


def _build_summary(
    scenario: RetirementScenario,
    ledger: list[ProjectionRow],
    failure_year: int | None,
) -> dict[str, float | int | None]:
    terminal_net_worth = ledger[-1].liquid_resources_end if ledger else 0.0
    total_taxes_paid = sum(row.taxes.get("total", 0.0) for row in ledger)
    total_roth_converted = sum(row.strategy.get("roth_conversion_total", 0.0) for row in ledger)
    total_rmds = sum(row.strategy.get("rmd_total", 0.0) for row in ledger)
    total_qcd = sum(row.strategy.get("qcd_total", 0.0) for row in ledger)
    total_given = sum(row.strategy.get("charitable_giving_total", 0.0) for row in ledger)

    husband_age_70_row = next((row for row in ledger if row.husband_age == 70), None)
    traditional_balance_at_70 = 0.0
    if husband_age_70_row is not None:
        traditional_accounts = {
            account.name
            for account in scenario.accounts
            if account.type in {AccountType.TRADITIONAL_IRA, AccountType.TRADITIONAL_401K}
        }
        traditional_balance_at_70 = sum(
            balance
            for name, balance in husband_age_70_row.account_balances_end.items()
            if name in traditional_accounts
        )

    return {
        "terminal_net_worth": round(terminal_net_worth, 2),
        "total_taxes_paid": round(total_taxes_paid, 2),
        "total_roth_converted": round(total_roth_converted, 2),
        "projected_rmds_by_year_total": round(total_rmds, 2),
        "total_qcd": round(total_qcd, 2),
        "total_given": round(total_given, 2),
        "traditional_balance_at_husband_age_70": round(traditional_balance_at_70, 2),
        "failure_year_if_any": failure_year,
    }
