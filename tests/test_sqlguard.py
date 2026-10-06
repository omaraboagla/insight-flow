import pytest
from app.ingest import ingest_directory
from app.sqlguard import SQLValidationError, validate_sql

TABLES, ERRORS = ingest_directory(__import__('pathlib').Path(__file__).resolve().parents[1] / 'data' / 'source')
assert not ERRORS
REL = None

@pytest.mark.parametrize('sql', [
    'DROP TABLE sales__sales',
    'DELETE FROM sales__sales',
    'UPDATE sales__sales SET quantity=0',
    'CREATE TABLE x AS SELECT 1',
    'COPY sales__sales TO \'/tmp/x.csv\'',
    'ATTACH \'/tmp/other.db\' AS other',
    'INSTALL httpfs',
    'LOAD httpfs',
    'PRAGMA version',
    'SET enable_external_access=true',
    'EXPORT DATABASE \'/tmp/export\'',
    'SELECT 1; SELECT 2',
    "SELECT * FROM read_csv('/etc/passwd')",
    "SELECT * FROM read_parquet('x.parquet')",
    "SELECT glob('*')",
    "SELECT http_get('https://example.com')",
    'SELECT * FROM unknown_table',
])
def test_unsafe_or_unloaded_sql_is_rejected(sql):
    with pytest.raises(SQLValidationError): validate_sql(sql, TABLES)


def test_single_select_with_cte_is_accepted_and_gets_safe_limit():
    name=next(iter(TABLES))
    query=validate_sql(f'WITH q AS (SELECT * FROM "{name}") SELECT * FROM q',TABLES)
    assert 'LIMIT 1000' in query.upper()


def test_limit_is_capped_and_negative_limit_rejected():
    name=next(iter(TABLES))
    query=validate_sql(f'SELECT * FROM "{name}" LIMIT 5000',TABLES)
    assert 'LIMIT 1000' in query.upper()
    with pytest.raises(SQLValidationError): validate_sql(f'SELECT * FROM "{name}" LIMIT -1',TABLES)


def test_unknown_and_ambiguous_columns_are_rejected():
    name=next(iter(TABLES))
    with pytest.raises(SQLValidationError): validate_sql(f'SELECT nonexistent FROM "{name}"',TABLES)


def test_join_requires_and_accepts_detected_keys():
    from app.relationships import detect_relationships
    rel=detect_relationships(TABLES)
    source='sales__sales'; target='products__products'
    safe=f'SELECT s.sku FROM "{source}" AS s JOIN "{target}" AS p ON s.sku=p.sku LIMIT 5'
    # Relationship links are available from the loaded source workbooks.
    assert 'LIMIT 5' in validate_sql(safe,TABLES,rel).upper()
    unsafe=f'SELECT s.sku FROM "{source}" AS s JOIN "{target}" AS p ON s.quantity=p.stockqty LIMIT 5'
    with pytest.raises(SQLValidationError): validate_sql(unsafe,TABLES,rel)


def test_join_key_cannot_be_optional_through_or_true():
    from app.relationships import detect_relationships
    rel=detect_relationships(TABLES)
    sql='SELECT s.sku FROM sales__sales AS s JOIN products__products AS p ON s.sku=p.sku OR TRUE LIMIT 5'
    with pytest.raises(SQLValidationError):validate_sql(sql,TABLES,rel)


def test_equality_between_prior_tables_cannot_authorize_new_join_target():
    from app.relationships import detect_relationships
    rel=detect_relationships(TABLES)
    sql=('SELECT s.sku FROM sales__sales AS s '
         'JOIN products__products AS p ON s.sku=p.sku '
         'JOIN customers__customers AS c ON s.sku=p.sku LIMIT 5')
    with pytest.raises(SQLValidationError):validate_sql(sql,TABLES,rel)


def test_citations_include_only_join_keys_actually_enforced():
    from app.relationships import detect_relationships
    from app.sqlguard import citations
    rel=detect_relationships(TABLES)
    sql=('SELECT s.sku,c.customerid FROM sales__sales AS s '
         'JOIN products__products AS p ON s.sku=p.sku '
         'JOIN customers__customers AS c ON s.customerid=c.customerid LIMIT 5')
    _,_,used=citations(sql,TABLES,rel)
    keys={(r['from_table'],r['from_column'],r['to_table'],r['to_column']) for r in used}
    assert keys=={
      ('sales__sales','sku','products__products','sku'),
      ('sales__sales','customerid','customers__customers','customerid'),
    }
    assert not any('employees__employees' in pair for key in keys for pair in key)
