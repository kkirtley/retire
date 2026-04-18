import json
from pathlib import Path

from typer.testing import CliRunner

from retireplan.cli.main import app

runner = CliRunner()


def test_validate_command_reports_diagnostics():
    scenario_path = Path(__file__).resolve().parents[1] / "scenarios" / "baseline_v1.0.1.yaml"

    result = runner.invoke(app, ["validate", str(scenario_path)])

    assert result.exit_code == 0
    assert "Scenario valid: baseline v1.1.0" in result.stdout
    assert "Warning:" in result.stdout


def test_run_command_writes_projection_file(tmp_path: Path):
    scenario_path = Path(__file__).resolve().parents[1] / "scenarios" / "baseline_v1.0.1.yaml"
    output_path = tmp_path / "run.json"
    charts_path = tmp_path / "charts"

    result = runner.invoke(
        app,
        ["run", str(scenario_path), "--out", str(output_path), "--charts", str(charts_path)],
    )

    assert result.exit_code == 0
    assert output_path.exists()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["scenario"]["version"] == "1.1.0"
    assert payload["summary"]["terminal_net_worth"] > 0.0
    assert payload["ledger"]
    assert payload["warnings"]
