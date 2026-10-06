# Insight Flow

**Turn scattered spreadsheets into answers people can review.**

Insight Flow is a local-first data and AI application built around a common store-operations problem: important information lives across spreadsheets, and staff spend time searching, joining, and calculating it by hand. Ask a question in plain English and get a database-calculated result with the query and source fields behind it.

> Spreadsheet files stay on your device. Calculations run locally in DuckDB. A hosted language model helps interpret the question and prepare the response; privacy controls limit the workbook details sent for that work.

## How it works

`Excel / CSV → ETL → Schema + relationships → RAG retrieval → SQL safety checks → DuckDB → Verified answer + citations`

### The data and AI approach

- **ETL:** reads Excel and CSV files, finds headers, cleans rows and columns, infers field types, and loads each worksheet as a queryable table.
- **RAG:** retrieves relevant table descriptions, relationships, categories, and candidate values to ground a question in the loaded data. It does not ask a language model to add up embedded spreadsheet rows.
- **Structured planning and tool use:** the model proposes a single SQL query. The app checks it, then invokes the local query engine. The model never directly edits a workbook or database table.
- **Verified answers:** DuckDB supplies the numbers. An answer check compares numbers in the response with the query result and uses a deterministic fallback when they do not match.
- **Reviewable output:** answers include the SQL, source tables and columns, detected join keys, assumptions, result rows, and export options.

## Built with

| Area | Technologies |
| --- | --- |
| Data ingestion | Python, pandas, openpyxl, xlrd |
| Analytical execution | DuckDB, in-memory tables, SQL |
| Retrieval | BM25, vector embeddings, NumPy |
| Query planning | Structured language-model responses, SQLGlot validation |
| Application | FastAPI, vanilla JavaScript, HTML, CSS |
| Visualization and export | Chart.js, CSV, PDF/PNG utilities |
| Quality checks | pytest, Playwright, recorded-response and independent-data evaluation harnesses |

The workflow is orchestrated directly in Python. LangGraph is not part of the current implementation.

## Run locally

**Requirements:** Python 3.11 or newer and an API key for the configured language-model service.

```bash
cp .env.example .env
# Add your key to .env, then:
make run
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The server binds to the local machine. Add workbooks in the app or place them in `data/source/`; this folder is intentionally excluded from Git. The app accepts `.xlsx`, `.xlsm`, `.xls`, and `.csv` files.

## Privacy and safety

- Source workbooks, generated datasets, credentials, logs, and local evaluation runs are excluded from this repository.
- SQL is parsed and checked before execution. Queries are restricted to loaded tables, read-only statements, and bounded results.
- The interface provides controls for reducing workbook context shared with the language-model service and for keeping result rows out of answer phrasing.
- Keep your `.env` file private. Never put an API key in source code, screenshots, issues, or commit messages.

## Learn the pipeline

[`learn.md`](learn.md) is a study guide to ingestion, schema profiling, relationship detection, retrieval, SQL planning and validation, execution, answer verification, privacy, caching, and evaluation.

## Project checks

```bash
make test
```

The live evaluation harness can make API calls. Its mock mode is designed to run without using model quota:

```bash
python tests/eval_harness.py --mode mock
```

See [`reports/BUILD_REPORT.md`](reports/BUILD_REPORT.md) for the current verification status and known limitations. Evaluation results are generated locally and are not committed.

---

Built by **Omar Aboagla** as a practical data and AI workflow for spreadsheet-heavy operations.
