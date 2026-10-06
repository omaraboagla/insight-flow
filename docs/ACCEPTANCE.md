# Acceptance and evidence

Every criterion has PASS, FAIL, or NOT RUN in the final report. Mock tests establish deterministic behavior; they do not establish live Gemini accuracy, latency, or availability. Preserve every evaluated question and failure. PLAN-GOVERN reviews evidence for each gate.

| ID | Required check | Evidence required for PASS |
| --- | --- | --- |
| AC-01 | From clean venv and valid .env, `make run` serves loopback and imports every supported archive file without manual steps. | Launch command/log with secrets removed; HTTP success; independent archive/source inventory matched to UI/API tables; bind inspected. |
| AC-02 | Every sheet has correct headers/types, merged/title/blank handling, cached formula values and uncached formula warnings. | Independent pandas/openpyxl profile for all real sheets; synthetic fixtures for merged/title/blank/mixed-date/duplicate headers; assertions comparing counts, column identities, types and formula flags. |
| AC-03 | Detect actual sales/customer/product/employee, purchases/supplier/product/employee and product/supplier keys with no false links. | Independently established expected relationship set and exact-set comparison; schema-map screenshot. If workbook schema differs, document actual expected links from observed columns. |
| AC-04 | At least 40 fixed real-data questions, >=90% fully correct; temperature 0. | Golden question JSON + independent pandas expected results; live sequential eval recording question, SQL, rows, verdict, category, tokens and latency. Category table includes all failures. Mock accuracy reported separately. |
| AC-05 | 100% answer-sentence numbers are supported by returned results within documented rounding. | Verifier tests for signs, grouping commas, decimals, dates, currency, percent, scientific notation, invented numbers; fallback assertions and live answer scan. |
| AC-06 | Every computed answer cites SQL, source files/sheets, actual tables/columns and join keys. | Parser-derived citation tests; join and single-table answer screenshots with expanded citation details. |
| AC-07 | 100% direct malicious SQL blocked before execution. | AST guard corpus/fuzz cases for DDL, DML, multiple statements, COPY, ATTACH, INSTALL, LOAD, PRAGMA, SET, EXPORT, file/network scans, unknown tables/columns, CTE shadowing, unsafe joins; instrumented executor proves rejected SQL never executes; timeout/cap checks. |
| AC-08 | Injection cell content cannot alter instructions or disclose secrets. | At least three malicious cell fixtures, truncation/delimiter assertions and recorded/live behavior evidence; no test contains the real credential. |
| AC-09 | No credential in source, logs, reports, screenshots, recordings or browser payloads. | Automated exact-byte scan excluding only .env secret source, screenshot text inspection/OCR if available, browser network capture assertions; scan output names files only. |
| AC-10 | At least 80% ambiguous questions clarify; every unavailable fact is refused with no invented numbers. | Five ambiguity cases (>=4 clarify) and five unanswerable cases (5 honest refusals), reported independently of numerical accuracy; clickable chooser E2E. |
| AC-11 | >=85% multi-turn follow-ups resolve. | At least eight follow-ups (>=7 pass), including filters, date periods, sort and dimensions, independently checked; context/privacy assertions. |
| AC-12 | Live median <6 seconds and p95 <15 seconds. | Uncached live question-to-final-response timings; sample count and percentile method; per-question input/output/total token record; startup/cache latency separate. |
| AC-13 | Missing/invalid key, 429/5xx, timeout and offline never crash; designed messages and retry policy. | SDK-injected failures, max-four-attempt checks with exponential jitter, 10-second SQL interrupt, exhausted-budget test, E2E screenshots for each degraded state. |
| AC-14 | Privacy switches remove protected content from every outbound call. | Capture generate + embed payloads with unique marker values; schema-only has no sample/distinct/text-range/value/history rows; no-results omits rows and phrasing call; privacy cache partition assertions. |
| AC-15 | Runtime outbound host is Gemini only and bind is loopback. | Server socket/config assertion; intercepted backend and browser outbound requests; local assets; SDK endpoint guard and rejected custom-host test; no secrets in browser requests. |
| AC-16 | Full UI states consistent, responsive and recording-ready. | Playwright captures loading, data loaded, upload success/error, explorer, question progress, answer/table/chart/citations, clarification, map, export, privacy and degraded/empty states at desktop and 1100px; visual review and artifact paths. |

## Required test inventory

Golden coverage: totals/averages, filters, monthly/category/channel grouping, top-N, margin by category, reorder stock with supplier, pending purchases/value, supplier spend, employee sales, loyalty spend, customer/product joins, date ranges. In addition: five ambiguous, five unanswerable, five destructive, three injection, eight follow-ups. Expected figures must be computed from source workbooks independently of product modules. Messy fixtures are synthetic and do not modify originals.

Unit/CI uses recorded responses with `--mock`; live eval is explicit, sequential, cached, quota-capped and retry-aware. Cache cannot hide failures from a prior attempt. The report must distinguish model/call/provider failures from SQL/answer defects. API and browser tests must exercise session isolation, upload error isolation, sorting/search pagination, CSV, PNG/PDF, no network CDN dependency and stale cache invalidation.

## Gate checklist

Phase 1: four governance docs present; source inventory/profile; startup health/static page; real ingestion evidence; tiny live call/model list evidence (or explicit blocker). Phase 2: grounded successful query, citation/result/number verification, guard and privacy tests, initial category evaluation. Phase 3: full evidence matrix, honest live metrics, all UI artifacts, security review, final release signoff. An unfulfilled mandatory criterion prevents an unqualified release approval.
