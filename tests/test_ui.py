import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from retireplan.core import project_scenario
from retireplan.io import load_scenario, load_scenario_text
from retireplan.reporting import build_reporting_bundle
from retireplan.ui import RetirePlanWindow
from retireplan.ui.viewmodels import build_comparison_table, build_ui_snapshot


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _baseline_loaded():
    scenario_path = Path(__file__).resolve().parents[1] / "scenarios" / "baseline_v1.0.1.yaml"
    return load_scenario(scenario_path)


def test_load_scenario_text_uses_same_validation_pipeline_as_file_loader():
    loaded = _baseline_loaded()
    text = loaded.path.read_text(encoding="utf-8")

    from_text = load_scenario_text(text, path_hint=loaded.path)

    assert from_text.scenario.metadata.version == loaded.scenario.metadata.version
    assert from_text.scenario.metadata.scenario_name == loaded.scenario.metadata.scenario_name
    assert from_text.warnings == loaded.warnings


def test_ui_snapshot_exposes_stage_9_views():
    loaded = _baseline_loaded()
    result = project_scenario(loaded.scenario, loaded.warnings)
    reporting = build_reporting_bundle(result)

    snapshot = build_ui_snapshot(result, reporting, loaded.warnings)
    comparison = build_comparison_table(snapshot, snapshot)

    assert snapshot.results_table.columns[0] == "year"
    assert snapshot.roth_planner_table.columns[0] == "year"
    assert snapshot.irmaa_table.columns[0] == "year"
    assert len(snapshot.charts) == 4
    assert comparison.columns[0] == "metric"


def test_stage_9_window_exposes_required_tabs():
    app = _app()
    loaded = _baseline_loaded()
    result = project_scenario(loaded.scenario, loaded.warnings)
    reporting = build_reporting_bundle(result)
    snapshot = build_ui_snapshot(result, reporting, loaded.warnings)

    window = RetirePlanWindow()
    window.apply_projection_snapshot(snapshot)

    tab_labels = [window.tabs.tabText(index) for index in range(window.tabs.count())]

    assert app is not None
    assert tab_labels == [
        "Inputs",
        "Results Table",
        "Charts",
        "Roth Conversion Planner",
        "IRMAA Warnings",
        "Scenario Compare",
    ]
    assert window.results_table.rowCount() == len(snapshot.results_table.rows)
    assert window.charts_tab.count() == len(snapshot.charts)

    window.close()
