"""CLI entry point for retireplan."""

import typer

app = typer.Typer(help="Retirement planning tool for veteran households.")


@app.command()
def validate(scenario_path: str = typer.Argument(..., help="Path to YAML scenario file")):
    """Validate a scenario file."""
    typer.echo(f"Validating scenario: {scenario_path}")


@app.command()
def run(
    scenario_path: str = typer.Argument(..., help="Path to YAML scenario file"),
    out: str = typer.Option("results/run.json", help="Output file path"),
    charts: str = typer.Option("results/", help="Charts output directory"),
):
    """Run a retirement projection."""
    typer.echo(f"Running scenario: {scenario_path}")
    typer.echo(f"Output: {out}")
    typer.echo(f"Charts: {charts}")


if __name__ == "__main__":
    app()
