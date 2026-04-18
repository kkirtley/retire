from pathlib import Path

from retireplan.core import TimelineEvent, build_timeline
from retireplan.io import load_scenario


def test_timeline_builder_creates_prorated_first_year_and_events():
    scenario_path = Path(__file__).resolve().parents[1] / "scenarios" / "baseline_v1.0.1.yaml"
    loaded = load_scenario(scenario_path)

    timeline = build_timeline(loaded.scenario)

    assert timeline
    assert timeline[0].year == 2026
    assert timeline[0].period_start.isoformat() == "2026-07-01"
    assert round(timeline[0].fraction_of_year, 4) == round(184 / 365, 4)
    assert TimelineEvent.SCENARIO_START in timeline[0].events
    assert timeline[0].has_event(TimelineEvent.HUSBAND_EARNED_INCOME_ACTIVE)
    assert timeline[-1].wife_age == 100


def test_timeline_builder_marks_retirement_and_medicare_milestones():
    scenario_path = Path(__file__).resolve().parents[1] / "scenarios" / "baseline_v1.0.1.yaml"
    loaded = load_scenario(scenario_path)

    timeline = build_timeline(loaded.scenario)
    by_year = {period.year: period for period in timeline}

    assert by_year[2033].has_event(TimelineEvent.HOUSEHOLD_RETIREMENT_TRANSITION)
    assert by_year[2032].has_event(TimelineEvent.HUSBAND_MEDICARE_AGE)
    assert by_year[2032].has_event(TimelineEvent.WIFE_MEDICARE_AGE)
    assert by_year[2033].husband_retired is True
    assert by_year[2033].wife_retired is True
