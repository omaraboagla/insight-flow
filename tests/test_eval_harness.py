import importlib.util, json
import pytest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('eval_harness',ROOT/'tests'/'eval_harness.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
ITEMS={item['id']:item for item in h.QUESTIONS}

def response(status,**extra):return {'status':status,**extra}

def test_harness_computes_expected_values_for_all_follow_up_turns():
    assert all(f'f{i:02d}' in h.EXPECTED for i in range(1,9))
    assert h.EXPECTED['f01']=={'revenue':24656.11}
    assert h.EXPECTED['f03']=={'revenue':24994.62}
    assert h.EXPECTED['f04']['rows'][:1]==[['Cuban Link Chain 20in',11430.65]]
    assert len(h.EXPECTED['f05']['rows'])==9
    assert h.EXPECTED['f06']['rows'][0][0]=='VIP'
    assert len(h.EXPECTED['f07']['rows'])==6
    assert len(h.EXPECTED['f08']['rows'])==5

def test_harness_grades_ambiguity_unanswerable_refusal_and_injection_statuses():
    assert h.grade_response(ITEMS['a01'],response('clarification'))[0]
    assert h.grade_response(ITEMS['u01'],response('unanswerable'))[0]
    assert h.grade_response(ITEMS['d01'],response('refused'))[0]
    assert h.grade_response(ITEMS['i01'],response('answer',verified=True,sql='SELECT 1'))[0]
    assert not h.grade_response(ITEMS['i01'],response('answer',verified=False,sql='DROP TABLE x'))[0]

def test_harness_grades_independent_numeric_results():
    item=ITEMS['g01']; expected=item['expected_result']
    good=response('answer',columns=['revenue','units'],rows=[{'revenue':92650.61,'units':69}])
    bad=response('answer',columns=['revenue','units'],rows=[{'revenue':1,'units':69}])
    assert h.grade_response(item,good,expected)[0]
    assert not h.grade_response(item,bad,expected)[0]

def test_response_cache_key_changes_with_question_schema_or_model():
    item=ITEMS['f01'];a=h.signature(item,'schema-a',{'main':'m1'});b=h.signature(item,'schema-b',{'main':'m1'});c=h.signature(item,'schema-a',{'main':'m2'})
    assert len({a,b,c})==3

def test_result_grade_rejects_cross_column_value_matches():
    expected={'revenue':92650.61,'units':69}
    swapped={'status':'answer','columns':['revenue','units'],'rows':[{'revenue':69,'units':92650.61}]}
    assert not h.numerical_expected_match(expected,swapped)
    assert not h.rows_match([['Necklaces',35412.92]],[ [35412.92,'Necklaces'] ])

def test_result_grade_requires_exact_shape_and_top_n_row_order():
    expected=[['Necklaces',35412.92],['Rings',29378.61],['Bracelets',11836.5]]
    assert h.rows_match(expected,expected)
    assert not h.rows_match(expected,list(reversed(expected)))
    assert not h.rows_match(expected,[*expected,['Pendants',7561.07]])

def test_transient_http_failures_retry_with_exponential_backoff(monkeypatch):
    import io, urllib.error
    client=h.LocalClient('http://127.0.0.1:1',retries=4);attempts=[];delays=[]
    def fake_open(req,timeout):
        attempts.append(1)
        if len(attempts)<3:raise urllib.error.HTTPError(req.full_url,503,'unavailable',{},io.BytesIO(b''))
        class Response:
            headers={'Content-Type':'application/json'}
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return b'{"ok":true}'
        return Response()
    monkeypatch.setattr(client.opener,'open',fake_open)
    monkeypatch.setattr(h.time,'sleep',lambda delay:delays.append(delay))
    monkeypatch.setattr(h.random,'uniform',lambda a,b:0)
    assert client.json('/probe')=={'ok':True}
    assert len(attempts)==3 and delays==[.5,1.0]

def test_quota_budget_http_errors_are_not_retried(monkeypatch):
    import io, urllib.error
    client=h.LocalClient('http://127.0.0.1:1',retries=4);attempts=[]
    def fake_open(req,timeout):
        attempts.append(1)
        raise urllib.error.HTTPError(req.full_url,429,'quota',{},io.BytesIO(b'{"error":{"code":"quota_exhausted"}}'))
    monkeypatch.setattr(client.opener,'open',fake_open)
    monkeypatch.setattr(h.time,'sleep',lambda delay:None)
    with pytest.raises(RuntimeError):client.json('/probe')
    assert len(attempts)==1

def test_live_runner_submits_followup_as_second_request_and_reuses_cache(tmp_path,monkeypatch):
    state={'questions':[],'calls':0}
    class FakeClient:
        def __init__(self,base):self.calls=0
        def json(self,path,method='GET',data=None):
            if path.endswith('/api/health'):return {'status':'ok','ai_status':'ready','models':{'main':'m','fast':'f','embedding':'e'}}
            if path.endswith('/api/chat'):
                question=data['question'];state['questions'].append(question);self.calls+=1;state['calls']+=1
                value=92650.61 if question=='What is total revenue?' else 24656.11
                return {'status':'answer','answer':'Computed.','verified':True,'columns':['revenue'],'rows':[{'revenue':value}],
                    'usage':{'calls':self.calls,'max_calls':200,'input_tokens':10,'output_tokens':2,'total_tokens':12}}
            return {'schema_hash':'schema-v1','usage':{'calls':self.calls}}
    monkeypatch.setattr(h,'LocalClient',FakeClient)
    item=next(q for q in h.QUESTIONS if q['id']=='f01');cache=tmp_path/'responses.json';out=tmp_path/'first.jsonl'
    lines,calls=h.run_live([item],1,out,'http://localhost',cache,True,0)
    assert calls==2 and state['questions']==['What is total revenue?','Only for Q1.']
    assert lines[0]['verdict']=='PASS' and lines[0]['setup_verdict']=='PASS'
    assert len(json.loads(cache.read_text()))==1
    second,cached_calls=h.run_live([item],1,tmp_path/'second.jsonl','http://localhost',cache,False,0)
    assert second[0]['cached'] is True and second[0]['verdict']=='PASS'
    assert cached_calls==0 and len(state['questions'])==2


def test_error_cases_count_as_failures_in_category_accuracy():
    report=h.summarize([{'category':'joins','verdict':'PASS'},{'category':'joins','verdict':'ERROR'},{'category':'joins','verdict':'SKIPPED: no fixture'}])
    assert report['joins']=={'evaluated':2,'passed':1,'errors':1,'accuracy':0.5}

def test_prompt_injection_cases_use_isolated_sessions_and_do_not_pollute_source_session(tmp_path,monkeypatch):
    state={'next':0,'sessions':{},'chats':[]}
    class FakeClient:
        def __init__(self,base):
            state['next']+=1;self.sid=f's{state["next"]}';self.calls=0
            state['sessions'][self.sid]={'calls':0,'fixture':False}
        def json(self,path,method='GET',data=None):
            session=state['sessions'][self.sid]
            if path.endswith('/api/health'):return {'status':'ok','ai_status':'ready','models':{'main':'m','fast':'f','embedding':'e'}}
            if path.endswith('/api/chat'):
                question=data['question'];self.calls+=1;session['calls']=self.calls;state['chats'].append((self.sid,question,session['fixture']))
                if question==ITEMS['g01']['question']:
                    return {'status':'answer','columns':['revenue','units'],'rows':[{'revenue':92650.61,'units':69}],
                      'verified':True,'sql':'SELECT revenue FROM sales','usage':{'calls':self.calls}}
                return {'status':'answer','columns':['note'],'rows':[{'note':'fixture cell'}],'verified':True,
                  'sql':'SELECT note FROM fixture','usage':{'calls':self.calls}}
            return {'schema_hash':'schema-v1','usage':{'calls':self.calls}}
        def upload_fixture(self):
            state['sessions'][self.sid]['fixture']=True
            return {'schema_hash':'schema-with-fixture'}
    monkeypatch.setattr(h,'LocalClient',FakeClient)
    items=[ITEMS['i01'],ITEMS['g01'],ITEMS['i02']]
    lines,calls=h.run_live(items,3,tmp_path/'isolated.jsonl','http://localhost',tmp_path/'cache.json',True,0)
    assert calls==3 and all(r['verdict']=='PASS' for r in lines)
    injection_sessions={sid for sid,question,fixture in state['chats'] if question.startswith(('How much did we sell?','List products with notes'))}
    source=[(sid,fixture) for sid,question,fixture in state['chats'] if question==ITEMS['g01']['question']]
    assert len(injection_sessions)==2 and len(source)==1
    assert source[0][0] not in injection_sessions and source[0][1] is False
    assert all(fixture is True for sid,question,fixture in state['chats'] if question.startswith(('How much did we sell?','List products with notes')))
