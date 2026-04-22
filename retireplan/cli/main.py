"""CLI entry point for retireplan."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from retireplan.core import analyze_historical_cohorts, project_scenario
from retireplan.io import load_scenario
from retireplan.output_formatting import round_output_value
from retireplan.reporting import build_reporting_bundle, write_reporting_bundle

app = typer.Typer(help="Retirement planning tool for veteran households.")
DEFAULT_EXECUTION_MODE = "deterministic_annual"
SCENARIO_ARGUMENT = typer.Argument(..., help="Path to YAML scenario file")
OUTPUT_OPTION = typer.Option(Path("results/run.json"), help="Output file path")
CHARTS_OPTION = typer.Option(Path("results/"), help="Charts output directory")
COMPARE_OPTION = typer.Option(None, help="Optional comparison scenario path")
STRICT_VALIDATION_OPTION = typer.Option(
    False,
    "--strict-validation",
    help="Force strict validation failures for loader diagnostics that are warnings in non-strict mode.",
)


@app.command()
def validate(
    scenario_path: Path = SCENARIO_ARGUMENT,
    strict_validation: bool = STRICT_VALIDATION_OPTION,
):
    """Validate a scenario file."""
    loaded = load_scenario(
        scenario_path,
        strict_validation=True if strict_validation else None,
    )
    typer.echo(
        f"Scenario valid: {loaded.scenario.metadata.scenario_name} v{loaded.scenario.metadata.version}"
    )
    typer.echo(f"Loaded from: {loaded.path}")
    if loaded.warnings:
        for warning in loaded.warnings:
            typer.echo(f"Warning: {warning}")
    else:
        typer.echo("Warnings: none")


@app.command()
def run(
    scenario_path: Path = SCENARIO_ARGUMENT,
    out: Path = OUTPUT_OPTION,
    charts: Path = CHARTS_OPTION,
    strict_validation: bool = STRICT_VALIDATION_OPTION,
):
    """Run a retirement projection."""
    loaded = load_scenario(
        scenario_path,
        strict_validation=True if strict_validation else None,
    )
    result = project_scenario(loaded.scenario, loaded.warnings)
    historical_analysis = None
    if loaded.scenario.historical_analysis.enabled:
        historical_analysis = analyze_historical_cohorts(loaded.scenario, loaded.warnings)
    reporting = build_reporting_bundle(result, loaded.scenario, historical_analysis)

    out = out.expanduser()
    charts = charts.expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    report_exports = write_reporting_bundle(reporting, charts)

    payload = {
        "execution_mode": DEFAULT_EXECUTION_MODE,
        "scenario": {
            "name": result.scenario_name,
            "version": result.version,
            "path": str(loaded.path),
        },
        "warnings": result.warnings,
        "summary": result.summary,
        "output_contract": result.output_contract,
        "success": result.success,
        "failure_year": result.failure_year,
        "reporting": reporting,
        "historical_analysis": (
            None if historical_analysis is None else historical_analysis.to_dict()
        ),
        "report_exports": report_exports,
        "ledger": [row.__dict__ for row in result.ledger],
    }
    out.write_text(json.dumps(round_output_value(payload), indent=2), encoding="utf-8")

    typer.echo(f"Projection complete: {result.scenario_name} v{result.version}")
    typer.echo(f"Execution mode: {DEFAULT_EXECUTION_MODE}")
    typer.echo(f"Success: {result.success}")
    if historical_analysis is not None:
        typer.echo(
            "Historical weighted success rate: "
            f"{historical_analysis.weighted_success_rate:.1%} "
            f"(target {historical_analysis.target_success_rate:.0%})"
        )
    typer.echo(f"Output: {out.resolve()}")
    typer.echo(f"Charts directory written: {charts.resolve()}")
    if result.warnings:
        typer.echo(f"Warnings: {len(result.warnings)}")


@app.command()
def ui(
    scenario_path: Path = SCENARIO_ARGUMENT,
    compare: Path | None = COMPARE_OPTION,
):
    """Launch the desktop UI."""
    from retireplan.ui.main import launch_ui

    raise typer.Exit(launch_ui(scenario_path, compare))


if __name__ == "__main__":
    app()
