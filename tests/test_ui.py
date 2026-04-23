import os
from copy import deepcopy

from retireplan.io.scenario_loader import ScenarioLoadResult

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import yaml
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from retireplan.core import analyze_historical_cohorts, project_scenario
from retireplan.io import load_scenario_text
from retireplan.reporting import build_reporting_bundle
from retireplan.ui import RetirePlanWindow
from retireplan.ui.viewmodels import (
    build_comparison_table,
    build_ui_snapshot,
    transpose_table,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_load_scenario_text_uses_same_validation_pipeline_as_file_loader(
    golden_loaded: ScenarioLoadResult,
):
    loaded = golden_loaded
    text = loaded.path.read_text(encoding="utf-8")

    from_text = load_scenario_text(text, path_hint=loaded.path)

    assert from_text.scenario.metadata.version == loaded.scenario.metadata.version
    assert from_text.scenario.metadata.scenario_name == loaded.scenario.metadata.scenario_name
    assert from_text.warnings == loaded.warnings


def test_ui_snapshot_exposes_stage_9_views(golden_loaded: ScenarioLoadResult):
    loaded = golden_loaded
    result = project_scenario(loaded.scenario, loaded.warnings)
    reporting = build_reporting_bundle(result, loaded.scenario)

    snapshot = build_ui_snapshot(loaded.scenario, result, reporting, loaded.warnings)
    comparison = build_comparison_table(snapshot, snapshot)

    assert snapshot.results_table.columns[0] == "year"
    assert snapshot.results_table.columns[1] == "husband/wife ages"
    assert "husband_age" not in snapshot.results_table.columns
    assert "wife_age" not in snapshot.results_table.columns
    assert snapshot.cashflow_table.columns[0] == "year"
    assert snapshot.cashflow_table.columns[1] == "husband/wife ages"
    assert "bridge_withdrawal_for_conversion_taxes" in snapshot.cashflow_table.columns
    assert "bridge_withdrawal_for_operations" in snapshot.cashflow_table.columns
    age_sixty_six_cashflow = next(row for row in snapshot.cashflow_table.rows if row[0] == 2033)
    assert age_sixty_six_cashflow[9] == 23455
    assert age_sixty_six_cashflow[10] == 27997
    assert age_sixty_six_cashflow[11] == 0
    assert age_sixty_six_cashflow[12] == 27997
    assert snapshot.activity_table.columns[0] == "year"
    assert snapshot.activity_table.columns[1] == "husband/wife ages"
    assert snapshot.activity_table.columns[4] == "qcd_distribution_total"
    assert snapshot.activity_table.columns[5] == "qcd_distributions"
    assert snapshot.activity_table.columns[6] == "roth_conversion_total"
    assert snapshot.qcd_depletion_table.columns[0] == "year"
    assert snapshot.qcd_depletion_table.columns[1] == "husband/wife ages"
    assert "wife_balance" not in snapshot.qcd_depletion_table.columns
    assert "wife_target_age" not in snapshot.qcd_depletion_table.columns
    assert "wife_required_qcd" not in snapshot.qcd_depletion_table.columns
    assert "wife_actual_qcd" not in snapshot.qcd_depletion_table.columns
    assert "wife_projected_balance_at_target_age" not in snapshot.qcd_depletion_table.columns
    assert all(row[0] >= 2038 for row in snapshot.qcd_depletion_table.rows)
    qcd_row = next(row for row in snapshot.qcd_depletion_table.rows if row[0] == 2042)
    assert qcd_row[3] == 89
    assert qcd_row[-2] is True
    assert qcd_row[-1] is False
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
    assert first_mortgage_row[2] == 1899
    assert first_mortgage_row[3] == "2032-11"
    assert first_mortgage_row[4] == 3529
    assert first_mortgage_row[5] == 1260
    assert first_mortgage_row[6] == 25956
    assert first_mortgage_row[9] == 21167
    assert first_mortgage_row[12] == 210402
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
    assert "effective_tax_rate" in snapshot.roth_planner_table.columns
    assert "irmaa_tier" in snapshot.roth_planner_table.columns
    assert "medicare_total" in snapshot.roth_planner_table.columns
    assert "planner_notes" in snapshot.roth_planner_table.columns
    first_planner_row = snapshot.roth_planner_table.rows[0]
    assert first_planner_row[0] == 2033
    assert first_planner_row[1] == "66 / 66"
    assert first_planner_row[4] == "21.3%"
    assert first_planner_row[7] == 0.0
    assert first_planner_row[8] == 5323
    assert "current-year MAGI via work_stoppage reconsideration" in first_planner_row[9]
    assert snapshot.irmaa_table.columns[0] == "year"
    assert len(snapshot.charts) == 4
    assert all(chart.x_axis == "age" for chart in snapshot.charts)
    assert all(chart.y_axis_step % 50000.0 == 0.0 for chart in snapshot.charts)
    assert snapshot.detail_years[0] == 2026
    assert '"year": 2026' in snapshot.detail_json_by_year[2026]
    assert "11912" in snapshot.detail_json_by_year[2026]
    assert '"qcd_distributions": {' in snapshot.detail_json_by_year[2042]
    assert '"rollovers": {' in snapshot.detail_json_by_year[2033]
    assert '"summary":' in snapshot.detail_summary_json
    assert comparison.columns[0] == "metric"


def test_stage_9_window_exposes_required_tabs(golden_loaded: ScenarioLoadResult):
    app = _app()
    loaded = golden_loaded
    result = project_scenario(loaded.scenario, loaded.warnings)
    reporting = build_reporting_bundle(result, loaded.scenario)
    snapshot = build_ui_snapshot(loaded.scenario, result, reporting, loaded.warnings)

    window = RetirePlanWindow()
    window.apply_projection_snapshot(snapshot)

    tab_labels = [window.tabs.tabText(index) for index in range(window.tabs.count())]

    assert app is not None
    assert tab_labels == [
        "Inputs",
        "Results Table",
        "Cash Flow",
        "Retirement Activity",
        "QCD Depletion",
        "Mortgage",
        "Account Balances",
        "Calculation Details",
        "Charts",
        "Historical Cohorts",
        "Roth Conversion Planner",
        "IRMAA Warnings",
        "Scenario Compare",
    ]
    assert window.results_table.rowCount() == len(snapshot.results_table.rows)
    assert window.cashflow_table.rowCount() == len(snapshot.cashflow_table.rows)
    assert window.activity_table.rowCount() == len(snapshot.activity_table.rows)
    assert window.qcd_depletion_table.rowCount() == len(snapshot.qcd_depletion_table.rows)
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
    first_chart = window.charts_tab.widget(0).chart()
    axis_x = first_chart.axes(Qt.Horizontal)[0]
    axis_y = first_chart.axes(Qt.Vertical)[0]
    assert axis_x.titleText() == "Age"
    assert axis_x.tickInterval() == 5.0
    assert axis_y.titleText() == "Amount ($K)"
    assert axis_y.labelFormat() == "$%.0fK"
    assert window.mortgage_table.item(0, 2).text() == "1,899"

    window.close()


def test_ui_snapshot_exposes_historical_cohort_results(golden_payload: dict):
    payload = deepcopy(golden_payload)
    payload["historical_analysis"] = {
        "enabled": True,
        "weighting": {
            "method": "modern_heavier",
            "modern_start_year": 1990,
            "modern_weight_multiplier": 3.0,
        },
    }
    loaded = load_scenario_text(yaml.safe_dump(payload, sort_keys=False))
    analysis = analyze_historical_cohorts(loaded.scenario, loaded.warnings)
    result = project_scenario(loaded.scenario, loaded.warnings)
    reporting = build_reporting_bundle(result, loaded.scenario, analysis)

    snapshot = build_ui_snapshot(
        loaded.scenario,
        result,
        reporting,
        loaded.warnings,
        analysis,
    )

    assert analysis is not None
    assert snapshot.historical_summary_rows[1] == (
        "Weighted Success Rate",
        f"{analysis.weighted_success_rate:.1%}",
    )
    assert snapshot.historical_summary_rows[2] == ("Target Success Rate", "90.0%")
    assert snapshot.historical_cohorts_table.columns[0] == "start_year"
    assert len(snapshot.historical_cohorts_table.rows) == analysis.cohort_count
    assert len(snapshot.charts) == 5
    assert snapshot.charts[-1].title == "Historical Cohort Terminal Net Worth"
    assert '"historical_analysis": {' in snapshot.detail_summary_json
