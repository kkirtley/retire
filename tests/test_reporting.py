import json
from pathlib import Path

from retireplan.core import project_scenario
from retireplan.io import load_scenario
from retireplan.reporting import build_reporting_bundle, write_reporting_bundle


def _baseline_result():
    scenario_path = Path(__file__).resolve().parents[1] / "scenarios" / "baseline_v1.0.1.yaml"
    loaded = load_scenario(scenario_path)
    return project_scenario(loaded.scenario, loaded.warnings)


def test_reporting_bundle_contains_stage_8_tables_and_charts():
    result = _baseline_result()

    bundle = build_reporting_bundle(result)

    assert bundle["summary"]["rows"] == len(result.ledger)
    assert set(bundle["tables"]) == {
        "yearly_overview",
        "cashflow",
        "tax_detail",
        "account_balances",
    }
    assert set(bundle["charts"]) == {
        "total_liquid_net_worth",
        "income_vs_expenses",
        "taxes_over_time",
        "account_balances_stacked",
    }
    assert len(bundle["tables"]["yearly_overview"]["rows"]) == len(result.ledger)
    assert bundle["charts"]["total_liquid_net_worth"]["series"][0]["points"][-1]["value"] == (
        result.summary["terminal_net_worth"]
    )


def test_reporting_bundle_writes_json_and_csv_exports(tmp_path: Path):
    result = _baseline_result()
    bundle = build_reporting_bundle(result)

    manifest = write_reporting_bundle(bundle, tmp_path)

    reporting_payload = json.loads((tmp_path / "reporting.json").read_text(encoding="utf-8"))
    chart_payload = json.loads((tmp_path / "chart_series.json").read_text(encoding="utf-8"))

    assert Path(manifest["reporting_json"]).name == "reporting.json"
    assert Path(manifest["chart_series_json"]).name == "chart_series.json"
    assert set(manifest["tables"]) == {
        "yearly_overview",
        "cashflow",
        "tax_detail",
        "account_balances",
    }
    assert reporting_payload["summary"]["scenario_name"] == result.scenario_name
    assert "taxes_over_time" in chart_payload
    assert (tmp_path / "yearly_overview.csv").exists()
    assert (tmp_path / "cashflow.csv").exists()
    assert (tmp_path / "tax_detail.csv").exists()
    assert (tmp_path / "account_balances.csv").exists()
