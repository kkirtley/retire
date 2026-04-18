"""Presentation helpers for the desktop UI."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from retireplan.core import ProjectionResult
from retireplan.mortgage import build_mortgage_schedule
from retireplan.scenario import RetirementScenario


@dataclass(frozen=True)
class UiTableModel:
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]


@dataclass(frozen=True)
class UiChartSeries:
    name: str
    points: tuple[tuple[int, float], ...]


@dataclass(frozen=True)
class UiChartModel:
    title: str
    kind: str
    series: tuple[UiChartSeries, ...]


@dataclass(frozen=True)
class UiProjectionSnapshot:
    scenario_name: str
    version: str
    warnings: tuple[str, ...]
    summary_rows: tuple[tuple[str, str], ...]
    results_table: UiTableModel
    activity_table: UiTableModel
    mortgage_table: UiTableModel
    account_balances_table: UiTableModel
    account_balance_tables: tuple[UiNamedTable, ...]
    roth_planner_table: UiTableModel
    irmaa_table: UiTableModel
    charts: tuple[UiChartModel, ...]
    detail_years: tuple[int, ...]
    detail_json_by_year: dict[int, str]
    detail_summary_json: str
    raw_summary: dict[str, float | int | None]


@dataclass(frozen=True)
class UiNamedTable:
    name: str
    table: UiTableModel


def transpose_table(table: UiTableModel) -> UiTableModel:
    if not table.columns:
        return table

    transposed_columns = (table.columns[0],) + tuple(str(row[0]) for row in table.rows)
    transposed_rows = tuple(
        (column_name,) + tuple(row[column_index] for row in table.rows)
        for column_index, column_name in enumerate(table.columns[1:], start=1)
    )
    return UiTableModel(columns=transposed_columns, rows=transposed_rows)


def _detail_json_by_year(result: ProjectionResult) -> dict[int, str]:
    return {row.year: json.dumps(asdict(row), indent=2) for row in result.ledger}


def _detail_summary_json(
    result: ProjectionResult,
    reporting: dict[str, Any],
    warnings: list[str] | tuple[str, ...],
) -> str:
    payload = {
        "scenario_name": result.scenario_name,
        "version": result.version,
        "success": result.success,
        "failure_year": result.failure_year,
        "warnings": list(warnings),
        "summary": result.summary,
        "reporting_summary": reporting["summary"],
    }
    return json.dumps(payload, indent=2)


def build_ui_snapshot(
    scenario: RetirementScenario,
    result: ProjectionResult,
    reporting: dict[str, Any],
    warnings: list[str] | tuple[str, ...],
) -> UiProjectionSnapshot:
    summary_rows = (
        ("Scenario", f"{result.scenario_name} v{result.version}"),
        ("Success", "Yes" if result.success else "No"),
        ("Failure Year", _format_value(result.failure_year)),
        (
            "Terminal Net Worth",
            _format_value(result.summary.get("terminal_net_worth")),
        ),
        (
            "Total Taxes Paid",
            _format_value(result.summary.get("total_taxes_paid")),
        ),
        (
            "Total Roth Converted",
            _format_value(result.summary.get("total_roth_converted")),
        ),
    )
    account_balance_tables = _account_balance_tables(result, scenario)
    return UiProjectionSnapshot(
        scenario_name=result.scenario_name,
        version=result.version,
        warnings=tuple(warnings),
        summary_rows=summary_rows,
        results_table=_table_from_reporting(
            reporting["tables"]["yearly_overview"],
            excluded_columns=("husband_age", "wife_age"),
        ),
        activity_table=_activity_table(result),
        mortgage_table=_mortgage_table(result, scenario),
        account_balances_table=account_balance_tables[0].table,
        account_balance_tables=account_balance_tables,
        roth_planner_table=_roth_planner_table(result),
        irmaa_table=_irmaa_table(result),
        charts=_charts_from_reporting(reporting["charts"]),
        detail_years=tuple(row.year for row in result.ledger),
        detail_json_by_year=_detail_json_by_year(result),
        detail_summary_json=_detail_summary_json(result, reporting, warnings),
        raw_summary=result.summary,
    )


def build_comparison_table(
    primary: UiProjectionSnapshot,
    comparison: UiProjectionSnapshot,
) -> UiTableModel:
    columns = ("metric", primary.scenario_name, comparison.scenario_name, "delta")
    metrics = (
        ("terminal_net_worth", "Terminal Net Worth"),
        ("total_taxes_paid", "Total Taxes Paid"),
        ("total_roth_converted", "Total Roth Converted"),
        ("projected_rmds_by_year_total", "Projected RMDs"),
        ("total_qcd", "Total QCD"),
        ("total_given", "Total Given"),
    )
    rows = []
    for key, label in metrics:
        primary_value = primary.raw_summary.get(key)
        comparison_value = comparison.raw_summary.get(key)
        delta = None
        if isinstance(primary_value, (int, float)) and isinstance(comparison_value, (int, float)):
            delta = round(primary_value - comparison_value, 2)
        rows.append(
            (
                label,
                _format_value(primary_value),
                _format_value(comparison_value),
                _format_value(delta),
            )
        )
    return UiTableModel(columns=columns, rows=tuple(rows))


def _table_from_reporting(
    table: dict[str, Any],
    excluded_columns: tuple[str, ...] = (),
) -> UiTableModel:
    columns = tuple(column for column in table["columns"] if column not in excluded_columns)
    rows = tuple(tuple(row[column] for column in columns) for row in table["rows"])
    return UiTableModel(columns=columns, rows=rows)


def _roth_planner_table(result: ProjectionResult) -> UiTableModel:
    columns = (
        "year",
        "husband/wife ages",
        "roth_conversion_total",
        "conversion_tax_impact",
        "conversion_tax_payment",
        "conversion_tax_shortfall",
        "irmaa_tier",
        "medicare_total",
        "planner_notes",
    )
    rows = []
    for row in result.ledger:
        if row.strategy.get("roth_conversion_total", 0.0) <= 0:
            continue
        planner_notes = "; ".join(
            alert
            for alert in row.alerts
            if "IRMAA" in alert or "conversion" in alert or "traditional balance target" in alert
        )
        rows.append(
            (
                row.year,
                _ages_label(row.husband_age, row.wife_age),
                row.strategy.get("roth_conversion_total", 0.0),
                row.strategy.get("conversion_tax_impact", 0.0),
                row.strategy.get("conversion_tax_payment", 0.0),
                row.strategy.get("conversion_tax_shortfall", 0.0),
                row.medicare.get("irmaa_tier", 0.0),
                row.medicare.get("total", 0.0),
                planner_notes,
            )
        )
    return UiTableModel(columns=columns, rows=tuple(rows))


def _activity_table(result: ProjectionResult) -> UiTableModel:
    columns = (
        "year",
        "husband/wife ages",
        "rollover_total",
        "rollovers",
        "roth_conversion_total",
        "conversion_tax_impact",
        "conversion_tax_payment",
        "alerts",
    )
    rows = []
    for row in result.ledger:
        rollover_total = round(sum(row.rollovers.values()), 2)
        conversion_total = row.strategy.get("roth_conversion_total", 0.0)
        if rollover_total <= 0 and conversion_total <= 0:
            continue
        rollovers = "; ".join(
            f"{name}: {_format_value(amount)}" for name, amount in row.rollovers.items()
        )
        rows.append(
            (
                row.year,
                _ages_label(row.husband_age, row.wife_age),
                rollover_total,
                rollovers,
                conversion_total,
                row.strategy.get("conversion_tax_impact", 0.0),
                row.strategy.get("conversion_tax_payment", 0.0),
                "; ".join(row.alerts),
            )
        )
    return UiTableModel(columns=columns, rows=tuple(rows))


def _mortgage_table(result: ProjectionResult, scenario: RetirementScenario) -> UiTableModel:
    mortgage_schedule = build_mortgage_schedule(scenario)
    monthly_payment = round(
        float(scenario.mortgage.scheduled_payment_monthly)
        + mortgage_schedule.extra_payment_monthly,
        2,
    )
    columns = (
        "year",
        "husband/wife ages",
        "monthly_payment",
        "scheduled_payment",
        "extra_principal",
        "total_payment",
        "interest",
        "principal",
        "remaining_balance",
    )
    rows = []
    for row in result.ledger:
        if (
            row.mortgage.get("total_payment", 0.0) <= 0.0
            and row.mortgage.get("remaining_balance", 0.0) <= 0.0
        ):
            continue
        rows.append(
            (
                row.year,
                _ages_label(row.husband_age, row.wife_age),
                monthly_payment,
                row.mortgage.get("scheduled_payment", 0.0),
                row.mortgage.get("extra_principal", 0.0),
                row.mortgage.get("total_payment", 0.0),
                row.mortgage.get("interest", 0.0),
                row.mortgage.get("principal", 0.0),
                row.mortgage.get("remaining_balance", 0.0),
            )
        )
    return UiTableModel(columns=columns, rows=tuple(rows))


def _account_balance_tables(
    result: ProjectionResult,
    scenario: RetirementScenario,
) -> tuple[UiNamedTable, ...]:
    if not result.ledger:
        empty = UiTableModel(columns=("year",), rows=())
        return (UiNamedTable(name="All", table=empty),)

    owner_accounts: dict[str, tuple[str, ...]] = {}
    for owner_name in ("Husband", "Wife", "Household"):
        owner_accounts[owner_name] = tuple(
            account.name
            for account in scenario.accounts
            if getattr(account.owner, "value", account.owner) == owner_name
        )

    grouped_tables = [UiNamedTable(name="All", table=_account_balances_table(result, scenario))]
    for owner_name, account_names in owner_accounts.items():
        if not account_names:
            continue
        grouped_tables.append(
            UiNamedTable(
                name=owner_name,
                table=_account_balances_table(result, scenario, account_names),
            )
        )
    return tuple(grouped_tables)


def _account_balances_table(
    result: ProjectionResult,
    scenario: RetirementScenario,
    account_names: tuple[str, ...] | None = None,
) -> UiTableModel:
    if not result.ledger:
        return UiTableModel(columns=("year",), rows=())

    selected_account_names = (
        tuple(result.ledger[0].account_balances_end.keys())
        if account_names is None
        else account_names
    )
    surplus_destination = scenario.contributions.surplus_allocation.destination_account
    surplus_column = ()
    if surplus_destination in selected_account_names:
        surplus_column = (f"surplus to {surplus_destination}",)
    columns = ("year", "husband/wife ages") + surplus_column + selected_account_names
    rows = []
    for row in result.ledger:
        surplus_values = ()
        if surplus_column:
            surplus_values = (row.surplus_allocations.get(surplus_destination, 0.0),)
        rows.append(
            (row.year, _ages_label(row.husband_age, row.wife_age))
            + surplus_values
            + tuple(
                row.account_balances_end.get(account_name, 0.0)
                for account_name in selected_account_names
            )
        )
    return UiTableModel(columns=columns, rows=tuple(rows))


def _irmaa_table(result: ProjectionResult) -> UiTableModel:
    columns = ("year", "husband_age", "wife_age", "irmaa_tier", "alerts")
    rows = []
    for row in result.ledger:
        irmaa_alerts = "; ".join(alert for alert in row.alerts if "IRMAA" in alert)
        irmaa_tier = row.medicare.get("irmaa_tier", 0.0)
        if irmaa_tier <= 0 and not irmaa_alerts:
            continue
        rows.append((row.year, row.husband_age, row.wife_age, irmaa_tier, irmaa_alerts))
    return UiTableModel(columns=columns, rows=tuple(rows))


def _charts_from_reporting(charts: dict[str, Any]) -> tuple[UiChartModel, ...]:
    ordered = []
    for chart in charts.values():
        ordered.append(
            UiChartModel(
                title=chart["title"],
                kind=chart["kind"],
                series=tuple(
                    UiChartSeries(
                        name=series["name"],
                        points=tuple(
                            (int(point["year"]), float(point["value"]))
                            for point in series["points"]
                        ),
                    )
                    for series in chart["series"]
                ),
            )
        )
    return tuple(ordered)


def _format_value(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def _ages_label(husband_age: int, wife_age: int) -> str:
    return f"{husband_age} / {wife_age}"
