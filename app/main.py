from __future__ import annotations
import asyncio,csv,io,json,os,queue,re,secrets,shutil,threading,time,zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI,Request,UploadFile,File,Query
from fastapi.responses import FileResponse,JSONResponse,StreamingResponse,Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel,Field
from .ingest import ingest_directory,ingest_file,SUPPORTED,clean_value
from .schema import schema_hash,examples
from .relationships import detect_relationships
from .executor import Executor
from .cache import ResponseCache
from .retrieve import Retriever
from .llm import Gemini,Usage,AIError
from .planner import Planner

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data'/'source'
MAX_UPLOAD=20*1024*1024
sessions={};session_lock=threading.RLock()
source_tables={};source_errors=[]
gemini=None;planner=None

class Session:
    def __init__(self):
        self.tables=dict(source_tables);self.errors=list(source_errors);self.history=[];self.results={};self.cache=ResponseCache();self.retriever=Retriever();self.lock=threading.RLock();self.last_seen=time.monotonic();self.id=secrets.token_urlsafe(24)
        self.usage=Usage(max_calls=max(1,int(os.getenv('MAX_CALLS_PER_SESSION','200'))));self.uploads=[];self.rebuild()
    def rebuild(self):
        old=getattr(self,'executor',None)
        self.executor=Executor(self.tables);self.relationships=detect_relationships(self.tables);self.schema_hash=schema_hash(self.tables)
        self.history=[];self.results={};self.cache=ResponseCache();self.retriever=Retriever()
        if old:old.close()
    def public(self):
        return dict(tables=[t.metadata() for t in self.tables.values()],relationships=self.relationships,schema_hash=self.schema_hash,examples=examples(self.tables),warnings=[w for t in self.tables.values() for w in t.warnings]+[f'{e["file"]}: {e["message"]}' for e in self.errors],usage=self.usage.public())

def prepare_source():
    SOURCE.mkdir(parents=True,exist_ok=True)
    archive=ROOT/'data'/'files.zip'
    if not archive.exists() and (Path.home()/'Downloads'/'files.zip').exists():shutil.copyfile(Path.home()/'Downloads'/'files.zip',archive)
    if not any(p.suffix.lower() in SUPPORTED for p in SOURCE.iterdir()) and archive.exists():
        used=set()
        with zipfile.ZipFile(archive) as z:
            for entry in z.infolist():
                parts=Path(entry.filename).parts
                if entry.is_dir() or any(p.startswith('.') or p=='__MACOSX' for p in parts):continue
                filename=Path(entry.filename).name
                if Path(filename).suffix.lower() not in SUPPORTED:continue
                if entry.file_size>100*1024*1024:continue
                stem=Path(filename).stem;suffix=Path(filename).suffix;counter=2
                while filename.lower() in used:filename=f'{stem}_{counter}{suffix}';counter+=1
                used.add(filename.lower())
                with z.open(entry) as src,(SOURCE/filename).open('wb') as dst:shutil.copyfileobj(src,dst)

def model_version(model):
    match=re.search(r'gemini-(\d+)\.(\d+)',model)
    return tuple(map(int,match.groups())) if match else (0,0)

def startup_ai_check():
    if gemini.client is None:return
    usage=Usage(max_calls=8)
    try:
        available=gemini.model_inventory(usage)
        changes=[]
        for attribute,lite in [('main_model',False),('fast_model',True)]:
            requested=getattr(gemini,attribute)
            if requested not in available:
                compatible=[m for m in available if 'flash' in m and 'gemini-2.5' not in m and not any(x in m for x in ('image','audio','tts','live'))]
                choices=[m for m in compatible if ('lite' in m)==lite]
                if not choices and lite: choices=compatible
                if not choices:raise AIError('model_not_found')
                selected=max(choices,key=lambda m:(model_version(m),not('preview' in m),m))
                setattr(gemini,attribute,selected);changes.append({'purpose':attribute,'requested':requested,'selected':selected})
        if gemini.embedding_model not in available:raise AIError('model_not_found')
        gemini.generate('Reply with OK only.',usage,fast=True)
        record={'available_models':available,'selected':{'main':gemini.main_model,'fast':gemini.fast_model,'embedding':gemini.embedding_model},'fallbacks':changes,'tiny_call':'passed','calls':usage.calls}
        (ROOT/'data'/'runtime_models.json').write_text(json.dumps(record,indent=2))
    except AIError as error:gemini.status=error.code
    except Exception:gemini.status='offline'

@asynccontextmanager
async def lifespan(app):
    global source_tables,source_errors,gemini,planner
    prepare_source();source_tables,source_errors=ingest_directory(SOURCE)
    gemini=Gemini();planner=Planner(gemini)
    # Keep startup/UI immediate; discovery uses only the application's credential boundary.
    ai_thread=threading.Thread(target=startup_ai_check,daemon=True);ai_thread.start()
    yield
    for session in list(sessions.values()):session.executor.close()
    if gemini.client:gemini.client.close()

app=FastAPI(title='Insight Flow',docs_url=None,redoc_url=None,lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','[::1]','testserver'])
app.mount('/static',StaticFiles(directory=ROOT/'app'/'static'),name='static')

@app.middleware('http')
async def local_session(request,call_next):
    if request.method in ('POST','PUT','DELETE','PATCH'):
        origin=request.headers.get('origin')
        if origin and origin not in (f'http://{request.headers.get("host")}',f'https://{request.headers.get("host")}'):
            return error('invalid_request','This action must originate from the local app.',403)
    if request.url.path.startswith('/api/'):
        with session_lock:
            session=sessions.get(request.cookies.get('sheet_session',''))
            if session is None:
                expired=[sid for sid,s in sessions.items() if time.monotonic()-s.last_seen>3600]
                for sid in expired:sessions.pop(sid).executor.close()
                if len(sessions)>=50:return error('invalid_request','Too many active sessions. Restart the local server.',503)
                session=Session();sessions[session.id]=session
            session.last_seen=time.monotonic();request.state.session=session
        response=await call_next(request)
        response.set_cookie('sheet_session',session.id,httponly=True,samesite='strict',max_age=3600)
    else:response=await call_next(request)
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'"
    response.headers['X-Content-Type-Options']='nosniff';response.headers['Referrer-Policy']='no-referrer'
    return response

def error(code,message,status=400,retryable=False):return JSONResponse({'error':{'code':code,'message':message,'retryable':retryable}},status_code=status)

def ai_response(exc):
    status={'missing_key':503,'invalid_key':503,'offline':503,'quota_exhausted':429,'budget_exhausted':429,'model_not_found':502,'timeout':504}.get(exc.code,502)
    return JSONResponse(exc.envelope(),status_code=status)

@app.get('/')
def index():return FileResponse(ROOT/'app'/'static'/'index.html')

@app.get('/api/health')
def health():return {'status':'ok','ai_status':gemini.status,'models':{'main':gemini.main_model,'fast':gemini.fast_model,'embedding':gemini.embedding_model}}

@app.get('/api/schema')
def schema(request:Request):return request.state.session.public()

@app.post('/api/reload')
def reload_data(request:Request):
    session=request.state.session
    with session.lock:
        session.tables,session.errors=ingest_directory(SOURCE)
        for path in session.uploads:
            try:
                for table in ingest_file(path):session.tables[table.name]=table
            except Exception:session.errors.append({'file':path.name,'message':'Could not reload uploaded workbook.'})
        session.rebuild();return session.public()

@app.get('/api/tables/{table}/preview')
def preview(table:str,request:Request,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),sort:str|None=None,direction:str='asc',search:str=Query('',max_length=200)):
    session=request.state.session
    with session.lock:
        if table not in session.tables:return error('invalid_request','Table not found.',404)
        frame=session.tables[table].frame
        if search:frame=frame[frame.astype(str).apply(lambda c:c.str.contains(search,case=False,regex=False)).any(axis=1)]
        if sort:
            if sort not in frame.columns or direction not in ('asc','desc'):return error('invalid_request','Invalid sort column or direction.')
            frame=frame.sort_values(sort,ascending=direction=='asc',na_position='last',kind='stable')
        total=len(frame);rows=frame.iloc[(page-1)*page_size:page*page_size]
        return dict(table=table,columns=list(frame.columns),rows=[{k:clean_value(v) for k,v in row.items()} for row in rows.to_dict('records')],total_rows=total,page=page,page_size=page_size)

@app.post('/api/upload')
async def upload(request:Request,files:list[UploadFile]=File(...)):
    session=request.state.session;results=[]
    if len(files)>20:return error('invalid_request','Upload up to 20 files at a time.')
    folder=ROOT/'data'/'uploads'/session.id;folder.mkdir(parents=True,exist_ok=True)
    for file in files:
        name=Path((file.filename or 'upload').replace('\\','/')).name[:150]
        if name.startswith('.') or Path(name).suffix.lower() not in SUPPORTED:
            results.append(dict(name=name,status='error',tables=[],error='Unsupported file. Use .xlsx, .xlsm, .xls, or .csv.'));continue
        contents=await file.read(MAX_UPLOAD+1)
        if len(contents)>MAX_UPLOAD:
            results.append(dict(name=name,status='error',tables=[],error='File is larger than the 20 MB upload limit.'));continue
        path=folder/name
        try:
            if Path(name).suffix.lower() in ('.xlsx','.xlsm'):
                with zipfile.ZipFile(io.BytesIO(contents)) as z:
                    if sum(e.file_size for e in z.infolist())>100*1024*1024:raise ValueError('Too large')
            path.write_bytes(contents)
            loaded=await asyncio.to_thread(ingest_file,path)
            if not loaded:raise ValueError('Empty workbook')
            with session.lock:
                for table in loaded:session.tables[table.name]=table
                if path not in session.uploads:session.uploads.append(path)
            results.append(dict(name=name,status='loaded',tables=[t.name for t in loaded],error=None))
        except Exception:
            path.unlink(missing_ok=True);results.append(dict(name=name,status='error',tables=[],error='Could not read this file. Check it is a valid, unlocked spreadsheet with nonempty sheets.'))
        finally:await file.close()
    with session.lock:session.rebuild();response=session.public()
    response['files']=results;return response

class ChatRequest(BaseModel):
    question:str=Field(min_length=1,max_length=4000)
    schema_only:bool=False
    dont_send_result_rows:bool=False

def ask(session,payload,progress=lambda stage:None):
    if not payload.question.strip():raise ValueError('invalid_request')
    with session.lock:return planner.ask(session,payload.question.strip(),payload.schema_only,payload.dont_send_result_rows,progress)

@app.post('/api/chat')
def chat(request:Request,payload:ChatRequest):
    try:return ask(request.state.session,payload)
    except AIError as exc:return ai_response(exc)
    except ValueError as exc:
        code=str(exc)
        if code=='empty_data':return error(code,'No data is loaded. Upload a workbook or reload the source folder.',422)
        if code=='invalid_request':return error(code,'Enter a question first.')
        return error('query_failed','The query could not be safely executed after repair. Rephrase the question or inspect the data explorer.',422)
    except Exception:return error('query_failed','The question could not be completed. Please retry or rephrase.',502,True)

@app.post('/api/chat/stream')
async def chat_stream(request:Request,payload:ChatRequest):
    events=asyncio.Queue();loop=asyncio.get_running_loop()
    messages={'understanding':'Understanding question','writing':'Writing query','running':'Running','verifying':'Verifying'}
    def progress(stage):loop.call_soon_threadsafe(events.put_nowait,('progress',{'stage':stage,'message':messages[stage]}))
    def work():
        try:result=ask(request.state.session,payload,progress);loop.call_soon_threadsafe(events.put_nowait,('result',result))
        except AIError as exc:loop.call_soon_threadsafe(events.put_nowait,('error',exc.envelope()))
        except ValueError as exc:
            code='empty_data' if str(exc)=='empty_data' else 'query_failed'
            message='No data is loaded. Upload a workbook or reload the source folder.' if code=='empty_data' else 'The query could not be safely executed after repair. Rephrase the question or inspect the data explorer.'
            loop.call_soon_threadsafe(events.put_nowait,('error',{'error':{'code':code,'message':message,'retryable':False}}))
        except Exception:loop.call_soon_threadsafe(events.put_nowait,('error',{'error':{'code':'query_failed','message':'The question could not be completed. Please retry or rephrase.','retryable':True}}))
    task=asyncio.create_task(asyncio.to_thread(work))
    async def stream():
        while True:
            try:event,data=await asyncio.wait_for(events.get(),timeout=5)
            except asyncio.TimeoutError:
                yield ': keepalive\n\n';continue
            yield f'event: {event}\ndata: {json.dumps(data,default=str)}\n\n'
            if event in ('result','error'):break
        await task
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

@app.get('/api/results/{result_id}/csv')
def export_csv(result_id:str,request:Request):
    session=request.state.session
    with session.lock:
        if result_id not in session.results:return error('invalid_request','Result not found in this session.',404)
        result=session.results[result_id];buf=io.StringIO();writer=csv.writer(buf);writer.writerow(result['columns'])
        # Neutralize formula injection when opening exported CSV in Excel.
        for row in result['rows']:writer.writerow(["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v for v in row])
        return Response(buf.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="sheet-agent-result.csv"'})
