"""Local endpoint contract tests; mock cloud boundary and never read .env."""
import pytest
fastapi=pytest.importorskip('fastapi')
httpx=pytest.importorskip('httpx')
from fastapi.testclient import TestClient
from app import main
from app.llm import AIError

SECRET_MARKER='TEST_ONLY_SECRET_MARKER_43b9'
class OfflineGemini:
    main_model='test-main';fast_model='test-fast';embedding_model='test-embed';status='missing_key';client=None
    # Represents an in-memory sentinel solely to assert it never reaches responses.
    private_test_marker=SECRET_MARKER
    def embed(self,*args,**kwargs): raise AIError('missing_key')
    def generate(self,*args,**kwargs): raise AIError('missing_key')
    def close(self): pass

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main,'Gemini',OfflineGemini)
    monkeypatch.setattr(main,'startup_ai_check',lambda:None)
    with TestClient(main.app) as c: yield c

def test_health_schema_and_index_are_local_and_secret_free(client):
    health=client.get('/api/health'); schema=client.get('/api/schema'); page=client.get('/')
    assert health.status_code==200 and health.json()['ai_status']=='missing_key'
    assert {'tables','relationships','schema_hash','examples','usage'} <= schema.json().keys()
    assert len(schema.json()['tables'])==6
    assert page.status_code==200 and 'Sheet Agent' in page.text
    for response in (health,schema,page): assert SECRET_MARKER not in response.text
    cookie=health.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=strict' in cookie

def test_chat_missing_key_returns_safe_message_without_credential(client):
    response=client.post('/api/chat',json={'question':'What is total sales?'})
    assert response.status_code==503
    assert response.json()['error']['code']=='missing_key'
    assert SECRET_MARKER not in response.text
    assert 'TEST_ONLY_SECRET_MARKER' not in response.text

def test_preview_pagination_and_sort_validation(client):
    schema=client.get('/api/schema').json(); table=next(t for t in schema['tables'] if t['sheet']=='Sales')
    response=client.get(f"/api/tables/{table['name']}/preview",params={'page':1,'page_size':5,'sort':'quantity','direction':'desc'})
    assert response.status_code==200 and len(response.json()['rows'])<=5
    bad=client.get(f"/api/tables/{table['name']}/preview",params={'sort':'missing','direction':'desc'})
    assert bad.status_code==400
