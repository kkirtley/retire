"""Stage 2 account contributions, withdrawals, and return application."""

from __future__ import annotations

from datetime import date
from typing import Callable

from retireplan.core.timeline_builder import TimelinePeriod, year_fraction_for_dates
from retireplan.scenario import (
    Account,
    AccountType,
    ContributionType,
    RetirementScenario,
    WithdrawalOrderType,
)


def apply_contributions(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    balances: dict[str, float],
    earned_income: dict[str, float],
) -> dict[str, float]:
    contributions: dict[str, float] = {}
    if not scenario.contributions.enabled:
        return contributions

    for schedule in scenario.contributions.schedules:
        if (
            not schedule.enabled
            or period.year < schedule.start_date.year
            or period.year > schedule.end_date.year
        ):
            continue

        amount = 0.0
        if schedule.type == ContributionType.PERCENT_OF_SALARY:
            owner_key = schedule.owner.lower()
            amount = earned_income.get(owner_key, 0.0) * float(schedule.percent or 0.0)
        elif schedule.type == ContributionType.FIXED_MONTHLY:
            active_fraction = year_fraction_for_dates(
                period,
                schedule.start_date,
                schedule.end_date,
                scenario,
            )
            amount = float(schedule.amount_monthly or 0.0) * 12 * active_fraction
        else:
            active_fraction = year_fraction_for_dates(
                period,
                schedule.start_date,
                schedule.end_date,
                scenario,
            )
            amount = float(schedule.amount_annual or 0.0) * active_fraction

        balances[schedule.destination_account] += amount
        contributions[schedule.destination_account] = round(
            contributions.get(schedule.destination_account, 0.0) + amount,
            2,
        )

    return contributions


def settle_net_cash_flow(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    balances: dict[str, float],
    net_cash_flow: float,
) -> tuple[dict[str, float], dict[str, float], float, int]:
    withdrawals: dict[str, float] = {}
    surplus_allocations: dict[str, float] = {}
    unmet_need = 0.0
    if net_cash_flow >= 0:
        surplus_destination = _surplus_destination_account(scenario, period)
        if surplus_destination is not None:
            balances[surplus_destination] += net_cash_flow
            surplus_allocations[surplus_destination] = round(net_cash_flow, 2)
        return withdrawals, surplus_allocations, net_cash_flow, 0

    withdrawals, unmet_need = withdraw_to_cover_deficit(scenario, balances, -net_cash_flow)
    return (
        withdrawals,
        surplus_allocations,
        net_cash_flow + sum(withdrawals.values()),
        int(unmet_need > 0),
    )


def _surplus_destination_account(
    scenario: RetirementScenario,
    period: TimelinePeriod,
) -> str | None:
    configured_destination = scenario.contributions.surplus_allocation.destination_account
    destination_account = next(
        (account for account in scenario.accounts if account.name == configured_destination),
        None,
    )
    if destination_account is None:
        return configured_destination
    if _account_accepts_surplus(destination_account, period):
        return configured_destination
    fallback_account = next(
        (account for account in scenario.accounts if account.name == "Household Operating Cash"),
        None,
    )
    if fallback_account is None:
        return None
    if fallback_account.contributions_enabled is False:
        return None
    return fallback_account.name


def _account_accepts_surplus(account: Account, period: TimelinePeriod) -> bool:
    if account.contributions_enabled is False:
        return False
    if account.purpose != "conversion_tax_funding":
        return True
    if not period.husband_retired:
        return False
    if account.purpose_transition is None:
        return True
    return period.husband_age >= account.purpose_transition.transition_age_husband


def withdraw_to_cover_deficit(
    scenario: RetirementScenario,
    balances: dict[str, float],
    required_amount: float,
) -> tuple[dict[str, float], float]:
    withdrawals: dict[str, float] = {}
    remaining = required_amount
    restricted_accounts = set(scenario.strategy.withdrawals.restrictions.never_use_accounts)

    for order_item in scenario.strategy.withdrawals.order:
        for account in matching_accounts(order_item, scenario.accounts):
            if account.name in restricted_accounts or account.withdrawals_enabled is False:
                continue
            available = balances[account.name]
            if available <= 0:
                continue
            amount = min(available, remaining)
            balances[account.name] -= amount
            withdrawals[account.name] = round(withdrawals.get(account.name, 0.0) + amount, 2)
            remaining = round(remaining - amount, 10)
            if remaining <= 0:
                return withdrawals, 0.0

    return withdrawals, max(remaining, 0.0)


def matching_accounts(order_item: WithdrawalOrderType, accounts: list[Account]) -> list[Account]:
    selectors: dict[WithdrawalOrderType, Callable[[Account], bool]] = {
        WithdrawalOrderType.HOUSEHOLD_OPERATING_CASH: lambda account: account.name
        == "Household Operating Cash",
        WithdrawalOrderType.TAXABLE_BRIDGE_ACCOUNT: lambda account: account.name
        == "Taxable Bridge Account",
        WithdrawalOrderType.TRADITIONAL_IRA: lambda account: account.type
        == AccountType.TRADITIONAL_IRA,
        WithdrawalOrderType.TRADITIONAL_401K: lambda account: account.type
        == AccountType.TRADITIONAL_401K,
        WithdrawalOrderType.ROTH_IRA: lambda account: account.type == AccountType.ROTH_IRA,
        WithdrawalOrderType.ROTH_401K: lambda account: account.type == AccountType.ROTH_401K,
    }
    selector = selectors[order_item]
    return [account for account in accounts if selector(account)]


def apply_account_returns(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    balances: dict[str, float],
) -> None:
    for account in scenario.accounts:
        balances[account.name] *= (
            1.0 + annual_return_for_year(account, period.year, scenario) * period.fraction_of_year
        )


def annual_return_for_year(account: Account, year: int, scenario: RetirementScenario) -> float:
    probe_date = date(year, 6, 30)
    if account.return_schedule:
        for entry in account.return_schedule:
            if entry.start_date <= probe_date and (
                entry.end_date is None or probe_date <= entry.end_date
            ):
                return float(entry.annual_rate)
    if account.return_rate is not None:
        return float(account.return_rate)
    return float(scenario.assumptions.investment_return_default)


def liquid_resources_total(scenario: RetirementScenario, balances: dict[str, float]) -> float:
    return sum(
        balances[account.name]
        for account in scenario.accounts
        if account.name not in scenario.strategy.withdrawals.restrictions.never_use_accounts
        and account.withdrawals_enabled is not False
    )
