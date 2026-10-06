from pathlib import Path
from app.ingest import ingest_directory
from app.relationships import detect_relationships

ROOT=Path(__file__).resolve().parents[1]
def test_expected_jewelry_foreign_keys_are_detected_without_spurious_links():
    tables,errors=ingest_directory(ROOT/'data'/'source')
    assert not errors
    links=detect_relationships(tables)
    actual={(x['from_table'].split('__')[0],x['from_column'],x['to_table'].split('__')[0],x['to_column']) for x in links}
    expected={
      ('sales','customerid','customers','customerid'),
      ('sales','sku','products','sku'),
      ('sales','soldby','employees','employeeid'),
      ('purchases','supplierid','suppliers','supplierid'),
      ('purchases','sku','products','sku'),
      ('purchases','approvedby','employees','employeeid'),
      ('products','supplierid','suppliers','supplierid'),
    }
    # Normalize column names and orientation while requiring every expected relation.
    norm={(a,ac.lower(),b,bc.lower()) for a,ac,b,bc in actual}
    assert expected <= norm
    # No transaction-to-transaction many-to-many links and no same-value false positives.
    assert all(x['from_table'].split('__')[0] not in {'purchases','sales'} or x['to_table'].split('__')[0] not in {'purchases','sales'} for x in links)
    assert all(x['confidence'] >= .95 for x in links)
