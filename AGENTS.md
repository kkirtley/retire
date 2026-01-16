You are an expert Python engineer building a LOCAL-FIRST desktop retirement planning application for a specific household. You MUST follow these instructions exactly. Deliver working code in small increments with tests. Do not invent requirements or silently change assumptions.

PRIMARY GOAL
Build a deterministic (non-Monte-Carlo in v1) retirement projection engine and desktop UI that models a veteran household with VA income, Social Security, Medicare premiums + IRMAA, mortgage amortization + early payoff, taxes (federal bracket-based + Missouri effective rate), account-level balances (Roth/Traditional/HSA), Roth conversions, RMDs, death/survivor transitions, and scenario overrides. Success criterion: “never run out of resources before age 100.”

NON-FUNCTIONAL REQUIREMENTS
- Local-first: runs fully offline for calculations. No external account integrations.
- Network calls: ONLY allowed for developer tooling (e.g., dependency install) and optional future updates; NOT allowed for pulling user financial data. App must function without network.
- Logging: do not log PII. Use generic labels “Husband” and “Wife” only. No names, SSNs, account numbers.
- Testing: pytest from day one. Build calculation core with deterministic golden tests.
- Packaging: runnable from source; also support packaging to Windows via PyInstaller.
- Code quality: type hints, black/ruff, clear module boundaries, docstrings for formulas.
- Deterministic v1: no Monte Carlo. Design extension points for Monte Carlo later.

TARGET PLATFORM
- Python 3.12+
- Desktop UI: PySide6 (Qt). However: DO NOT start UI until core engine + tests are complete.

HIGH-LEVEL BUILD STAGES (MUST FOLLOW)
Stage 0: Repo scaffolding and CI-ready tooling
Stage 1: Data model + YAML scenario loader + validation
Stage 2: Deterministic projection engine (annual) with tests
Stage 3: Taxes: federal bracket-based + Missouri effective rate with tests
Stage 4: Mortgage amortization + payoff-by-age-65 rule + property tax/insurance expense lines
Stage 5: Social Security + VA + survivor transitions + COLA rules
Stage 6: Medicare premiums + IRMAA thresholds + tests
Stage 7: Withdrawal strategy + Roth conversions + RMDs + tests
Stage 8: Reporting outputs (tables + charts export) from engine (no GUI yet)
Stage 9: Build PySide6 UI on top of stable engine; store scenarios in YAML v1 and add SQLite persistence v2

DATA INPUTS AND STORAGE
- v1 scenarios stored as YAML files in /scenarios.
- Scenario versioning: automatically include semantic versions in YAML metadata (e.g., baseline_v1.0.0). Provide a CLI helper to bump versions.
- Later (v2): store scenarios and runs in SQLite; keep YAML import/export.

CORE OUTPUTS REQUIRED (v1)
1) Year-by-year ledger from current year through age 100 for both spouses:
   - Ages, filing status, alive flags
   - All income sources (VA, SS, earned income if any)
   - Medicare premiums and medical OOP
   - Taxes (federal + MO)
   - Expenses (base + travel + property tax + insurance + other)
   - Mortgage payments/interest/principal + remaining balance
   - Roth conversions and taxes attributable
   - RMDs and taxable distributions
   - Net cash flow surplus/deficit
   - Account balances end-of-year by account
2) Success flag per year; “failure year” if any account resources exhausted.
3) Charts (engine-level):
   - Total liquid net worth over time
   - Income vs expenses over time
   - Taxes over time
   - Account balances stacked area

IMPORTANT HOUSEHOLD BASELINE ASSUMPTIONS (DEFAULT SCENARIO)
Use these as default YAML baseline values (editable):
- Ages today: Husband 58, Wife 58
- Retirement ages: Husband 67, Wife 67 (independent retirement ages supported)
- Model horizon: through age 100 for Wife; Husband death modeled explicitly as scenario input
- Success definition: never run out of liquid resources before Wife age 100

INCOME
VA Disability (Husband):
- Monthly: $4,158.00 (non-taxable)
- COLA: 2.50% annually (apply at start of each year for simplicity)
- Stops at Husband death year (no VA after death)
- Survivor benefit to Wife: begins only if Husband death occurs after February 2035.
  Implement as an input income stream “VA_Survivor” with configurable start condition:
  - if death_date >= 2035-02-01, enable survivor VA benefit; else $0.
  Amount: parameterized in YAML (default placeholder $0.00 unless provided later).
  (Do not guess the benefit amount.)

Social Security (both claim at 67 by default):
- Husband SS at 67: $3,700.00/month (YAML input, allow override)
- Wife SS at 67: $1,500.00/month (YAML input, allow override)
- SS COLA: use a configurable long-run average default 2.00% annually (YAML input)
- Survivor rule: upon Husband death, Wife benefit steps up to the higher of her own or Husband’s (standard survivor logic). Model this explicitly.

EARNED INCOME
- Default: none post-retirement.
- Pre-retirement earnings may be added later; structure supports earned income schedules.

ACCOUNTS (START BALANCES; editable)
- Roth IRA (Husband): $300,000.00
- Traditional IRA (Husband): $373,000.00
- HSA (Household): $9,000.00 (assume investable)
- Wife Traditional IRA: $20,000.00
- Wife Roth 401k: $760.00
- Add placeholders for additional accounts; design accounts as list objects.

INVESTMENT RETURNS (Deterministic)
- Default annual return for all accounts: 5.00% nominal (YAML input, per-account override allowed).
- Inflation baseline: 2.50% (YAML input).
- Apply returns end-of-year to average balance or end balance consistently; document your convention and keep it consistent in tests.

EXPENSES
- Base living expenses: $10,000.00/month in today’s dollars (annualize to $120,000.00)
- Travel: $5,000.00/year
- Inflate expenses by CPI (default 2.50%) annually.
- Property tax and homeowners insurance are separate expense lines (see mortgage section).

MORTGAGE + HOME COSTS
- Mortgage balance: $450,000.00
- Interest rate: 5.50% fixed
- Term remaining: 15 years
- HARD REQUIREMENT: mortgage must be paid off by Husband age 65 (even though retire at 67).
  Implement an “extra principal payment” solver that computes required extra annual payment (or additional monthly equivalent aggregated annually) to achieve payoff by target age.
- Property tax: YAML input (default placeholder $0.00 unless provided later)
- Homeowners insurance: YAML input (default placeholder $0.00 unless provided later)

TAXES
Federal:
- Bracket-based approximation for MFJ and Single.
- Use a configurable bracket table in YAML (do not hardcode a single tax year).
- Include standard deduction (configurable).
- Taxable income includes: SS taxable portion approximation, Traditional distributions, Roth conversions, RMDs, interest/dividends if later modeled.
- VA is non-taxable and must not enter taxable income.
Missouri:
- Use an effective flat rate input (e.g., 4.00% default placeholder) applied to MO taxable income proxy.
- Make this explicit and configurable; don’t attempt perfect MO law modeling in v1.

MEDICARE + IRMAA
- Medicare starts at age 65 for each spouse.
- Model Part B + Part D base premiums as YAML inputs (default current-year placeholders; do not fetch from web).
- Model IRMAA using configurable thresholds and premium surcharges (YAML tables).
- IRMAA is based on MAGI from two years prior; implement the 2-year lookback rule.
- Include flags/warnings when IRMAA tier changes due to Roth conversions and other income.

RMDs
- Implement RMDs starting at a configurable age (default 75, YAML input).
- Use a configurable Uniform Lifetime Table factor table (YAML).
- Apply RMDs to Traditional accounts only.

WITHDRAWAL ORDER + FUNDING LOGIC
- Preferred withdrawal order is an input list in YAML. Implement default:
  1) Taxable (if any)
  2) Traditional (subject to taxes and RMD)
  3) Roth
  4) HSA (only for qualified medical expenses unless user chooses otherwise; in v1 treat HSA withdrawals as allowed for medical line items; keep it configurable)
- If annual cashflow is negative, withdraw in order to cover deficit.
- If annual cashflow positive, allocate surplus according to a contribution/savings policy (v1 can park surplus in a “cash” taxable bucket).

ROTH CONVERSIONS (IN SCOPE v1)
- Implement annual Roth conversion amounts as a schedule (YAML list by year or by age).
- Conversions move money from Traditional to Roth and create taxable ordinary income.
- Provide a helper mode: “convert up to top of bracket X” (YAML: max_marginal_bracket), using federal brackets.
- Ensure conversions interact with IRMAA (MAGI) and SS taxation.

DEATH / SURVIVOR MODELING
- Husband death modeled explicitly as a scenario input (year or exact date). Wife continues to age 100.
- After husband death:
  - Filing status becomes Single (starting the year after death unless user selects otherwise; make rule explicit).
  - Expenses may drop by configurable percentage (YAML input, default 70%).
  - VA stops; SS survivor step-up applies; VA survivor benefit conditional after Feb 2035 as described.

SCENARIOS
Provide at least:
- baseline_v1.0.0.yaml
- “high_inflation_3yrs” scenario override
- “market_downturn_2yrs” deterministic stress scenario (negative return years)

CLI TOOLS (v1)
- `retireplan validate scenarios/baseline.yaml`
- `retireplan run scenarios/baseline.yaml --out results/baseline_run.json --charts results/`
- `retireplan bump-version scenarios/baseline.yaml --patch` (or minor/major)

TESTING REQUIREMENTS (MUST IMPLEMENT)
- Unit tests for:
  - YAML validation + defaults
  - Mortgage amortization math and payoff-by-age-65 solver
  - SS COLA compounding and survivor step-up
  - VA COLA compounding + stop at death + survivor conditional trigger
  - Federal tax bracket computations + standard deduction
  - IRMAA lookback logic + tier transitions
  - RMD calculation against factor table
  - Roth conversion transfers and tax impact
- Golden test:
  - For baseline scenario, assert key outputs at select ages/years (e.g., balances at 67, 75, 100; taxes at 67; mortgage payoff year).
- Use $ formatting only in presentation; internal floats/Decimal recommended. For deterministic finance math, prefer Decimal where feasible.

UI REQUIREMENTS (Stage 9+)
- PySide6 desktop app
- Tabs:
  - Inputs (view/edit scenario)
  - Results table
  - Charts
  - Roth conversion planner
  - IRMAA warnings
  - Scenario compare (baseline vs stress)
- UI must call the engine as a library; no duplicated business logic.
- v2 persistence: store scenarios and runs in SQLite; support YAML import/export.

DELIVERABLE STRUCTURE (EXPECTED REPO LAYOUT)
- /retireplan/ (python package)
  - /core/ (engine)
  - /tax/
  - /medicare/
  - /mortgage/
  - /io/ (yaml/json)
  - /cli/
  - /ui/ (added later)
- /scenarios/
- /tests/
- pyproject.toml with dependencies + tooling

IMPORTANT CONSTRAINTS
- Do not implement Monte Carlo in v1.
- Do not hardcode tax-year values; put tables in YAML with defaults.
- Do not guess missing amounts (property tax, insurance, VA survivor amount). Use explicit placeholders and require YAML inputs.
- Document every major formula and convention in code comments/docstrings.

FIRST TASK
Implement Stage 0–2 only:
1) Scaffold project with pyproject.toml, ruff, black, mypy (optional), pytest.
2) Define YAML schema and loader with pydantic (preferred) or dataclasses + validation.
3) Implement deterministic annual projection engine with:
   - incomes (VA + SS only)
   - expenses (base + travel)
   - investment returns (simple)
   - withdrawal order (Traditional then Roth for now)
   - record ledger rows
4) Write tests that pass.

After Stage 0–2 pass, proceed to Stage 3 (tax) and onward in order. Always keep the app runnable and tests green.

If any requirement conflicts, STOP and surface the conflict rather than guessing.
