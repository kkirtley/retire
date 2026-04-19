"""Projection engine exports."""

from retireplan.core.historical_analysis import (
    HistoricalAnalysisResult,
    HistoricalCohortSummary,
    analyze_historical_cohorts,
)
from retireplan.core.projection import ProjectionResult, ProjectionRow, project_scenario
from retireplan.core.timeline_builder import (
    TimelineEvent,
    TimelinePeriod,
    build_timeline,
    year_fraction_for_dates,
)

__all__ = [
    "HistoricalAnalysisResult",
    "HistoricalCohortSummary",
    "ProjectionResult",
    "ProjectionRow",
    "TimelineEvent",
    "TimelinePeriod",
    "analyze_historical_cohorts",
    "build_timeline",
    "project_scenario",
    "year_fraction_for_dates",
]
