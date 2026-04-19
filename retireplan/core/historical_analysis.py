"""Historical cohort analysis for retirement plan strength testing."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Iterable

from retireplan.core.market_history import (
    historical_start_years_for_scenario,
    historical_weight_for_start_year,
)
from retireplan.core.projection import project_scenario
from retireplan.scenario import RetirementScenario


@dataclass(frozen=True)
class HistoricalCohortSummary:
    start_year: int
    end_year: int
    weight: float
    success: bool
    failure_year: int | None
    terminal_net_worth: float
    total_taxes_paid: float
    total_roth_converted: float


@dataclass(frozen=True)
class HistoricalAnalysisResult:
    dataset: str
    cohort_count: int
    projection_years: int
    target_success_rate: float
    weighted_success_rate: float
    unweighted_success_rate: float
    passes_target: bool
    best_terminal_start_year: int | None
    worst_terminal_start_year: int | None
    cohorts: list[HistoricalCohortSummary]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def analyze_historical_cohorts(
    scenario: RetirementScenario,
    scenario_warnings: Iterable[str] | None = None,
) -> HistoricalAnalysisResult | None:
    if not scenario.historical_analysis.enabled:
        return None

    start_years = historical_start_years_for_scenario(scenario)
    cohorts: list[HistoricalCohortSummary] = []
    total_weight = 0.0
    success_weight = 0.0
    success_count = 0
    best_terminal_start_year: int | None = None
    best_terminal_value: float | None = None
    worst_terminal_start_year: int | None = None
    worst_terminal_value: float | None = None
    projection_years = 0

    for start_year in start_years:
        cohort_scenario = deepcopy(scenario)
        cohort_scenario.historical_analysis.selected_start_year = start_year
        cohort_result = project_scenario(cohort_scenario, scenario_warnings)
        projection_years = len(cohort_result.ledger)
        end_year = start_year + projection_years - 1
        weight = historical_weight_for_start_year(cohort_scenario, start_year)
        terminal_net_worth = float(cohort_result.summary["terminal_net_worth"])
        summary = HistoricalCohortSummary(
            start_year=start_year,
            end_year=end_year,
            weight=round(weight, 4),
            success=cohort_result.success,
            failure_year=cohort_result.failure_year,
            terminal_net_worth=terminal_net_worth,
            total_taxes_paid=float(cohort_result.summary["total_taxes_paid"]),
            total_roth_converted=float(cohort_result.summary["total_roth_converted"]),
        )
        cohorts.append(summary)

        total_weight += weight
        if cohort_result.success:
            success_count += 1
            success_weight += weight

        if best_terminal_value is None or terminal_net_worth > best_terminal_value:
            best_terminal_value = terminal_net_worth
            best_terminal_start_year = start_year
        if worst_terminal_value is None or terminal_net_worth < worst_terminal_value:
            worst_terminal_value = terminal_net_worth
            worst_terminal_start_year = start_year

    if not cohorts:
        raise ValueError(
            "historical analysis could not find enough contiguous years for the scenario horizon"
        )

    weighted_success_rate = success_weight / total_weight if total_weight > 0 else 0.0
    unweighted_success_rate = success_count / len(cohorts)
    target_success_rate = float(scenario.historical_analysis.success_rate_target)
    return HistoricalAnalysisResult(
        dataset=str(scenario.historical_analysis.dataset),
        cohort_count=len(cohorts),
        projection_years=projection_years,
        target_success_rate=target_success_rate,
        weighted_success_rate=round(weighted_success_rate, 4),
        unweighted_success_rate=round(unweighted_success_rate, 4),
        passes_target=weighted_success_rate >= target_success_rate,
        best_terminal_start_year=best_terminal_start_year,
        worst_terminal_start_year=worst_terminal_start_year,
        cohorts=cohorts,
    )
