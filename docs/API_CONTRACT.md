# API contract — Sheet Agent

Version 1, 2026-10-05. This is the shared implementation and test contract. JSON keys are stable; additive metadata is permitted. All endpoints are same-origin at `http://127.0.0.1:8000`. Browser requests never contain the Gemini credential.

## Session and errors

A random opaque cookie `sheet_session` identifies an in-memory session and is HttpOnly, SameSite=Strict. The first API request creates a session. Each session owns a DuckDB connection, conversation (last three successful turns), cache, and token/call counters. Source frames may be shared read-only; queries and uploads are session-isolated. Restart discards sessions. Reload invalidates the cache and conversation.

Errors use `{"error":{"code":"string","message":"safe user-facing string","retryable":false}}`. Codes include `missing_key`, `invalid_key`, `offline`, `quota_exhausted`, `budget_exhausted`, `model_not_found`, `timeout`, `empty_data`, `invalid_file`, `unsafe_sql`, `query_failed`, `invalid_request`. HTTP 400 is invalid input, 413 oversize upload, 422 unsupported/corrupt input or unsafe SQL, 429 budget/quota, 502 unavailable upstream, 503 missing configuration/offline, 504 timeout. No raw provider exception, HTTP headers, credential, query string, or local absolute path reaches the browser.

## Endpoints

| Method and path | Input | Success body |
| --- | --- | --- |
| `GET /` | none | HTML application |
| `GET /api/health` | none | `{status, ai_status, models:{main,fast,embedding}}`; no credential |
| `GET /api/schema` | none | `{tables:[Table], relationships:[Relationship], schema_hash, examples:[string], warnings:[string], usage:Usage}` |
| `GET /api/tables/{table}/preview` | `page` default 1, `page_size` 1–100 default 25, `sort` safe column, `direction` asc/desc, `search` string | `{table, columns:[string], rows:[object], total_rows, page, page_size}` |
| `POST /api/upload` | multipart `files`, one or more supported files | `{files:[{name,status,tables:[string],error:string|null}], tables:[Table], relationships:[Relationship], schema_hash}`; individual file errors preserve other successes |
| `POST /api/reload` | empty body | same schema response, reread `data/source/` |
| `POST /api/chat` | `ChatRequest` | `ChatResponse` |
| `POST /api/chat/stream` | `ChatRequest` | SSE: `progress` events `{stage:"understanding"|"writing"|"running"|"verifying",message}` followed by one `result` containing ChatResponse or `error` using error envelope |
| `GET /api/results/{result_id}/csv` | none | `text/csv`, safe attachment filename; only own-session result, capped at 1000 query rows |

PNG export may run entirely in the browser using locally served code; PDF export may use the browser print dialog with an answer-card print stylesheet. At least one image/document export in addition to CSV must work. Do not add third-party network requests for export.

## Shapes

`Table = {name, alias, file, sheet, row_count, columns:[Column], warnings:[string]}`.
`Column = {name, original_name, type, null_pct, min, max, sample_values:[scalar], distinct_values:[scalar]|null, uncalculated:boolean}`. Samples at most five; distinct list only for at most 50 unique text values. Types: number, date, text, boolean, currency, percent. Names are safe SQL identifiers; file/sheet/original_name are display citations. JSON dates are ISO strings and nonfinite numbers become null.

`Relationship = {from_table, from_column, to_table, to_column, overlap, confidence}`. `to_column` must be unique among nonnull values, identifiers must be semantically compatible, and value overlap must be high. A coincidental equal-sized numeric sequence is not enough.

`Usage = {calls, max_calls, remaining_calls, input_tokens, output_tokens, total_tokens}`. Every actual network attempt, including retries and embeddings, consumes a call. Defaults: `MAX_CALLS_PER_SESSION=200`; four attempts maximum for 429/5xx with exponential backoff and jitter. Local cache hits consume no call.

`ChatRequest = {question:string, schema_only:boolean=false, dont_send_result_rows:boolean=false}`. Reject empty or excessive-length questions. Follow-up history comes from the session, never arbitrary client SQL. A clarification click submits the original question plus the selected option as another ordinary question.

`ChatResponse = {status:"answer"|"clarification"|"unanswerable"|"refused", answer:string, needs_clarification:Clarification|null, result_id:string|null, columns:[string], rows:[object], total_rows:number, truncated:boolean, sql:string, tables_used:[string], columns_used:[string], assumptions:[string], join_keys:[string], sources:[{file,sheet,table,columns:[string]}], chart:object|null, verified:boolean, source:"computed"|null, model:string, tokens:{input,output,total}, latency_ms:number, cached:boolean, usage:Usage}`.

`Clarification = {question:string, options:[string]}` with 2–6 actionable options. Answer rows contain up to 1000 rows; browser shows at most 200 and labels truncation. `total_rows` is the count returned by the capped SQL, not an invented uncapped count. Chart metadata references result columns; no model-generated numbers. Citation fields are derived or validated against parsed SQL, never trusted merely because the model listed them.

## Gemini main-call schema

All fields are required. Null clarification means no clarification. If clarification is present or answerable is false, SQL must be empty and is never executed.

```json
{
  "type": "object",
  "properties": {
    "needs_clarification": {
      "anyOf": [
        {"type":"null"},
        {"type":"object","properties":{"question":{"type":"string"},"options":{"type":"array","items":{"type":"string"}}},"required":["question","options"],"additionalProperties":false}
      ]
    },
    "sql": {"type":"string"},
    "tables_used": {"type":"array","items":{"type":"string"}},
    "columns_used": {"type":"array","items":{"type":"string"}},
    "assumptions": {"type":"array","items":{"type":"string"}},
    "answerable": {"type":"boolean"},
    "reason_if_unanswerable": {"type":"string"}
  },
  "required":["needs_clarification","sql","tables_used","columns_used","assumptions","answerable","reason_if_unanswerable"],
  "additionalProperties":false
}
```

## Prompt, retrieval, privacy, and computation

Main model temperature is zero. Include today's date, schema cards, detected join hints, and 4–6 generated examples using actual table/column names. Instructions demand one SELECT (CTEs allowed), quoted identifiers, explicit safe joins, and LIMIT no greater than 1000. Ask rather than guess if metric, column, date period, or join is ambiguous. Unsupported facts return answerable=false with closest columns. Refuse destructive requests before any model call.

Use all cards below approximately 60 columns. Otherwise combine BM25 and embedding similarity to retrieve relevant cards and connecting tables. Embed high-cardinality name values to resolve fuzzy mentions. Distinct/sample values are 60 characters maximum and live in a delimited block preceded by a fixed instruction that its contents are untrusted data, never instructions. Do not put credentials into prompts, model-visible errors, or histories.

Schema-only mode strips samples, distinct values, textual min/max, retrieved value matches, and row-valued conversation summaries from every outbound prompt and embedding input. User-authored question text, including values the user typed, remains in the question and prior-question context; schema-only mode does not redact the user’s own instructions. String literals in prior SQL are replaced by an omission marker. Numeric/date schema aggregates may remain. Turning it on must not reuse an answer cached under weaker privacy settings. No-result-rows mode skips model answer phrasing and omits result rows from history/rewrite prompts; compose locally. Cache identity includes question, schema/data hash, model, both privacy toggles, and conversation context.

Normal answer phrasing sends no more than 50 result rows, with cell values truncated. A deterministic verifier accepts numbers only when represented in query results within supported rounding; otherwise use a deterministic result-based sentence. Do not let a model's arithmetic or extra narrative statistics reach the user.

Last three turns supply question, validated SQL, and bounded privacy-aware summary. A fast-model rewrite resolves genuine follow-ups. SQL gets at most two repair attempts after the initial attempt, with sanitized validator/executor feedback.

Before execution: sqlglot DuckDB parsing accepts exactly one SELECT, validates all physical tables and columns including CTE scopes, disallows DDL/DML and unsafe functions, enforces result LIMIT, and checks joins against approved relationships or explicitly stated safe keys. DuckDB external access is disabled and execution interrupts after 10 seconds. The app provides no SQL write endpoint.
