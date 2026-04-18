"""PySide6 desktop UI for scenario editing and projection review."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from retireplan.core import project_scenario
from retireplan.io import load_scenario, load_scenario_text
from retireplan.reporting import build_reporting_bundle
from retireplan.ui.viewmodels import (
    UiProjectionSnapshot,
    UiTableModel,
    build_comparison_table,
    build_ui_snapshot,
    transpose_table,
)


class RetirePlanWindow(QMainWindow):
    def __init__(
        self,
        scenario_path: str | Path | None = None,
        compare_path: str | Path | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("RetirePlan")
        self.resize(1440, 960)

        self.scenario_path = Path(scenario_path).expanduser().resolve() if scenario_path else None
        self.compare_path = Path(compare_path).expanduser().resolve() if compare_path else None

        self.scenario_path_input = QLineEdit()
        self.compare_path_input = QLineEdit()
        self.inputs_editor = QPlainTextEdit()
        self.inputs_warning_label = QLabel()
        self.summary_label = QLabel()
        self.results_table = QTableWidget()
        self.account_balance_filter = QComboBox()
        self.account_balance_transpose = QCheckBox("Transpose table")
        self.account_balances_table = QTableWidget()
        self.detail_year_filter = QComboBox()
        self.detail_output = QPlainTextEdit()
        self.charts_tab = QTabWidget()
        self.roth_table = QTableWidget()
        self.irmaa_table = QTableWidget()
        self.compare_label = QLabel("Load a comparison scenario to populate this tab.")
        self.compare_table = QTableWidget()
        self.tabs = QTabWidget()
        self._account_balance_tables: dict[str, UiTableModel] = {}
        self._detail_json_by_year: dict[int, str] = {}
        self._detail_summary_json = ""

        self._build_ui()
        self._wire_actions()

        if self.scenario_path is not None:
            self.load_scenario_file(self.scenario_path)
        if self.compare_path is not None:
            self.compare_path_input.setText(str(self.compare_path))

    def _build_ui(self) -> None:
        self.setStatusBar(QStatusBar(self))
        self._build_toolbar()

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.addLayout(self._build_path_controls())
        layout.addWidget(self.tabs)

        self.inputs_warning_label.setWordWrap(True)
        self.summary_label.setWordWrap(True)
        self.compare_label.setWordWrap(True)
        self.detail_output.setReadOnly(True)

        inputs_widget = QWidget()
        inputs_layout = QVBoxLayout(inputs_widget)
        inputs_layout.addWidget(self.inputs_warning_label)
        inputs_layout.addWidget(self.inputs_editor)

        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.addWidget(self.summary_label)
        results_layout.addWidget(self.results_table)

        balances_widget = QWidget()
        balances_layout = QVBoxLayout(balances_widget)
        balances_layout.addWidget(self.account_balance_filter)
        balances_layout.addWidget(self.account_balance_transpose)
        balances_layout.addWidget(self.account_balances_table)

        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.addWidget(self.detail_year_filter)
        details_layout.addWidget(self.detail_output)

        charts_widget = QWidget()
        charts_layout = QVBoxLayout(charts_widget)
        charts_layout.addWidget(self.charts_tab)

        compare_widget = QWidget()
        compare_layout = QVBoxLayout(compare_widget)
        compare_layout.addWidget(self.compare_label)
        compare_layout.addWidget(self.compare_table)

        self.tabs.addTab(inputs_widget, "Inputs")
        self.tabs.addTab(results_widget, "Results Table")
        self.tabs.addTab(balances_widget, "Account Balances")
        self.tabs.addTab(details_widget, "Calculation Details")
        self.tabs.addTab(charts_widget, "Charts")
        self.tabs.addTab(self.roth_table, "Roth Conversion Planner")
        self.tabs.addTab(self.irmaa_table, "IRMAA Warnings")
        self.tabs.addTab(compare_widget, "Scenario Compare")

        self.setCentralWidget(container)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        load_action = QAction("Load", self)
        load_action.triggered.connect(self._browse_scenario_file)
        toolbar.addAction(load_action)

        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_scenario)
        toolbar.addAction(save_action)

        run_action = QAction("Run", self)
        run_action.triggered.connect(self.run_projection)
        toolbar.addAction(run_action)

    def _build_path_controls(self) -> QGridLayout:
        layout = QGridLayout()

        load_button = QPushButton("Browse Scenario")
        save_button = QPushButton("Save Scenario")
        run_button = QPushButton("Run Projection")
        compare_button = QPushButton("Browse Compare")

        load_button.clicked.connect(self._browse_scenario_file)
        save_button.clicked.connect(self.save_scenario)
        run_button.clicked.connect(self.run_projection)
        compare_button.clicked.connect(self._browse_compare_file)

        layout.addWidget(QLabel("Scenario YAML"), 0, 0)
        layout.addWidget(self.scenario_path_input, 0, 1)
        layout.addWidget(load_button, 0, 2)
        layout.addWidget(save_button, 0, 3)

        layout.addWidget(QLabel("Compare Scenario"), 1, 0)
        layout.addWidget(self.compare_path_input, 1, 1)
        layout.addWidget(compare_button, 1, 2)
        layout.addWidget(run_button, 1, 3)

        return layout

    def _wire_actions(self) -> None:
        self._configure_table(self.results_table)
        self._configure_table(self.account_balances_table)
        self._configure_table(self.roth_table)
        self._configure_table(self.irmaa_table)
        self._configure_table(self.compare_table)
        self.account_balance_filter.currentTextChanged.connect(
            self._on_account_balance_filter_changed
        )
        self.account_balance_transpose.toggled.connect(self._refresh_account_balance_table)
        self.detail_year_filter.currentTextChanged.connect(self._refresh_detail_output)

    def load_scenario_file(self, path: str | Path) -> None:
        scenario_path = Path(path).expanduser().resolve()
        self.scenario_path = scenario_path
        self.scenario_path_input.setText(str(scenario_path))
        self.inputs_editor.setPlainText(scenario_path.read_text(encoding="utf-8"))
        self.statusBar().showMessage(f"Loaded scenario {scenario_path}", 5000)

    def save_scenario(self) -> None:
        scenario_text = self.inputs_editor.toPlainText()
        path_text = self.scenario_path_input.text().strip()
        if not path_text:
            selected_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Scenario",
                "scenarios/baseline_ui.yaml",
                "YAML Files (*.yaml *.yml)",
            )
            if not selected_path:
                return
            path_text = selected_path
            self.scenario_path_input.setText(path_text)
        scenario_path = Path(path_text).expanduser().resolve()
        scenario_path.parent.mkdir(parents=True, exist_ok=True)
        scenario_path.write_text(scenario_text, encoding="utf-8")
        self.scenario_path = scenario_path
        self.statusBar().showMessage(f"Saved scenario to {scenario_path}", 5000)

    def run_projection(self) -> None:
        try:
            loaded = load_scenario_text(
                self.inputs_editor.toPlainText(),
                path_hint=self.scenario_path_input.text().strip() or None,
            )
            result = project_scenario(loaded.scenario, loaded.warnings)
            reporting = build_reporting_bundle(result)
            snapshot = build_ui_snapshot(loaded.scenario, result, reporting, loaded.warnings)

            comparison_snapshot = None
            compare_text = self.compare_path_input.text().strip()
            if compare_text:
                compare_loaded = load_scenario(compare_text)
                compare_result = project_scenario(compare_loaded.scenario, compare_loaded.warnings)
                compare_reporting = build_reporting_bundle(compare_result)
                comparison_snapshot = build_ui_snapshot(
                    compare_loaded.scenario,
                    compare_result,
                    compare_reporting,
                    compare_loaded.warnings,
                )

            self.apply_projection_snapshot(snapshot, comparison_snapshot)
            self.statusBar().showMessage(
                f"Projection complete for {snapshot.scenario_name} v{snapshot.version}",
                5000,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Projection Error", str(exc))

    def apply_projection_snapshot(
        self,
        snapshot: UiProjectionSnapshot,
        comparison_snapshot: UiProjectionSnapshot | None = None,
    ) -> None:
        self.inputs_warning_label.setText(self._warning_text(snapshot.warnings))
        self.summary_label.setText(
            "\n".join(f"{label}: {value}" for label, value in snapshot.summary_rows)
        )
        self._populate_table(self.results_table, snapshot.results_table)
        self._account_balance_tables = {
            item.name: item.table for item in snapshot.account_balance_tables
        }
        self.account_balance_filter.blockSignals(True)
        self.account_balance_filter.clear()
        self.account_balance_filter.addItems(list(self._account_balance_tables))
        self.account_balance_filter.setCurrentText("All")
        self.account_balance_filter.blockSignals(False)
        self.account_balance_transpose.blockSignals(True)
        self.account_balance_transpose.setChecked(False)
        self.account_balance_transpose.blockSignals(False)
        self._refresh_account_balance_table()
        self._detail_summary_json = snapshot.detail_summary_json
        self._detail_json_by_year = snapshot.detail_json_by_year
        self.detail_year_filter.blockSignals(True)
        self.detail_year_filter.clear()
        self.detail_year_filter.addItem("Projection Summary")
        for year in snapshot.detail_years:
            self.detail_year_filter.addItem(str(year))
        self.detail_year_filter.setCurrentText("Projection Summary")
        self.detail_year_filter.blockSignals(False)
        self._refresh_detail_output()
        self._populate_table(self.roth_table, snapshot.roth_planner_table)
        self._populate_table(self.irmaa_table, snapshot.irmaa_table)
        self._populate_charts(snapshot)

        if comparison_snapshot is None:
            self.compare_label.setText("Load a comparison scenario to populate this tab.")
            self._populate_table(self.compare_table, UiTableModel(columns=(), rows=()))
            return

        self.compare_label.setText(
            f"Comparing {snapshot.scenario_name} v{snapshot.version} against "
            f"{comparison_snapshot.scenario_name} v{comparison_snapshot.version}."
        )
        self._populate_table(
            self.compare_table,
            build_comparison_table(snapshot, comparison_snapshot),
        )

    def _populate_charts(self, snapshot: UiProjectionSnapshot) -> None:
        self.charts_tab.clear()
        for chart in snapshot.charts:
            self.charts_tab.addTab(self._build_chart_view(chart), chart.title)

    def _build_chart_view(self, chart) -> QChartView:
        qchart = QChart()
        qchart.setTitle(chart.title)

        all_years = [point[0] for series in chart.series for point in series.points]
        all_values = [point[1] for series in chart.series for point in series.points]

        axis_x = QValueAxis()
        axis_x.setLabelFormat("%.0f")
        axis_x.setTitleText("Year")
        if all_years:
            axis_x.setRange(float(min(all_years)), float(max(all_years)))

        axis_y = QValueAxis()
        axis_y.setLabelFormat("%.0f")
        axis_y.setTitleText("Value")
        if all_values:
            axis_y.setRange(float(min(0.0, min(all_values))), float(max(all_values) * 1.05 or 1.0))

        qchart.addAxis(axis_x, Qt.AlignBottom)
        qchart.addAxis(axis_y, Qt.AlignLeft)

        for series_model in chart.series:
            series = QLineSeries()
            series.setName(series_model.name)
            for year, value in series_model.points:
                series.append(float(year), float(value))
            qchart.addSeries(series)
            series.attachAxis(axis_x)
            series.attachAxis(axis_y)

        view = QChartView(qchart)
        view.setRenderHint(view.renderHints())
        return view

    def _populate_table(self, table: QTableWidget, model: UiTableModel) -> None:
        table.clear()
        table.setColumnCount(len(model.columns))
        table.setRowCount(len(model.rows))
        if model.columns:
            table.setHorizontalHeaderLabels(list(model.columns))
        for row_index, row in enumerate(model.rows):
            for column_index, value in enumerate(row):
                item = QTableWidgetItem(self._format_cell(value))
                table.setItem(row_index, column_index, item)
        table.resizeColumnsToContents()

    def _warning_text(self, warnings: tuple[str, ...]) -> str:
        if not warnings:
            return "Warnings: none"
        return "Warnings:\n" + "\n".join(f"- {warning}" for warning in warnings)

    def _format_cell(self, value: object) -> str:
        if isinstance(value, float):
            return f"{value:,.2f}"
        return str(value)

    def _configure_table(self, table: QTableWidget) -> None:
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)

    def _on_account_balance_filter_changed(self, filter_name: str) -> None:
        del filter_name
        self._refresh_account_balance_table()

    def _refresh_account_balance_table(self) -> None:
        table = self._account_balance_tables.get(self.account_balance_filter.currentText())
        if table is None:
            return
        if self.account_balance_transpose.isChecked():
            table = transpose_table(table)
        self._populate_table(self.account_balances_table, table)

    def _refresh_detail_output(self) -> None:
        selected = self.detail_year_filter.currentText()
        if not selected or selected == "Projection Summary":
            self.detail_output.setPlainText(self._detail_summary_json)
            return
        try:
            year = int(selected)
        except ValueError:
            self.detail_output.setPlainText("")
            return
        self.detail_output.setPlainText(self._detail_json_by_year.get(year, ""))

    def _browse_scenario_file(self) -> None:
        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Scenario",
            str(self.scenario_path or Path.cwd()),
            "YAML Files (*.yaml *.yml)",
        )
        if selected_path:
            self.load_scenario_file(selected_path)

    def _browse_compare_file(self) -> None:
        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Comparison Scenario",
            str(self.compare_path or Path.cwd()),
            "YAML Files (*.yaml *.yml)",
        )
        if selected_path:
            self.compare_path = Path(selected_path).expanduser().resolve()
            self.compare_path_input.setText(str(self.compare_path))


def launch_ui(
    scenario_path: str | Path | None = None,
    compare_path: str | Path | None = None,
) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = RetirePlanWindow(scenario_path=scenario_path, compare_path=compare_path)
    window.show()
    return app.exec()


def main() -> int:
    scenario_path = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else None
    return launch_ui(scenario_path=scenario_path)


if __name__ == "__main__":
    raise SystemExit(main())
