# Release signoff

**Decision: NOT APPROVED**

Review date: 2026-10-05. Reviewer: PLAN-GOVERN (gpt-6-astra, high reasoning). Scope: repository artifacts, STATUS.md, reports/BUILD_REPORT.md, API contract, and static review of ingestion/schema/retrieval/planner/SQL guard/execution/cloud boundary/server/browser implementation and test sources. The reviewer did not inspect .env or access the API credential. This document does not certify application execution.

## Phase gates

| Gate | Decision | Evidence and outstanding requirement |
| --- | --- | --- |
| Phase 1 — specification and skeleton | **CHANGES REQUESTED** | Governance docs, launcher, six-workbook profile and application skeleton exist. `make run` failed during dependency installation; startup and ingestion were not exercised. Official SDK model listing and tiny API call were not run. |
| Phase 2 — core grounded flow | **CHANGES REQUESTED** | Grounding, structured plans, SQL guard, execution, verifier, UI and tests are present as source. There is no successful real question-to-answer trace or passing pytest evidence. The reported direct join bypasses now have source fixes; no executed SQL-guard evidence exists. Remaining verification/evaluation limitations are below. |
| Phase 3 — hardening and report | **CHANGES REQUESTED** | Privacy, context, export and degraded-state code exist. No full suite, live accuracy/latency evaluation, browser screenshots, or network capture is available. Mandatory acceptance criteria remain unverified. |

## Evidence that exists

STATUS.md records passing Python compilation, Node syntax checking, independent calculation of 43 expected answers (35 direct and eight follow-up results), a mock harness run over 61 question records, and a workspace secret-value scan finding zero copies outside its authorized .env source. These checks are useful but do not establish application correctness. Most mock question records are skipped because no recorded model answer exists; a completed harness run must not be called 61 successful answers.

Source profiling and expected-result calculation read workbook OOXML independently of product code. The corpus contains 35 computed-answer cases, five ambiguity cases, five unavailable-fact cases, five destructive requests, three injection cases and eight follow-up entries. The latest report records offline fake-client checks for grading/retries/cache/follow-up/isolation, direct verifier smoke checks, and a mock harness artifact with one transport fixture and 60 skips. These checks do not invoke the actual server or Gemini. No live case has an observed correctness verdict. No uncached median/p95 response timings or live token measurements exist. Zero Gemini calls are reported.

The updated report now includes the orchestrator’s exact-byte workspace scan. That scan improves source/log/report evidence, but browser payloads and screenshots still have no runtime capture. AC-09 therefore remains NOT RUN for complete acceptance. Screenshot images also require image text inspection; a byte scan alone does not detect a rendered credential.

## Why runtime evidence is blocked

The available Python environments lack required runtime/test packages, including google-genai, FastAPI, DuckDB, pandas, openpyxl, sqlglot and pytest. `make run` attempted installation and failed because the execution sandbox cannot resolve `pypi.org`. `make test` failed because pytest is absent. Playwright/browser dependencies are unavailable. This blocks server startup, automated integration/E2E tests, screenshots, the authenticated model inventory, the tiny Gemini call and live evaluation. Public model documentation confirms published IDs only, not account access. No fallback model has been exercised and no runtime Gemini model has been successfully used in this environment.

Dependency/network access must become available, followed by execution of the recorded checks. This is not evidence that the Gemini API itself is offline or that the user's key is invalid.

## Acceptance audit

| AC | Audit status | Remaining evidence or correction |
| --- | --- | --- |
| AC-01 | NOT RUN | Successful clean launch, loopback HTTP request and archive-to-table inventory. |
| AC-02 | NOT RUN | Real and messy-fixture ingestion tests; header/type/formula comparisons. |
| AC-03 | NOT RUN | Exact expected relationships and rendered map comparison. |
| AC-04 | NOT RUN | At least 40-question live evaluation with >=90% correctness, independent result comparisons and category metrics. Harness now grades, but grading completeness and live execution remain unverified. |
| AC-05 | NOT RUN | Scientific/word/compact/date/sign and template fixes are present; existing smoke evidence covers selected formats, while the full verifier corpus and answer path remain unverified. |
| AC-06 | NOT RUN | Predicate-based join citations and per-SELECT source alias resolution are implemented; parser-backed source/column/CTE citation tests remain unavailable. |
| AC-07 | NOT RUN | OR/irrelevant-target/CASE/COALESCE bypasses have conservative source fixes; run the complete guard/timeout/cap corpus. |
| AC-08 | NOT RUN | Actual injection behavior evidence in addition to prompt delimiter/truncation source. |
| AC-09 | NOT RUN (partial scan evidence) | Full automated suite plus browser payload capture and screenshot inspection; retain zero-copy workspace scan evidence. |
| AC-10 | NOT RUN | >=4/5 ambiguous cases clarify and all five unavailable facts refuse honestly. |
| AC-11 | NOT RUN | Actually submit eight follow-up messages after their setup turns; >=7/8 correct. |
| AC-12 | NOT RUN | Uncached live timings/tokens, median <6s and p95 <15s. |
| AC-13 | NOT RUN | Runtime simulations for invalid/missing key, throttling, timeout, offline, budgets and retry bounds. |
| AC-14 | NOT RUN | Capture every generation/embedding payload; history-marker test is aligned in source, not executed. |
| AC-15 | NOT RUN | Runtime backend/browser host capture and loopback binding evidence. |
| AC-16 | NOT RUN | Browser run, actual screenshots, responsive/visual review and export verification. |

## Final focused static review of hardening

This section supersedes the initial and intermediate static findings. Review reflects the current files and latest BUILD_REPORT.md. Runtime execution remains unavailable; a source fix or direct smoke check does not establish complete AC compliance.

| Finding | Current evidence/status |
| --- | --- |
| Optional OR/NOT, CASE/COALESCE and unrelated-target join predicates | Addressed in source. `_joined_relationships()` unwraps parentheses/AND and requires every leaf to be a plain column equality connecting the newly introduced alias through a detected relationship. It no longer searches arbitrary expression descendants. Guard tests are present but not executed. |
| Join citations listed unused detected relationships | Addressed in source: citations now use actual accepted predicates, and column aliases resolve within each SELECT's direct source scope. Parser-backed nested/CTE citation tests still need execution. |
| Scientific notation, common spelled quantities, compact K/M/B/T and bn/mn/tn, date claims, signed quantities | Parsing and date-to-result comparison are implemented. The earlier `2bn` and “negative one” findings are addressed in source; ordinary unicode-minus numeric tokens are normalized. Direct verifier smoke checks are recorded in BUILD_REPORT.md; the full supported-format/sign combinations and app path still require execution. |
| Unverified alias numbers in templates; contradictory fallback test | Templates now verify and fall back to a number-free sentence. The test correctly rejects the raw alias-bearing template and accepts the fallback. |
| Privacy history marker mismatch | Source/test aligned: user-authored question literals remain; prior SQL string literals and result rows are omitted. API_CONTRACT.md documents this policy. Runtime outbound capture is still absent. |
| Missing eval grading/cache/retries/follow-up submission | Implemented. Eight follow-up results are independently computed; cases submit setup and follow-up separately. Default corpus is 61, with 43 computed expected results. Fake-client checks are reported. |
| Cross-column matching, ERROR exclusion, injection upload contamination | Exact row/column shape and ordering are compared, ERROR contributes to accuracy, injection uses separate sessions, and cached historical usage adds no new calls. Function-level smoke checks are reported; pytest remains unavailable. Remaining behavioral-grade limitations are below. |

### Remaining limitations requiring evidence or correction

1. **Behavioral grades are partial checks.** Unanswerable and injection grades primarily inspect status/verified/SQL prefix. They do not independently prove absent invented numbers, exposure, or behavioral effect of injection. Preserve independent checks and human evidence alongside those status grades rather than interpreting them as complete AC-08/AC-10 success.
2. **Aggregate eval budget can overshoot.** The harness tracks calls across isolated sessions and recovers failed-request usage, but a multi-call app request or follow-up pair can cross the aggregate eval cap before its usage is reported. Individual app sessions still enforce their configured call limit. Treat the eval aggregate cap as a stop-after-response threshold, not a strict provider-call ceiling.
3. **Broader runtime checks remain necessary.** SDK request-hook compatibility, external-access-disabled dataframe registration, SQL timeout/cancellation, session cleanup, unsafe SQL coverage, CSP behavior, upload replacement and chart/export rendering are source-reviewed only. The frontend uses custom SVG charts rather than the requested Chart.js; this stack deviation has no browser evidence. Conservative SQL join rules also refuse derived-table/CTE joins without trusted lineage, which may reduce live accuracy.

The evaluator now compares exact result shape, column position, and row order. SQL column citation aliases are resolved within each SELECT's direct source scope; nested/CTE citation behavior still needs a runnable parser test.

Positive source-level controls include fixed loopback launch binding, local assets and restrictive CSP, same-origin mutation checks, HttpOnly/SameSite cookies, sanitized provider errors, suppressed HTTP debug logging, a Gemini HTTPS host hook with redirects/proxies disabled, bounded upload/archive sizes, session-local query connections, disabled DuckDB external access, model-produced SQL validation before execution, result caps/timeouts, bounded cell/result prompting, no-results template composition, and privacy/context-sensitive cache keys. Their presence is not a passing security test.

## Required next gate review

Install dependencies through an available permitted network; run the full offline suite and browser cases; perform authenticated model discovery/tiny generation; complete and run the independent live eval; capture screenshots and runtime network evidence; update BUILD_REPORT.md with actual results. Until that evidence exists, deliver this workspace as an implementation awaiting validation, not a complete verified application.
