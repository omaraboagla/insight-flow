# Build and evaluation report

## Current status

Static UI evidence: `node --check app/static/app.js` and local static-asset checks passed. Python syntax compilation of the E2E source passed; Playwright itself and a browser were unavailable. The source workbook profile and independent answer calculations are complete. The golden corpus has 61 questions, with exact, independently recomputed expected results for 43 computed-answer questions. The calculation reads original XLSX OOXML using only Python's standard library and does not import app code. No Gemini calls were sent.

The final mock harness run covered all 61 questions in a local run log, with zero Gemini calls. One question used an explicitly labeled transport-only fixture; 60 were skipped because no recorded app responses exist. This is harness coverage evidence only, not an application accuracy result. The independent expected calculator reproduced all 43 computed references. Offline fake-client checks passed for strict column-aligned grading, retry/backoff, persisted cache reuse, distinct setup/follow-up requests, and prompt-injection session isolation; direct smoke checks also confirmed exact result shape/order grading rejects reversed top-N rows and extra columns. These checks were function-level, not a pytest run. App-level 429 quota/budget failures are terminal and are not retried. Answer verifier smoke checks include scientific notation, spelled quantities, compact K/M/B/T/bn/mn/tn suffixes, negative written/Unicode-sign values, ISO/natural dates, and number-free fallback templates. Regression tests for strict order/shape, long suffixes, and negative forms are source-added but not run under pytest.

## Acceptance evidence

| AC | Status | Evidence |
|---|---|---|
| AC-01 | NOT RUN | `make run` was attempted and failed while installing FastAPI because pypi.org DNS was unavailable; server startup was not verified. |
| AC-02 | NOT RUN | Read-only profile at [profile.md](../tests/fixtures/profile.md); ingestion tests written, not executed. |
| AC-03 | NOT RUN | Relationship expectations documented and direct tests written, not executed. |
| AC-04 | NOT RUN | 61-question mock harness completed with zero Gemini calls; 60 questions had no recorded app response and were skipped. The independent expected set now includes 35 direct and 8 follow-up results. No live accuracy result. |
| AC-05 | NOT RUN | Direct verifier smoke checks passed for scientific notation, word/compact scales, ISO/natural dates, and alias-digit fallback. Full app answer path was not tested. |
| AC-06 | NOT RUN | Citation aliases are resolved per SELECT in source, but parser/runtime citation tests could not be run because sqlglot and the app dependencies are unavailable. |
| AC-07 | NOT RUN | Direct malicious SQL test cases written, not executed. |
| AC-08 | NOT RUN | Injection fixture and payload test written, not executed against Gemini. |
| AC-09 | NOT RUN | Orchestrator scanned the workspace against the `.env` key, excluding `.env`, and found zero other copies. The key was not printed. Remaining browser-network checks were not run. |
| AC-10 | NOT RUN | Ambiguity/unanswerable prompts are present; classification has not been evaluated. |
| AC-11 | NOT RUN | Eight follow-up pairs have independent expected results; fake-client checks confirmed separate setup/follow-up requests. Live app multi-turn accuracy was not evaluated. |
| AC-12 | NOT RUN | No app latency or live token measurements exist. |
| AC-13 | NOT RUN | API test stubs missing-key only; 429/timeout/offline live behavior not exercised. |
| AC-14 | NOT RUN | Privacy payload capture tests written, not executed. |
| AC-15 | NOT RUN | Network allow-list/bind behavior has not been tested. |
| AC-16 | NOT RUN | Node syntax and static-asset checks passed; Playwright E2E source covers core views and screenshot capture. Browser/dependency run was unavailable, so no screenshots were captured and visual readiness is unverified. |

## Independent source answers

Workbook-derived reference values include total sales of **$92,650.61** across **69 units**, average line total **$1,425.39**, pending purchase value **$9,902.46** across **3** orders, and total current stock **339** units. Category revenue is: Necklaces $35,412.92; Rings $29,378.61; Bracelets $11,836.50; Pendants $7,561.07; Watches $4,422.55; Earrings $4,038.96. Full expected rows are in `tests/golden/expected_results.json`.

## Accuracy by category

| Category | Questions | Evaluated | Accuracy |
|---|---:|---:|---|
| Totals, averages, group-by, top-N, margin, stock, purchases, joins, filters, products, customers, employees, loyalty | 35 | 0 | NOT MEASURED |
| Ambiguous | 5 | 0 | NOT MEASURED |
| Unanswerable | 5 | 0 | NOT MEASURED |
| Destructive | 5 | 0 | NOT MEASURED |
| Prompt injection | 3 | 0 | NOT MEASURED |
| Follow-up | 8 | 0 | NOT MEASURED |
| **Total** | **61** | **0** | **NOT MEASURED** |

The corpus currently has 61 questions, including 43 computed-answer prompts (35 direct and 8 follow-up results); 18 behavior prompts cover ambiguity, unanswerable requests, destructive requests, and injection handling.

## Latency and token usage

Not measured. No app answers or Gemini requests were recorded. The harness's default mock mode sends no requests. Live mode is explicit (`python tests/eval_harness.py --mode live`), defaults to all 61 cases, records app usage, reuses cached answers, and stops when the 200-call session/aggregate cap is reached.

## Tests and blockers

Direct tests have been added for SQL validation, ingestion, source relationships, schema privacy and outbound payload bounds, answer-number verification, executor file isolation, API health/schema/chat/preview behavior with a stubbed cloud boundary, and independent expected-result reproducibility. The eval harness now grades exact result shape, corresponding column positions and row order, persists/reuses live responses by question/schema/model/privacy signature, retries transient app failures with exponential backoff and jitter, and submits each follow-up setup then follow-up as separate requests. Each injection case uses a separate app session so fixture uploads cannot persist into later source-only cases. Error outcomes count in category accuracy denominators. Default mock mode remains quota-free; live mode defaults to all 61 cases, runs sequentially, reuses its cache, and treats 200 calls as a stop-after-response aggregate/session threshold. The eval harness includes an opt-in inherited-environment secret scan that skips `.env`, prints only matching paths, and never emits or stores the credential. A unit test exercises the scanner with a fake marker. The orchestrator's final workspace scan found zero key copies outside `.env`; the value was withheld. SQL tests additionally target optional `OR TRUE` and CASE/COALESCE join conditions, unrelated prior-table equalities, and citations limited to actual safe join keys. Privacy history checks preserve the user question while removing SQL literals and result rows. The messy XLSX fixture was generated directly as OOXML, including merged cells, title/blank rows, duplicate headers, mixed date strings, uncalculated formulas, and an untrusted injection string.

`make test` failed because pytest is absent from `.venv`; application runtime packages including pandas/openpyxl/duckdb/sqlglot are unavailable, so integration tests could not be executed. App integration/e2e tests remain blocked by unavailable runtime dependencies; the API, planner, and static frontend modules are now present, but no local app server could be started. BUILD has since added code for dropping legacy `values` from prompt cards and mapping `SoldBy`/`ApprovedBy` to `EmployeeID`; these fixes are covered by the direct tests but remain runtime-unverified.

## Screenshots

No screenshots have been captured because Playwright/browser dependencies are unavailable. The E2E source is ready to write boot, explorer, relationships, answer/export, privacy, and upload captures under `reports/screenshots/e2e/` when run.

## E2E source

`tests/e2e/test_ui.py` passes Python syntax compilation, starts a loopback static server for the actual frontend, and fulfills API calls with deterministic local fixtures. It covers initial boot, navigation, explorer preview, relationship map, example question rendering, citations, CSV/PDF export, privacy toggles and request payloads, and workbook upload. Its API route mock prevents Gemini access and quota use. This validates the UI against a mock backend; backend behavior is covered by separate API tests and has not been exercised here.
