"""Stage 4 mortgage amortization and payoff solver."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from retireplan.scenario import RetirementScenario


@dataclass(frozen=True)
class AnnualMortgageSummary:
    year: int
    scheduled_payment: float
    extra_principal: float
    total_payment: float
    interest: float
    principal: float
    ending_balance: float

    def ledger_values(self) -> dict[str, float]:
        return {
            "scheduled_payment": round(self.scheduled_payment, 2),
            "extra_principal": round(self.extra_principal, 2),
            "total_payment": round(self.total_payment, 2),
            "interest": round(self.interest, 2),
            "principal": round(self.principal, 2),
            "remaining_balance": round(self.ending_balance, 2),
        }


@dataclass(frozen=True)
class MortgageSchedule:
    extra_payment_monthly: float
    payoff_date: date | None
    annual_summaries: dict[int, AnnualMortgageSummary]


def build_mortgage_schedule(scenario: RetirementScenario) -> MortgageSchedule:
    if not scenario.mortgage.enabled:
        return MortgageSchedule(extra_payment_monthly=0.0, payoff_date=None, annual_summaries={})

    balance = float(scenario.mortgage.starting_balance)
    scheduled_payment = float(scenario.mortgage.scheduled_payment_monthly)
    monthly_rate = float(scenario.mortgage.interest_rate) / 12.0
    remaining_term_months = scenario.mortgage.remaining_term_years * 12
    target_term_months = _target_term_months(scenario, remaining_term_months)
    extra_payment_monthly = _solve_extra_payment_monthly(
        balance=balance,
        scheduled_payment=scheduled_payment,
        monthly_rate=monthly_rate,
        target_term_months=target_term_months,
    )

    annual_totals: dict[int, dict[str, float]] = {}
    payment_month = scenario.simulation.start_date.replace(day=1)
    payoff_date: date | None = None

    for month_index in range(remaining_term_months):
        if balance <= 0:
            break

        interest = round(balance * monthly_rate, 10)
        total_payment_target = scheduled_payment
        if month_index < target_term_months:
            total_payment_target += extra_payment_monthly
        total_payment = min(total_payment_target, balance + interest)
        principal = total_payment - interest
        ending_balance = max(balance - principal, 0.0)

        year_totals = annual_totals.setdefault(
            payment_month.year,
            {
                "scheduled_payment": 0.0,
                "extra_principal": 0.0,
                "total_payment": 0.0,
                "interest": 0.0,
                "principal": 0.0,
                "ending_balance": 0.0,
            },
        )
        scheduled_component = min(scheduled_payment, total_payment)
        extra_component = max(total_payment - scheduled_component, 0.0)
        year_totals["scheduled_payment"] += scheduled_component
        year_totals["extra_principal"] += extra_component
        year_totals["total_payment"] += total_payment
        year_totals["interest"] += interest
        year_totals["principal"] += principal
        year_totals["ending_balance"] = ending_balance

        balance = ending_balance
        if balance <= 0 and payoff_date is None:
            payoff_date = payment_month
        payment_month = _next_month(payment_month)

    annual_summaries = {
        year: AnnualMortgageSummary(
            year=year,
            scheduled_payment=round(values["scheduled_payment"], 2),
            extra_principal=round(values["extra_principal"], 2),
            total_payment=round(values["total_payment"], 2),
            interest=round(values["interest"], 2),
            principal=round(values["principal"], 2),
            ending_balance=round(values["ending_balance"], 2),
        )
        for year, values in annual_totals.items()
    }

    return MortgageSchedule(
        extra_payment_monthly=round(extra_payment_monthly, 2),
        payoff_date=payoff_date,
        annual_summaries=annual_summaries,
    )


def _target_term_months(scenario: RetirementScenario, remaining_term_months: int) -> int:
    if not scenario.mortgage.payoff_by_age.enabled:
        return remaining_term_months

    target_date = date(
        scenario.household.husband.birth_year + scenario.mortgage.payoff_by_age.target_age,
        scenario.household.husband.birth_month,
        1,
    )
    start_date = scenario.simulation.start_date.replace(day=1)
    months_until_target = (target_date.year - start_date.year) * 12 + (
        target_date.month - start_date.month
    )
    return max(1, min(remaining_term_months, months_until_target))


def _solve_extra_payment_monthly(
    balance: float,
    scheduled_payment: float,
    monthly_rate: float,
    target_term_months: int,
) -> float:
    if (
        _ending_balance_after_term(balance, scheduled_payment, monthly_rate, target_term_months)
        <= 0
    ):
        return 0.0

    lower_bound = 0.0
    upper_bound = max(balance / target_term_months, 1.0)
    while (
        _ending_balance_after_term(
            balance,
            scheduled_payment + upper_bound,
            monthly_rate,
            target_term_months,
        )
        > 0
    ):
        upper_bound *= 2.0

    for _ in range(80):
        midpoint = (lower_bound + upper_bound) / 2.0
        ending_balance = _ending_balance_after_term(
            balance,
            scheduled_payment + midpoint,
            monthly_rate,
            target_term_months,
        )
        if ending_balance > 0:
            lower_bound = midpoint
        else:
            upper_bound = midpoint

    return upper_bound


def _ending_balance_after_term(
    balance: float,
    total_payment: float,
    monthly_rate: float,
    term_months: int,
) -> float:
    remaining_balance = balance
    for _ in range(term_months):
        if remaining_balance <= 0:
            return 0.0
        interest = remaining_balance * monthly_rate
        principal = min(total_payment - interest, remaining_balance)
        if principal <= 0:
            return remaining_balance
        remaining_balance -= principal
    return remaining_balance


def _next_month(month_start: date) -> date:
    if month_start.month == 12:
        return date(month_start.year + 1, 1, 1)
    return date(month_start.year, month_start.month + 1, 1)
