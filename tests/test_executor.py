from pathlib import Path
from app.ingest import ingest_directory
from app.executor import Executor

ROOT=Path(__file__).resolve().parents[1]
def test_executor_reads_tables_and_caps_return_to_1000_rows():
    tables,errors=ingest_directory(ROOT/'data'/'source')
    assert not errors
    ex=Executor(tables)
    try:
        result=ex.execute('SELECT * FROM sales__sales LIMIT 1001')
        assert len(result['rows'])<=1000
        assert result['capped'] is True
    finally: ex.close()

def test_executor_connection_has_no_external_access():
    tables,errors=ingest_directory(ROOT/'data'/'source')
    assert not errors
    ex=Executor(tables)
    try:
        # External file/table functions must remain unavailable even if SQL guard regresses.
        try:
            ex.execute("SELECT * FROM read_csv('/etc/passwd')")
        except Exception:
            pass
        else:
            raise AssertionError('DuckDB unexpectedly read an external file')
    finally: ex.close()
