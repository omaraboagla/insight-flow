"""Playwright UI E2E with a local static server and fully mocked API.

No FastAPI process, .env access, SDK initialization, or Gemini traffic is used.
All browser API calls are fulfilled by Playwright routes, so this suite can run
without a key and cannot consume model quota.
"""
from __future__ import annotations
import functools, json, threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[2]
STATIC=ROOT/'app'/'static'
FIXTURE=ROOT/'tests'/'fixtures'/'messy_ingestion.xlsx'

TABLES=[
 {'name':'sales__sales','alias':'Sales · Sales','file':'sales.xlsx','sheet':'Sales','row_count':65,'warnings':[],
  'columns':[{'name':'channel','original_name':'Channel','type':'text','null_pct':0,'sample_values':['In-store','Online'],'distinct_values':['In-store','Online']},{'name':'quantity','original_name':'Quantity','type':'number','null_pct':0,'sample_values':[1,2]},{'name':'line_total_usd','original_name':'LineTotalUSD','type':'currency','null_pct':0,'sample_values':[6249,511.1]}]},
 {'name':'products__products','alias':'Products · Products','file':'products.xlsx','sheet':'Products','row_count':40,'warnings':[],
  'columns':[{'name':'sku','original_name':'SKU','type':'text','null_pct':0,'sample_values':['RNG-001'],'distinct_values':['RNG-001']},{'name':'category','original_name':'Category','type':'text','null_pct':0,'distinct_values':['Rings','Necklaces']}]},
 {'name':'customers__customers','alias':'Customers · Customers','file':'customers.xlsx','sheet':'Customers','row_count':32,'warnings':[],
  'columns':[{'name':'customerid','original_name':'CustomerID','type':'text','null_pct':0,'sample_values':['C001']}]},
 {'name':'employees__employees','alias':'Employees · Employees','file':'employees.xlsx','sheet':'Employees','row_count':14,'warnings':[],
  'columns':[{'name':'employeeid','original_name':'EmployeeID','type':'text','null_pct':0,'sample_values':['E001']}]},
 {'name':'purchases__purchases','alias':'Purchases · Purchases','file':'purchases.xlsx','sheet':'Purchases','row_count':40,'warnings':[],
  'columns':[{'name':'status','original_name':'Status','type':'text','null_pct':0,'distinct_values':['Pending','Received']}]},
 {'name':'suppliers__suppliers','alias':'Suppliers · Suppliers','file':'suppliers.xlsx','sheet':'Suppliers','row_count':10,'warnings':[],
  'columns':[{'name':'supplierid','original_name':'SupplierID','type':'text','null_pct':0,'sample_values':['S01']}]},
]
RELATIONSHIPS=[
 {'from_table':'sales__sales','from_column':'sku','to_table':'products__products','to_column':'sku','overlap':1.0,'confidence':1.0,'kind':'many-to-one'},
 {'from_table':'sales__sales','from_column':'customerid','to_table':'customers__customers','to_column':'customerid','overlap':1.0,'confidence':1.0,'kind':'many-to-one'},
]
def save_screenshot(page,name):
    folder=ROOT/'reports'/'screenshots'/'e2e';folder.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(folder/f'{name}.png'),full_page=True)

def schema_payload(tables=None):
    tables=tables or TABLES
    return {'tables':tables,'relationships':RELATIONSHIPS,'schema_hash':'mock-schema-v1','examples':['What is total sales revenue?','Show sales by channel.'],'warnings':[],
            'usage':{'calls':0,'max_calls':200,'remaining_calls':200,'input_tokens':0,'output_tokens':0,'total_tokens':0}}
def answer_payload():
    return {'status':'answer','answer':'Computed sales revenue is 92,650.61 across the two channels.','needs_clarification':None,'result_id':'mock-result','columns':['channel','revenue'],
            'rows':[{'channel':'In-store','revenue':67655.99},{'channel':'Online','revenue':24994.62}],'total_rows':2,'truncated':False,
            'sql':'SELECT channel, SUM(line_total_usd) AS revenue FROM sales__sales GROUP BY channel LIMIT 1000','tables_used':['sales__sales'],
            'columns_used':['sales__sales.channel','sales__sales.line_total_usd'],'assumptions':[],'join_keys':[],
            'sources':[{'file':'sales.xlsx','sheet':'Sales','table':'sales__sales','columns':['channel','line_total_usd']}],
            'chart':{'type':'bar','label_column':'channel','value_columns':['revenue']},'verified':True,'source':'computed','model':'mock',
            'tokens':{'input':0,'output':0,'total':0},'latency_ms':23,'cached':False,
            'usage':{'calls':0,'max_calls':200,'remaining_calls':200,'input_tokens':0,'output_tokens':0,'total_tokens':0}}

@pytest.fixture(scope='session')
def local_static_url():
    handler=functools.partial(SimpleHTTPRequestHandler,directory=str(STATIC))
    server=ThreadingHTTPServer(('127.0.0.1',0),handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try: yield f'http://127.0.0.1:{server.server_port}'
    finally: server.shutdown();server.server_close();thread.join(timeout=2)

@pytest.fixture
def ui(local_static_url):
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(accept_downloads=True,viewport={'width':1440,'height':1000})
        page=context.new_page()
        page.add_init_script("window.print=()=>{window.__printCalled=true};")
        state={'chat_bodies':[],'uploaded':False}
        def mock_api(route):
            req=route.request; path=req.url.split('?',1)[0]
            if path.endswith('/api/health'):
                return route.fulfill(json={'status':'ok','ai_status':'missing_key','models':{'main':'mock-main','fast':'mock-fast','embedding':'mock-embed'}})
            if path.endswith('/api/schema') or path.endswith('/api/reload'):
                return route.fulfill(json=schema_payload())
            if '/api/tables/' in path and path.endswith('/preview'):
                return route.fulfill(json={'table':'sales__sales','columns':['channel','quantity','line_total_usd'],
                  'rows':[{'channel':'In-store','quantity':1,'line_total_usd':6249},{'channel':'Online','quantity':2,'line_total_usd':511.1}],
                  'total_rows':65,'page':1,'page_size':25})
            if path.endswith('/api/chat/stream'):
                body=req.post_data_json or {};state['chat_bodies'].append(body)
                sse='event: progress\ndata: {"stage":"understanding","message":"Understanding question"}\n\nevent: result\ndata: '+json.dumps(answer_payload())+'\n\n'
                return route.fulfill(status=200,headers={'Content-Type':'text/event-stream','Cache-Control':'no-cache'},body=sse)
            if path.endswith('/api/upload'):
                state['uploaded']=True
                added={'name':'messy_ingestion__orders_notes','alias':'Messy_Ingestion · Orders & Notes','file':'messy_ingestion.xlsx','sheet':'Orders & Notes','row_count':2,'warnings':[],
                       'columns':[{'name':'order_id','original_name':'Order ID','type':'text','null_pct':0,'sample_values':['A-1']}]}
                all_tables=TABLES+[added]
                return route.fulfill(json={**schema_payload(all_tables),'files':[{'name':'messy_ingestion.xlsx','status':'loaded','tables':[added['name']],'error':None}]})
            if '/api/results/' in path and path.endswith('/csv'):
                return route.fulfill(status=200,headers={'Content-Type':'text/csv','Content-Disposition':'attachment; filename="sheet-agent-result.csv"'},body='channel,revenue\nIn-store,67655.99\nOnline,24994.62\n')
            return route.fulfill(status=404,json={'error':{'code':'not_found','message':'Mock endpoint not found.','retryable':False}})
        page.route('**/api/**',mock_api)
        # Fail any accidental nonlocal request. App assets and API remain loopback-only.
        page.route('https://**',lambda route: route.abort())
        page.goto(local_static_url,wait_until='domcontentloaded')
        expect(page.locator('#dataset-pill')).to_contain_text('6 tables')
        yield {'page':page,'state':state}
        context.close();browser.close()

def test_initial_boot_navigation_explorer_and_relationship_map(ui):
    page=ui['page']
    expect(page.get_by_text('Cloud AI: Gemini · missing key')).to_be_visible()
    expect(page.locator('#table-list .source-item')).to_have_count(6)
    save_screenshot(page,'boot')
    page.get_by_role('button',name='Data explorer').click()
    expect(page.locator('#explorer-view')).to_be_visible()
    expect(page.locator('#column-cards')).to_contain_text('Channel')
    expect(page.locator('#preview-table table tbody tr')).to_have_count(2)
    save_screenshot(page,'explorer')
    page.get_by_role('button',name='Relationships').click()
    expect(page.locator('#map-view')).to_be_visible()
    expect(page.locator('#relationship-count')).to_contain_text('2 relationships')
    expect(page.locator('.map-node')).to_have_count(6)
    assert page.locator('.relationship-row').count()==2
    save_screenshot(page,'relationships')

def test_example_question_answer_citation_and_exports(ui,tmp_path):
    page=ui['page']
    page.locator('.example-chip').first.click()
    answer=page.locator('.answer-card');expect(answer).to_be_visible();expect(answer).to_contain_text('92,650.61')
    answer.locator('details.citation summary').click()
    expect(answer.locator('pre')).to_contain_text('SELECT channel')
    expect(answer).to_contain_text('sales.xlsx · Sales')
    with page.expect_download() as download_info: answer.get_by_role('button',name='↓ CSV').click()
    download=download_info.value
    assert download.suggested_filename=='sheet-agent-result.csv'
    path=tmp_path/'result.csv';download.save_as(path);assert '92,650.61' not in path.read_text() # CSV is exact result rows, not answer prose.
    answer.get_by_role('button',name='▧ PDF').click()
    page.wait_for_function('window.__printCalled === true')
    save_screenshot(page,'answer-export')

def test_privacy_toggles_are_persisted_and_sent_to_chat(ui):
    page=ui['page']
    page.locator('#privacy-button').click()
    dialog=page.locator('#privacy-dialog');expect(dialog).to_be_visible()
    page.locator('#schema-only').check();page.locator('#no-result-rows').check()
    page.locator('#close-privacy').click()
    page.locator('.example-chip').first.click()
    expect(page.locator('.answer-card')).to_be_visible()
    payload=ui['state']['chat_bodies'][-1]
    assert payload['schema_only'] is True and payload['dont_send_result_rows'] is True
    assert page.evaluate("localStorage.getItem('sheet-schema-only')")=='true'
    assert page.evaluate("localStorage.getItem('sheet-no-result-rows')")=='true'
    page.locator('#privacy-button').click();save_screenshot(page,'privacy')

def test_upload_additional_workbook_with_progress_and_schema_refresh(ui):
    page=ui['page']
    assert FIXTURE.exists()
    page.locator('#file-input').set_input_files(str(FIXTURE))
    expect(page.locator('#upload-status')).to_contain_text('messy_ingestion.xlsx · loaded (1 table)')
    expect(page.locator('#table-list .source-item')).to_have_count(7)
    assert ui['state']['uploaded'] is True
    save_screenshot(page,'upload')
