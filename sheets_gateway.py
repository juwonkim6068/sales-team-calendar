"""Shared, bounded Sheets read cache with single-flight reads and quota backoff."""
from contextlib import contextmanager
from copy import deepcopy
from functools import wraps
import threading
import time
from googleapiclient.errors import HttpError
from googleapiclient.http import HttpRequest

class SheetsReadUnavailable(RuntimeError):
 pass

class SheetsGateway:
 def __init__(self,service,clock=time.monotonic):
  self._service=service;self._clock=clock;self._lock=threading.RLock()
  self._cache={};self._cooldown=0;self._local=threading.local();self.read_status=''
 def __getattr__(self,name):
  return getattr(_Resource(self,self._service),name)
 def _execute(self,request,*args,**kwargs):
  with self._lock:
   now=self._clock();read=request.method=='GET';key=request.uri
   if not read:
    try:return request.execute(*args,**kwargs)
    finally:
     # Keep stale snapshots for outage display but never regard them as fresh.
     self._cache={k:(0,v) for k,(_,v) in self._cache.items()}
   fresh=getattr(self._local,'fresh',False)
   cached=self._cache.get(key)
   if not fresh and cached and cached[0]>now:
    return deepcopy(cached[1])
   def unavailable():
    self.read_status='Google Sheets 요청 한도로 최신 조회를 잠시 대기 중입니다. 마지막 조회 데이터를 표시합니다.'
    if cached and not fresh:return deepcopy(cached[1])
    raise SheetsReadUnavailable('Google Sheets 요청이 일시적으로 제한되었습니다. 약 1분 후 다시 시도해 주세요. 작성한 내용은 유지됩니다.')
   if self._cooldown>now:return unavailable()
   try:
    # Never automatically retry writes or immediately retry exhausted read quotas.
    result=request.execute(*args,**kwargs)
   except HttpError as exc:
    status=getattr(exc.resp,'status',None)
    if status not in (429,500,502,503,504):raise
    self._cooldown=now+(65 if status==429 else 10)
    return unavailable()
   ttl=300 if '/values' not in key else 30
   if len(self._cache)>=128 and key not in self._cache:
    self._cache.pop(next(iter(self._cache)))
   self._cache[key]=(self._clock()+ttl,deepcopy(result))
   self.read_status=''
   return result

class _Resource:
 def __init__(self,gateway,resource):self._gateway=gateway;self._resource=resource
 def __getattr__(self,name):
  member=getattr(self._resource,name)
  if not callable(member) or name=='execute':return member
  @wraps(member)
  def call(*args,**kwargs):
   result=member(*args,**kwargs)
   if isinstance(result,HttpRequest):return _Request(self._gateway,result)
   return _Resource(self._gateway,result)
  return call

class _Request:
 def __init__(self,gateway,request):self._gateway=gateway;self._request=request
 def execute(self,*args,**kwargs):return self._gateway._execute(self._request,*args,**kwargs)

@contextmanager
def fresh_reads(service):
 """Mutation preflight must never use an old snapshot or stale fallback."""
 if not isinstance(service,SheetsGateway):
  yield;return
 previous=getattr(service._local,'fresh',False)
 service._local.fresh=True
 try:yield
 finally:service._local.fresh=previous
