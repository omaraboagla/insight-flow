from pathlib import Path
from app.ingest import ingest_directory
from app.schema import schema_cards

ROOT=Path(__file__).resolve().parents[1]
def test_schema_only_cards_omit_all_samples_and_distinct_values():
    tables,errors=ingest_directory(ROOT/'data'/'source')
    assert not errors
    cards=schema_cards(tables,schema_only=True)
    for table in cards:
        for col in table['columns']:
            assert 'sample_values' not in col
            assert 'distinct_values' not in col
            assert 'values' not in col

def test_normal_cards_bound_sample_and_distinct_strings():
    tables,errors=ingest_directory(ROOT/'data'/'source')
    assert not errors
    for table in schema_cards(tables):
        for col in table['columns']:
            assert len(col.get('sample_values',[]))<=5
            assert len(col.get('distinct_values',[]))<=50
            assert 'values' not in col
            assert all(not isinstance(v,str) or len(v)<=60 for v in col.get('sample_values',[])+col.get('distinct_values',[]))
