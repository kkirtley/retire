"""CLI entry point for retireplan."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from retireplan.core import project_scenario
from retireplan.io import load_scenario
from retireplan.reporting import build_reporting_bundle, write_reporting_bundle

app = typer.Typer(help="Retirement planning tool for veteran households.")
SCENARIO_ARGUMENT = typer.Argument(..., help="Path to YAML scenario file")
OUTPUT_OPTION = typer.Option(Path("results/run.json"), help="Output file path")
CHARTS_OPTION = typer.Option(Path("results/"), help="Charts output directory")


@app.command()
def validate(scenario_path: Path = SCENARIO_ARGUMENT):
    """Validate a scenario file."""
    loaded = load_scenario(scenario_path)
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
):
    """Run a retirement projection."""
    loaded = load_scenario(scenario_path)
    result = project_scenario(loaded.scenario, loaded.warnings)
    reporting = build_reporting_bundle(result)

    out = out.expanduser()
    charts = charts.expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    report_exports = write_reporting_bundle(reporting, charts)

    payload = {
        "scenario": {
            "name": result.scenario_name,
            "version": result.version,
            "path": str(loaded.path),
        },
        "warnings": result.warnings,
        "summary": result.summary,
        "success": result.success,
        "failure_year": result.failure_year,
        "reporting": reporting,
        "report_exports": report_exports,
        "ledger": [row.__dict__ for row in result.ledger],
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    typer.echo(f"Projection complete: {result.scenario_name} v{result.version}")
    typer.echo(f"Success: {result.success}")
    typer.echo(f"Output: {out.resolve()}")
    typer.echo(f"Charts directory written: {charts.resolve()}")
    if result.warnings:
        typer.echo(f"Warnings: {len(result.warnings)}")


if __name__ == "__main__":
    app()
