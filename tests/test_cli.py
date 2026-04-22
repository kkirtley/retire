import json

import yaml
from typer.testing import CliRunner

from retireplan.cli.main import app

runner = CliRunner()


def test_validate_help_includes_strict_validation_flag():
    result = runner.invoke(app, ["validate", "--help"])

    assert result.exit_code == 0
    assert "--strict-validation" in result.stdout


def test_run_help_includes_strict_validation_flag():
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0
    assert "--strict-validation" in result.stdout


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
    assert payload["execution_mode"] == "deterministic_annual"
    assert payload["scenario"]["version"] == golden_loaded.scenario.metadata.version
    assert payload["summary"]["terminal_net_worth"] >= 0
    assert payload["summary"]["failure_year_if_any"] is None
    assert isinstance(payload["summary"]["terminal_net_worth"], int)
    assert payload["output_contract"]["yearly_ledger"]
    assert payload["output_contract"]["account_balances_by_year"]
    assert payload["output_contract"]["taxes_by_year"]
    assert payload["output_contract"]["conversion_totals_by_year"]
    assert payload["output_contract"]["rmd_qcd_giving_by_year"]
    assert payload["output_contract"]["failure_year"] is None
    assert payload["output_contract"]["net_worth"] == payload["summary"]["terminal_net_worth"]
    assert payload["output_contract"]["total_taxes"] == payload["summary"]["total_taxes_paid"]
    assert (
        payload["output_contract"]["total_conversions"]
        == payload["summary"]["total_roth_converted"]
    )
    assert (
        payload["output_contract"]["ira_balance_at_70"]
        == payload["summary"]["traditional_balance_at_husband_age_70"]
    )
    assert payload["reporting"]["charts"]["total_liquid_net_worth"]["series"]
    assert (
        payload["reporting"]["output_contract"]["net_worth"]
        == payload["output_contract"]["net_worth"]
    )
    assert "yearly_overview" in payload["report_exports"]["tables"]
    assert payload["ledger"]
    assert payload["warnings"]
    assert payload["historical_analysis"] is None
    assert (charts_path / "reporting.json").exists()
    assert (charts_path / "chart_series.json").exists()
    assert (charts_path / "yearly_overview.csv").exists()
    assert "Execution mode: deterministic_annual" in result.stdout


def test_validate_command_reports_soft_warnings_when_not_strict(tmp_path, golden_payload):
    payload = golden_payload
    payload["validation"]["strict"] = False
    payload["household"]["husband"]["current_age"] = 99

    scenario_path = tmp_path / "baseline_v9.9.9.yaml"
    scenario_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    result = runner.invoke(app, ["validate", str(scenario_path)])

    assert result.exit_code == 0
    assert "Warning:" in result.stdout
    assert "current_age=99" in result.stdout
    assert "version does not match" in result.stdout


def test_validate_command_strict_override_fails_on_soft_warnings(tmp_path, golden_payload):
    payload = golden_payload
    payload["validation"]["strict"] = False
    payload["household"]["husband"]["current_age"] = 99

    scenario_path = tmp_path / "baseline_v9.9.9.yaml"
    scenario_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    result = runner.invoke(app, ["validate", str(scenario_path), "--strict-validation"])

    assert result.exit_code != 0
    assert result.exception is not None
    assert "Strict validation failed" in str(result.exception)
    assert "current_age=99" in str(result.exception)


def test_run_command_strict_override_fails_on_soft_warnings(tmp_path, golden_payload):
    payload = golden_payload
    payload["validation"]["strict"] = False
    payload["household"]["husband"]["current_age"] = 99

    scenario_path = tmp_path / "baseline_v9.9.9.yaml"
    scenario_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    output_path = tmp_path / "run.json"
    charts_path = tmp_path / "charts"
    result = runner.invoke(
        app,
        [
            "run",
            str(scenario_path),
            "--out",
            str(output_path),
            "--charts",
            str(charts_path),
            "--strict-validation",
        ],
    )

    assert result.exit_code != 0
    assert result.exception is not None
    assert "Strict validation failed" in str(result.exception)
    assert not output_path.exists()


def test_validate_command_strict_override_fails_on_modeled_death_warning(tmp_path, golden_payload):
    payload = golden_payload
    payload["validation"]["strict"] = False
    payload["household"]["husband"]["modeled_death"] = {"enabled": True, "death_year": None}

    scenario_path = tmp_path / "death-warning.yaml"
    scenario_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    result = runner.invoke(app, ["validate", str(scenario_path), "--strict-validation"])

    assert result.exit_code != 0
    assert result.exception is not None
    assert "Strict validation failed" in str(result.exception)
    assert "modeled_death is enabled but death_year is null" in str(result.exception)
