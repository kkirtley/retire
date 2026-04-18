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
from retireplan.scenario import AccountOwner, AccountType, RetirementScenario
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
    surplus_allocations: dict[str, float]
    rollovers: dict[str, float]
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
    executed_rollovers: set[tuple[str, str]] = set()

    for period in build_timeline(scenario):
        year = period.year
        rollovers, rollover_alerts = _apply_retirement_account_rollovers(
            scenario,
            period.husband_retired,
            period.wife_retired,
            balances,
            executed_rollovers,
        )
        income = build_income(scenario, period)
        mortgage_summary = mortgage_schedule.annual_summaries.get(year)
        lookback_year = year - scenario.medicare.irmaa.lookback_years
        lookback_tax = tax_history.get(lookback_year)
        base_expenses = build_expenses(scenario, period, mortgage_summary)
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
        current_year_magi: float | None = None
        expenses = dict(base_expenses)
        tax_summary = calculate_tax_summary(
            scenario,
            period.filing_status,
            income,
            strategy_execution.cash_withdrawals,
            extra_ordinary_income=strategy_execution.conversion_ordinary_income,
        )
        withdrawals: dict[str, float] = dict(strategy_execution.cash_withdrawals)
        surplus_allocations: dict[str, float] = {}
        net_cash_flow = 0.0
        failed = 0
        medicare_summary = calculate_medicare_summary(
            scenario,
            period,
            lookback_magi=None if lookback_tax is None else lookback_tax.adjusted_gross_income,
            lookback_filing_status=filing_status_history.get(lookback_year),
            previous_irmaa_tier=previous_irmaa_tier,
        )
        for _ in range(4):
            expenses = dict(base_expenses)
            expenses.update(
                {
                    "medicare_part_b": medicare_summary.part_b_base + medicare_summary.irmaa_part_b,
                    "medicare_part_d": medicare_summary.part_d_base + medicare_summary.irmaa_part_d,
                }
            )
            if strategy_execution.taxable_giving > 0:
                expenses["charitable_giving"] = strategy_execution.taxable_giving

            total_income = sum(income.values())
            total_expenses = sum(expenses.values())
            (
                tax_summary,
                withdrawals,
                surplus_allocations,
                net_cash_flow,
                failed,
                balances,
            ) = _settle_period_cash_flow(
                scenario,
                period,
                period.filing_status,
                income,
                total_income,
                total_expenses,
                balances_after_contributions,
                strategy_execution.cash_withdrawals,
                sum(strategy_execution.cash_withdrawals.values()),
                strategy_execution.conversion_ordinary_income,
            )
            next_current_year_magi = tax_summary.adjusted_gross_income
            next_medicare_summary = calculate_medicare_summary(
                scenario,
                period,
                lookback_magi=None if lookback_tax is None else lookback_tax.adjusted_gross_income,
                lookback_filing_status=filing_status_history.get(lookback_year),
                current_year_magi=next_current_year_magi,
                current_year_filing_status=period.filing_status,
                previous_irmaa_tier=previous_irmaa_tier,
            )
            if (
                next_current_year_magi == current_year_magi
                and next_medicare_summary == medicare_summary
            ):
                medicare_summary = next_medicare_summary
                break
            current_year_magi = next_current_year_magi
            medicare_summary = next_medicare_summary
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
                surplus_allocations=_rounded_values(surplus_allocations),
                rollovers=_rounded_values(rollovers),
                withdrawals=_rounded_values(withdrawals),
                alerts=rollover_alerts + medicare_summary.alerts + strategy_execution.alerts,
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
        "Projection covers the Stage 9 desktop UI workflow; SQLite persistence remains a later YAML-to-database follow-on.",
    ]
    return warnings


def _settle_period_cash_flow(
    scenario: RetirementScenario,
    period,
    filing_status: str,
    income: dict[str, float],
    total_income: float,
    total_expenses: float,
    starting_balances: dict[str, float],
    base_withdrawals: dict[str, float],
    base_cash_inflows: float,
    extra_ordinary_income: float,
) -> tuple[TaxSummary, dict[str, float], dict[str, float], float, int, dict[str, float]]:
    withdrawals: dict[str, float] = dict(base_withdrawals)
    surplus_allocations: dict[str, float] = {}
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
            total_income + base_cash_inflows - total_expenses - tax_summary.total_tax
        )
        trial_balances = dict(starting_balances)
        (
            extra_withdrawals,
            next_surplus_allocations,
            settled_net_cash_flow,
            failed,
        ) = settle_net_cash_flow(
            scenario,
            period,
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
            surplus_allocations = next_surplus_allocations
            break
        withdrawals = next_withdrawals
        final_balances = trial_balances
        surplus_allocations = next_surplus_allocations

    return (
        tax_summary,
        withdrawals,
        surplus_allocations,
        settled_net_cash_flow,
        failed,
        final_balances,
    )


def _rounded_values(values: dict[str, float]) -> dict[str, float]:
    return {key: round(value, 2) for key, value in values.items()}


def _apply_retirement_account_rollovers(
    scenario: RetirementScenario,
    husband_retired: bool,
    wife_retired: bool,
    balances: dict[str, float],
    executed_rollovers: set[tuple[str, str]],
) -> tuple[dict[str, float], tuple[str, ...]]:
    config = scenario.strategy.account_rollovers
    if not config.enabled:
        return {}, ()

    rollovers: dict[str, float] = {}
    alerts: list[str] = []
    owner_retirement = (
        (AccountOwner.HUSBAND, husband_retired),
        (AccountOwner.WIFE, wife_retired),
    )
    for owner, retired in owner_retirement:
        if not retired:
            continue
        if config.roll_traditional_401k_to_ira:
            rollover_entry = _roll_account_balances(
                scenario,
                owner,
                AccountType.TRADITIONAL_401K,
                AccountType.TRADITIONAL_IRA,
                balances,
                executed_rollovers,
            )
            if rollover_entry is not None:
                rollover_name, rollover_amount, alert = rollover_entry
                rollovers[rollover_name] = rollover_amount
                alerts.append(alert)
        if config.roll_roth_401k_to_ira:
            rollover_entry = _roll_account_balances(
                scenario,
                owner,
                AccountType.ROTH_401K,
                AccountType.ROTH_IRA,
                balances,
                executed_rollovers,
            )
            if rollover_entry is not None:
                rollover_name, rollover_amount, alert = rollover_entry
                rollovers[rollover_name] = rollover_amount
                alerts.append(alert)
    return rollovers, tuple(alerts)


def _roll_account_balances(
    scenario: RetirementScenario,
    owner: AccountOwner,
    source_type: AccountType,
    target_type: AccountType,
    balances: dict[str, float],
    executed_rollovers: set[tuple[str, str]],
) -> tuple[str, float, str] | None:
    rollover_key = (owner.value, source_type.value)
    if rollover_key in executed_rollovers:
        return None

    source_accounts = [
        account
        for account in scenario.accounts
        if account.owner == owner and account.type == source_type
    ]
    if not source_accounts:
        return None

    target_account = next(
        (
            account
            for account in scenario.accounts
            if account.owner == owner and account.type == target_type
        ),
        None,
    )
    if target_account is None:
        return None

    rollover_total = round(sum(balances.get(account.name, 0.0) for account in source_accounts), 10)
    executed_rollovers.add(rollover_key)
    if rollover_total <= 0:
        return None

    balances[target_account.name] = round(balances[target_account.name] + rollover_total, 10)
    for account in source_accounts:
        balances[account.name] = 0.0

    rollover_name = f"{source_accounts[0].name} -> {target_account.name}"
    alert = f"Rolled {owner.value} {source_type.value.replace('_', ' ')} balances into {target_account.name} at retirement."
    return rollover_name, round(rollover_total, 2), alert


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
            if account.owner == AccountOwner.HUSBAND
            and account.type in {AccountType.TRADITIONAL_IRA, AccountType.TRADITIONAL_401K}
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
