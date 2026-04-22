# Execution Order Contract

The deterministic annual engine must execute each yearly period in this order:

1. Build timeline
2. Apply proration
3. Compute income
4. Compute expenses
5. Apply contributions
6. Execute strategy
7. Compute taxes
8. Settle surplus/deficit
9. Apply returns
10. Write ledger

## Runtime Mapping

- Timeline construction happens once at the start of `project_scenario`.
- Proration is applied from the timeline-derived period fraction and date-overlap helpers before income, expenses, and contributions are evaluated for the year.
- Expenses are built before contributions and strategy execution. Medicare and charitable-giving cashflow are then iterated consistently around taxes and settlement without changing the phase order.
- Tax computation and surplus/deficit settlement are separate runtime phases, even though they may iterate to a stable yearly result.
- Account returns are applied only after the year has been fully settled.
- Ledger rows are written last from the settled year-end state.

## Notes

- Retirement account rollovers are treated as part of the strategy phase for ordering purposes because they are deterministic year actions that affect post-contribution balances before taxes, withdrawals, and returns.
- If execution order and implementation convenience conflict, the execution order contract wins.