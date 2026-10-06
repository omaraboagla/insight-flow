# Sheet Agent specification

A local web application for verifiable questions over spreadsheet data. The browser talks only to the loopback FastAPI server. Gemini plans SQL from grounded schema; DuckDB computes results; every answer exposes its query and source sheets/columns. Numbers never come from language-model arithmetic.

## Delivery scope and architecture

Python 3.11+, FastAPI, DuckDB, pandas, openpyxl, xlrd for legacy Excel, sqlglot, google-genai, numpy, python-dotenv. Vanilla JavaScript UI with a dark theme, one accent, tabular numerals and responsive layout down to 1100 px. Serve CSS, charting and any export dependencies locally. `make run` creates a venv, installs requirements, loads .env, imports all discovered source files, and binds only 127.0.0.1:8000.

`ingest.py` reads cached formulas and formula metadata separately, detects headers below title/blank rows, fills merged ranges, removes empty rows/columns, handles duplicate names, infers useful types and preserves original names. Every sheet becomes a safely named table. Ingestion reports uncached formula columns rather than pretending blanks are calculated values. Original archives and source workbooks are immutable.

`schema.py` creates row count, type, null rate, ranges, sample and distinct-value cards. `relationships.py` accepts semantically matching ID names with unique referenced keys and high observed overlap. `retrieve.py` combines schema/value embeddings and BM25 when schema is large. `planner.py` assembles guarded context and structured model output. `sqlguard.py` is the mandatory boundary before `executor.py`; all query paths use it. `answer.py` verifies numeric claims or renders deterministic text. `cache.py` partitions by schema/data, model, privacy and conversation. `llm.py` owns credential loading, outbound host restriction, retries, budgets, redaction, token accounting and runtime model choice.

The UI includes uploads with per-file progress/errors, reload, schema map, table explorer with sorting/search/pagination, actual-schema question chips, chat stages, clarification choices, result sorting and automatic meaningful charts, citation expander, CSV plus PNG/PDF export, privacy toggles, call budget and persistent Cloud AI: Gemini label. Missing configuration, invalid key, offline, throttled/exhausted quota, absent model, slow response and empty-data states are designed rather than raw exceptions.

## Decisions

1. User requirement for a single outbound Gemini host takes precedence over the suggested Tailwind CDN. CSS and JavaScript assets are served locally; no external fonts, CDN, analytics or browser-to-Gemini requests. Dependency installation is a setup action, outside runtime network scope.
2. Session-local in-memory DuckDB connections prevent cross-session data/context leakage. An immutable source snapshot may initialize each session; uploads remain in the uploading session unless explicitly persisted by a documented local action.
3. A cookie identifies sessions; bind to loopback, validate Host/Origin for mutations, disable cross-origin access and use same-origin asset policy. No endpoint accepts arbitrary URLs, file paths, or client-supplied SQL for execution.
4. Literal/sample strings, formulas, column labels, user questions and model output are untrusted. Render via textContent, never innerHTML. Export filenames are sanitized. Spreadsheet CSV export should neutralize formula-leading text cells while preserving legitimate numeric values.
5. Secret-scan tests necessarily exclude the authorized .env secret source and process memory. They must scan source, reports, logs, recorded fixtures and screenshot-derived text without printing the matching value. A reported match identifies only its location, then is removed.
6. No git repository was present at handoff. Initialize only if feasible under workspace permissions; phase evidence belongs in STATUS.md regardless. Do not claim commits/tags that were not created.
7. Gemini defaults are requested configuration, not verified availability. Use official SDK model listing and one tiny generation through the app/eval boundary. Exclude every Gemini 2.5 model. Record actual fallback selection and evidence in AGENT_CONFIG.md and README.
8. Performance and accuracy targets require observed live evidence. If provider availability, quota or elapsed time prevents a criterion, mark NOT RUN or FAIL and retain the failure cases.

## Security invariants and review gates

Never inspect, echo, hard-code, transmit to the browser or include the credential in prompts. SDK obtains it from process environment loaded from .env at app startup. Disable/redact HTTP debug logs; upstream errors become fixed messages. Runtime network destination is exactly generativelanguage.googleapis.com. Use no tools or code execution capabilities in Gemini requests.

SQL is read-only by AST validation, catalog/column resolution, forbidden operation/function checks, external access disabled, bounded results and time, plus safe-join validation. Attempts at file scans, extension loading, settings, filesystem/network functions and multiple statements must fail before DuckDB execution. View/table source registration is a trusted ingestion operation, not an exposed write capability.

Phase 1 requires docs, usable launch/skeleton, real ingestion/profile, and API preflight evidence. Phase 2 requires a successful real grounded query with citations and initial security/unit tests. Phase 3 requires full test evidence, honest live eval report, screenshot artifacts, all AC reviewed, and RELEASE_SIGNOFF.md. Gates are written APPROVED or CHANGES REQUESTED only after evidence review.
