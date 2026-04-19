import json

from typer.testing import CliRunner

from retireplan.cli.main import app

runner = CliRunner()


def test_validate_command_reports_diagnostics(golden_scenario_path, golden_loaded):
    result = runner.invoke(app, ["validate", str(golden_scenario_path)])

    assert result.exit_code == 0
    assert (
        f"Scenario valid: {golden_loaded.scenario.metadata.scenario_name}"
        f" v{golden_loaded.scenario.metadata.version}"
    ) in result.stdout
    assert "Warnings: none" in result.stdout


def test_run_command_writes_projection_file(tmp_path, golden_scenario_path, golden_loaded):
    output_path = tmp_path / "run.json"
    charts_path = tmp_path / "charts"

    result = runner.invoke(
        app,
        [
            "run",
            str(golden_scenario_path),
            "--out",
            str(output_path),
            "--charts",
            str(charts_path),
        ],
    )

    assert result.exit_code == 0
    assert output_path.exists()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["scenario"]["version"] == golden_loaded.scenario.metadata.version
    assert payload["summary"]["terminal_net_worth"] >= 0
    assert payload["summary"]["failure_year_if_any"] is None
    assert isinstance(payload["summary"]["terminal_net_worth"], int)
    assert payload["reporting"]["charts"]["total_liquid_net_worth"]["series"]
    assert "yearly_overview" in payload["report_exports"]["tables"]
    assert payload["ledger"]
    assert payload["warnings"]
    assert (charts_path / "reporting.json").exists()
    assert (charts_path / "chart_series.json").exists()
    assert (charts_path / "yearly_overview.csv").exists()
