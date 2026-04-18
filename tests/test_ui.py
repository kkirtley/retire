import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from retireplan.core import project_scenario
from retireplan.io import load_scenario, load_scenario_text
from retireplan.reporting import build_reporting_bundle
from retireplan.ui import RetirePlanWindow
from retireplan.ui.viewmodels import (
    build_comparison_table,
    build_ui_snapshot,
    transpose_table,
)


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

    snapshot = build_ui_snapshot(loaded.scenario, result, reporting, loaded.warnings)
    comparison = build_comparison_table(snapshot, snapshot)

    assert snapshot.results_table.columns[0] == "year"
    assert snapshot.results_table.columns[1] == "husband/wife ages"
    assert "husband_age" not in snapshot.results_table.columns
    assert "wife_age" not in snapshot.results_table.columns
    assert snapshot.activity_table.columns[0] == "year"
    assert snapshot.activity_table.columns[1] == "husband/wife ages"
    assert snapshot.activity_table.columns[4] == "roth_conversion_total"
    assert snapshot.mortgage_table.columns[0] == "year"
    assert snapshot.mortgage_table.columns[1] == "husband/wife ages"
    assert snapshot.mortgage_table.columns[2] == "monthly_payment"
    assert snapshot.mortgage_table.columns[3] == "payoff_date"
    assert snapshot.mortgage_table.columns[4] == "property_tax"
    assert snapshot.mortgage_table.columns[5] == "homeowners_insurance"
    assert snapshot.mortgage_table.columns[6] == "total_housing_payment"
    assert snapshot.mortgage_table.columns[-1] == "remaining_balance"
    first_mortgage_row = snapshot.mortgage_table.rows[0]
    assert first_mortgage_row[0] == 2026
    assert first_mortgage_row[1] == "59 / 59"
    assert first_mortgage_row[2] == 3527.79
    assert first_mortgage_row[3] == "2032-11"
    assert first_mortgage_row[4] == 3528.77
    assert first_mortgage_row[5] == 1260.27
    assert first_mortgage_row[6] == 25955.8
    assert first_mortgage_row[9] == 21166.76
    assert first_mortgage_row[12] == 210401.83
    assert snapshot.account_balances_table.columns[0] == "year"
    assert snapshot.account_balances_table.columns[1] == "husband/wife ages"
    assert snapshot.account_balances_table.columns[2] == "surplus to Taxable Bridge Account"
    assert "Husband Traditional IRA" in snapshot.account_balances_table.columns
    assert [table.name for table in snapshot.account_balance_tables] == [
        "All",
        "Husband",
        "Wife",
        "Household",
    ]
    husband_table = next(
        table.table for table in snapshot.account_balance_tables if table.name == "Husband"
    )
    transposed_husband_table = transpose_table(husband_table)
    assert "surplus to Taxable Bridge Account" not in husband_table.columns
    assert "Wife Traditional IRA" not in husband_table.columns
    assert transposed_husband_table.columns[0] == "year"
    assert transposed_husband_table.rows[0][0] == "husband/wife ages"
    assert transposed_husband_table.rows[1][0] == "Husband Traditional IRA"
    assert snapshot.roth_planner_table.columns[0] == "year"
    assert snapshot.roth_planner_table.columns[1] == "husband/wife ages"
    assert "irmaa_tier" in snapshot.roth_planner_table.columns
    assert "medicare_total" in snapshot.roth_planner_table.columns
    assert "planner_notes" in snapshot.roth_planner_table.columns
    first_planner_row = snapshot.roth_planner_table.rows[0]
    assert first_planner_row[0] == 2033
    assert first_planner_row[1] == "66 / 66"
    assert first_planner_row[6] == 0.0
    assert first_planner_row[7] == 5025.6
    assert "current-year MAGI via work_stoppage reconsideration" in first_planner_row[8]
    assert snapshot.irmaa_table.columns[0] == "year"
    assert len(snapshot.charts) == 4
    assert snapshot.detail_years[0] == 2026
    assert '"year": 2026' in snapshot.detail_json_by_year[2026]
    assert '"rollovers": {' in snapshot.detail_json_by_year[2033]
    assert '"summary":' in snapshot.detail_summary_json
    assert comparison.columns[0] == "metric"


def test_stage_9_window_exposes_required_tabs():
    app = _app()
    loaded = _baseline_loaded()
    result = project_scenario(loaded.scenario, loaded.warnings)
    reporting = build_reporting_bundle(result)
    snapshot = build_ui_snapshot(loaded.scenario, result, reporting, loaded.warnings)

    window = RetirePlanWindow()
    window.apply_projection_snapshot(snapshot)

    tab_labels = [window.tabs.tabText(index) for index in range(window.tabs.count())]

    assert app is not None
    assert tab_labels == [
        "Inputs",
        "Results Table",
        "Retirement Activity",
        "Mortgage",
        "Account Balances",
        "Calculation Details",
        "Charts",
        "Roth Conversion Planner",
        "IRMAA Warnings",
        "Scenario Compare",
    ]
    assert window.results_table.rowCount() == len(snapshot.results_table.rows)
    assert window.activity_table.rowCount() == len(snapshot.activity_table.rows)
    assert window.mortgage_table.rowCount() == len(snapshot.mortgage_table.rows)
    assert window.account_balances_table.rowCount() == len(snapshot.account_balances_table.rows)
    assert window.account_balances_table.columnCount() == len(
        snapshot.account_balances_table.columns
    )
    window.account_balance_filter.setCurrentText("Wife")
    assert window.account_balances_table.columnCount() < len(
        snapshot.account_balances_table.columns
    )
    wife_row_count = window.account_balances_table.rowCount()
    wife_column_count = window.account_balances_table.columnCount()
    window.account_balance_transpose.setChecked(True)
    assert window.account_balances_table.columnCount() == wife_row_count + 1
    assert window.account_balances_table.rowCount() == wife_column_count - 1
    window.detail_year_filter.setCurrentText("2026")
    assert '"year": 2026' in window.detail_output.toPlainText()
    assert window.charts_tab.count() == len(snapshot.charts)

    window.close()
