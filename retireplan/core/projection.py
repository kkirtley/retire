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
from retireplan.scenario import RetirementScenario


@dataclass(frozen=True)
class ProjectionRow:
    year: int
    husband_age: int
    wife_age: int
    husband_alive: bool
    wife_alive: bool
    filing_status: str
    income: dict[str, float]
    expenses: dict[str, float]
    contributions: dict[str, float]
    withdrawals: dict[str, float]
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
    """Run a Stage 2 annual projection using the richer scenario file as input."""

    balances = {account.name: float(account.starting_balance) for account in scenario.accounts}
    ledger: list[ProjectionRow] = []
    failure_year: int | None = None
    warnings = list(scenario_warnings or [])
    warnings.extend(_stage_limit_warnings(scenario))

    for period in build_timeline(scenario):
        year = period.year
        income = build_income(scenario, period)
        expenses = build_expenses(scenario, period)
        earned_income = {
            "husband": income["earned_income_husband"],
            "wife": income["earned_income_wife"],
        }
        contributions = apply_contributions(scenario, period, balances, earned_income)

        total_income = sum(income.values())
        total_expenses = sum(expenses.values())
        total_contributions = sum(contributions.values())
        net_cash_flow = total_income - total_expenses - total_contributions
        withdrawals, net_cash_flow, failed = settle_net_cash_flow(scenario, balances, net_cash_flow)
        if failed and failure_year is None:
            failure_year = year

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
                expenses=_rounded_values(expenses),
                contributions=_rounded_values(contributions),
                withdrawals=_rounded_values(withdrawals),
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
        "Projection applies the richer scenario schema, but the engine is still Stage 2: taxes, Medicare, IRMAA, RMDs, QCDs, and Roth conversion logic are validated but not applied in cashflow results.",
    ]
    if scenario.mortgage.enabled:
        warnings.append(
            "Mortgage is currently modeled as scheduled annual payments only; amortization, extra principal solving, and payoff-by-age enforcement are not applied yet."
        )
    return warnings


def _rounded_values(values: dict[str, float]) -> dict[str, float]:
    return {key: round(value, 2) for key, value in values.items()}
