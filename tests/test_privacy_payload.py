import json
from pathlib import Path
from app.ingest import ingest_directory
from app.schema import schema_cards
from app.planner import prompt_for, safe_history
from app.answer import compose_answer

ROOT=Path(__file__).resolve().parents[1]

def test_schema_only_outbound_prompt_contains_no_samples_or_value_lists():
    tables,errors=ingest_directory(ROOT/'data'/'source')
    assert not errors
    cards=schema_cards(tables,schema_only=True)
    payload=prompt_for('summarize products',cards,[],[],[])
    for private_key in ('sample_values','distinct_values','"values"'):
        assert private_key not in payload
    # Ensure exact cell values do not sneak in via low-cardinality categorical fields.
    assert 'Classic Solitaire Engagement Ring' not in payload
    assert 'Antwerp Diamond Partners' not in payload

def test_schema_only_history_omits_result_rows_and_literal_values():
    history=[{'question':'customer C001 spent?','sql':"SELECT * FROM customers WHERE customerid='C001'",'result':{'columns':['name'],'rows':[['Liam Alvarez']],'row_count':1}}]
    payload=json.dumps(safe_history(history,True,False))
    parsed=json.loads(payload)
    assert parsed[0]['question']=='customer C001 spent?'  # User-authored question is retained.
    assert "customerid='C001'" not in parsed[0]['sql'] and '[value omitted]' in parsed[0]['sql']
    assert 'Liam Alvarez' not in payload
    assert 'rows' not in json.loads(payload)[0]['result_summary']

def test_no_result_rows_mode_uses_template_without_calling_answer_model():
    class NeverCall:
        def generate(self,*args,**kwargs): raise AssertionError('model must not receive result rows')
    result={'columns':['total'],'rows':[[123.0]],'row_count':1,'capped':False}
    answer,verified=compose_answer('total?',result,NeverCall(),None,dont_send_result_rows=True)
    assert answer=='total: 123.' and verified

def test_answer_phrase_payload_truncates_to_50_rows_and_60_char_cells():
    class Capture:
        def __init__(self): self.prompt=''
        def generate(self,prompt,usage,fast):
            self.prompt=prompt
            return 'The result is 42.'
    gemini=Capture(); rows=[[42,('X'*70 if i==0 else f'item-{i}')] for i in range(60)]
    result={'columns':['value','label'],'rows':rows,'row_count':60,'capped':False}
    answer,verified=compose_answer('question',result,gemini,None,False)
    assert verified and answer=='The result is 42.'
    data=json.loads(gemini.prompt.split('<DATA>\n',1)[1].split('\n</DATA>',1)[0])
    assert len(data['rows'])==50 and len(data['rows'][0][1])==60
