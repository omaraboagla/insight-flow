"""Only boundary to the cloud. Never expose provider exceptions or credentials."""
from __future__ import annotations
import json,logging,os,random,time
from dataclasses import dataclass
from urllib.parse import urlsplit
from dotenv import load_dotenv
from google import genai
from google.genai import types

GOOGLE_HOST='generativelanguage.googleapis.com'
for name in ('google.genai','httpx','httpcore'): logging.getLogger(name).setLevel(logging.CRITICAL)

PLAN_SCHEMA={"type":"object","properties":{
 "needs_clarification":{"anyOf":[{"type":"null"},{"type":"object","properties":{"question":{"type":"string"},"options":{"type":"array","items":{"type":"string"}}},"required":["question","options"],"additionalProperties":False}]},
 "sql":{"type":"string"},"tables_used":{"type":"array","items":{"type":"string"}},"columns_used":{"type":"array","items":{"type":"string"}},"assumptions":{"type":"array","items":{"type":"string"}},"answerable":{"type":"boolean"},"reason_if_unanswerable":{"type":"string"}},"required":["needs_clarification","sql","tables_used","columns_used","assumptions","answerable","reason_if_unanswerable"],"additionalProperties":False}

MESSAGES={
 'missing_key':'The online answer service is not set up. Add its key to local settings and restart Insight Flow.',
 'invalid_key':'The online answer service did not accept its key. Check local settings and restart.',
 'offline':'Could not reach the online answer service. Check your connection and try again.',
 'quota_exhausted':'The online answer service is busy. Wait a moment and try again.',
 'budget_exhausted':'You have reached the usage limit for this session.',
 'model_not_found':'The online answer service is unavailable. Check local settings.',
 'timeout':'The answer took too long. Try again.',
 'upstream_error':'The online answer service is temporarily unavailable. Try again shortly.',
 'invalid_response':'The answer could not be prepared. Please try a different question.'}
class AIError(Exception):
    def __init__(self,code): self.code=code; self.message=MESSAGES[code]; super().__init__(self.message)
    def envelope(self): return {'error':{'code':self.code,'message':self.message,'retryable':self.code in ('offline','timeout','quota_exhausted','upstream_error')}}

@dataclass
class Usage:
    calls:int=0
    input_tokens:int=0
    output_tokens:int=0
    max_calls:int=40
    def public(self): return dict(calls=self.calls,max_calls=self.max_calls,remaining_calls=max(0,self.max_calls-self.calls),input_tokens=self.input_tokens,output_tokens=self.output_tokens,total_tokens=self.input_tokens+self.output_tokens)

def restrict_host(request):
    if request.url.host!=GOOGLE_HOST or request.url.scheme!='https': raise RuntimeError('Outbound destination blocked.')

def _model(value):
    if 'gemini-2.5' in value: raise ValueError('Gemini 2.5 models are disabled. Select a supported Gemini Flash model.')
    return value

class Gemini:
    def __init__(self):
        load_dotenv()
        self.main_model=_model(os.getenv('GEMINI_MODEL','gemini-3.5-flash'))
        self.fast_model=_model(os.getenv('GEMINI_FAST_MODEL','gemini-3.1-flash-lite'))
        self.embedding_model=_model(os.getenv('GEMINI_EMBED_MODEL','gemini-embedding-001'))
        self.client=None
        key=os.getenv('GEMINI_API_KEY','').strip()
        if key:
            # Prevent redirection to third parties, proxy use and SDK-level retry duplication.
            options=types.HttpOptions(timeout=90000,client_args={'event_hooks':{'request':[restrict_host]},'follow_redirects':False,'trust_env':False},retry_options=types.HttpRetryOptions(attempts=1))
            self.client=genai.Client(api_key=key,http_options=options)
        self.status='ready' if self.client else 'missing_key'
    def _call(self,usage,method,**kwargs):
        if self.client is None: raise AIError('missing_key')
        for attempt in range(4):
            if usage.calls>=usage.max_calls: raise AIError('budget_exhausted')
            usage.calls+=1
            try:
                response=method(**kwargs)
                meta=getattr(response,'usage_metadata',None)
                if meta:
                    usage.input_tokens+=getattr(meta,'prompt_token_count',0) or 0
                    usage.output_tokens+=getattr(meta,'candidates_token_count',0) or 0
                return response
            except AIError: raise
            except Exception as exc:
                # Use status only. Raw SDK exception may contain sensitive request details.
                code=getattr(exc,'code',None) or getattr(exc,'status_code',None)
                try: code=int(code)
                except (ValueError,TypeError): code=0
                if (code==429 or 500<=code<600) and attempt<3:
                    time.sleep(min(4, .5*(2**attempt))+random.uniform(0,.25));continue
                if code in (400,401,403): category='invalid_key'
                elif code==404: category='model_not_found'
                elif code==429: category='quota_exhausted'
                elif code in (408,504) or 'timeout' in type(exc).__name__.lower(): category='timeout'
                elif 500<=code<600: category='upstream_error'
                else: category='offline'
                self.status=category
                raise AIError(category) from None
        raise AIError('upstream_error')
    def generate(self,prompt,usage,structured=False,fast=False):
        config=types.GenerateContentConfig(temperature=0,max_output_tokens=9999,response_mime_type='application/json' if structured else 'text/plain',response_json_schema=PLAN_SCHEMA if structured else None)
        response=self._call(usage,self.client.models.generate_content if self.client else None,model=self.fast_model if fast else self.main_model,contents=prompt,config=config)
        self.status='ready'
        if not structured:return (response.text or '').strip()
        try:
            plan=json.loads(response.text)
            if set(plan)!=set(PLAN_SCHEMA['required']): raise ValueError()
            if not isinstance(plan['answerable'],bool) or not isinstance(plan['sql'],str): raise ValueError()
            for field in ('tables_used','columns_used','assumptions'):
                if not isinstance(plan[field],list) or not all(isinstance(v,str) for v in plan[field]): raise ValueError()
            clarification=plan['needs_clarification']
            if clarification is not None:
                if not isinstance(clarification,dict) or not isinstance(clarification.get('question'),str) or not isinstance(clarification.get('options'),list) or not 2<=len(clarification['options'])<=6 or not all(isinstance(v,str) for v in clarification['options']): raise ValueError()
            return plan
        except Exception:raise AIError('invalid_response') from None
    def embed(self,texts,usage):
        if not texts:return []
        response=self._call(usage,self.client.models.embed_content if self.client else None,model=self.embedding_model,contents=texts,config=types.EmbedContentConfig(output_dimensionality=768))
        return [e.values for e in response.embeddings]
    def model_inventory(self,usage):
        response=self._call(usage,lambda:list(self.client.models.list()))
        return [m.name.removeprefix('models/') for m in response]
