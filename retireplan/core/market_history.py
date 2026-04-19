"""Historical market data helpers for account-type return and inflation modeling."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files

from retireplan.core.timeline_builder import TimelinePeriod, build_timeline
from retireplan.scenario import Account, AccountOwner, AccountType, RetirementScenario


@dataclass(frozen=True)
class HistoricalMarketRecord:
    year: int
    stocks: float
    bonds: float
    cash: float
    inflation: float


def historical_projection_enabled(scenario: RetirementScenario) -> bool:
    return bool(
        scenario.historical_analysis.enabled and scenario.historical_analysis.selected_start_year
    )


@lru_cache(maxsize=4)
def load_historical_market_dataset(dataset_name: str) -> dict[int, HistoricalMarketRecord]:
    if dataset_name != "damodaran_us_annual_1970_2025":
        raise ValueError(f"unsupported historical dataset: {dataset_name}")

    dataset_path = files("retireplan").joinpath("defaults/historical_market_annual.csv")
    with dataset_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            int(row["year"]): HistoricalMarketRecord(
                year=int(row["year"]),
                stocks=float(row["stocks"]),
                bonds=float(row["bonds"]),
                cash=float(row["cash"]),
                inflation=float(row["inflation"]),
            )
            for row in reader
        }


def historical_record_for_projection_year(
    scenario: RetirementScenario,
    projection_year: int,
) -> HistoricalMarketRecord:
    if not historical_projection_enabled(scenario):
        raise ValueError("historical projection is not active for this scenario")

    start_year = int(scenario.historical_analysis.selected_start_year or 0)
    dataset_year = start_year + (projection_year - scenario.simulation.start_date.year)
    dataset = load_historical_market_dataset(str(scenario.historical_analysis.dataset))
    try:
        return dataset[dataset_year]
    except KeyError as exc:
        raise ValueError(f"historical dataset does not contain year {dataset_year}") from exc


def compound_growth_factor(
    scenario: RetirementScenario,
    start_year: int,
    end_year: int,
    fixed_rate: float,
    *,
    use_historical_inflation: bool,
) -> float:
    if end_year <= start_year:
        return 1.0

    factor = 1.0
    for year in range(start_year + 1, end_year + 1):
        if historical_projection_enabled(scenario) and use_historical_inflation:
            rate = historical_record_for_projection_year(scenario, year).inflation
        else:
            rate = fixed_rate
        factor *= 1.0 + rate
    return factor


def account_return_for_period(
    account: Account,
    period: TimelinePeriod,
    scenario: RetirementScenario,
) -> float:
    if historical_projection_enabled(scenario):
        return account_type_return_for_period(account.type, period, scenario)
    return fixed_account_return_for_year(account, period.year, scenario)


def account_type_return_for_period(
    account_type: AccountType,
    period: TimelinePeriod,
    scenario: RetirementScenario,
) -> float:
    if historical_projection_enabled(scenario):
        policy = scenario.historical_analysis.account_type_return_policies[account_type]
        age = _reference_age_for_account_type(account_type, period, scenario)
        allocation = next(
            (
                band.allocation
                for band in policy.glide_path
                if band.start_age <= age <= band.end_age
            ),
            None,
        )
        if allocation is None:
            raise ValueError(
                f"no historical glide path band covers age {age} for account type {account_type.value}"
            )
        record = historical_record_for_projection_year(scenario, period.year)
        return (
            allocation.stocks * record.stocks
            + allocation.bonds * record.bonds
            + allocation.cash * record.cash
        )

    matching_returns = [
        fixed_account_return_for_year(account, period.year, scenario)
        for account in scenario.accounts
        if account.type == account_type
    ]
    if matching_returns:
        return sum(matching_returns) / len(matching_returns)
    return float(scenario.assumptions.investment_return_default)


def fixed_account_return_for_year(
    account: Account,
    year: int,
    scenario: RetirementScenario,
) -> float:
    from datetime import date

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


def historical_start_years_for_scenario(scenario: RetirementScenario) -> list[int]:
    dataset = load_historical_market_dataset(str(scenario.historical_analysis.dataset))
    dataset_years = sorted(dataset)
    projection_years = len(build_timeline(scenario))
    latest_start = dataset_years[-1] - projection_years + 1
    return [year for year in dataset_years if year <= latest_start]


def historical_weight_for_start_year(scenario: RetirementScenario, start_year: int) -> float:
    weighting = scenario.historical_analysis.weighting
    if weighting.method == "modern_heavier" and start_year >= int(weighting.modern_start_year or 0):
        return float(weighting.modern_weight_multiplier)
    return 1.0


def _reference_age_for_account_type(
    account_type: AccountType,
    period: TimelinePeriod,
    scenario: RetirementScenario,
) -> int:
    matching_accounts = [account for account in scenario.accounts if account.type == account_type]
    if not matching_accounts:
        return max(period.husband_age, period.wife_age)

    owners = {account.owner for account in matching_accounts}
    if owners == {AccountOwner.HUSBAND}:
        return period.husband_age
    if owners == {AccountOwner.WIFE}:
        return period.wife_age
    living_ages = []
    if period.husband_alive:
        living_ages.append(period.husband_age)
    if period.wife_alive:
        living_ages.append(period.wife_age)
    if living_ages:
        return max(living_ages)
    return max(period.husband_age, period.wife_age)
