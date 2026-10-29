import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import MagicMock
from googleapiclient.errors import HttpError
from googleapiclient.http import HttpRequest
from httplib2 import Response
from sheets_gateway import SheetsGateway, SheetsReadUnavailable, fresh_reads

class GatewayTests(unittest.TestCase):
 def setUp(self):
  self.now=[1.0];self.gateway=SheetsGateway(None,clock=lambda:self.now[0])
 def request(self,method='GET',uri='https://sheets.googleapis.com/v4/spreadsheets/S/values/T'):
  request=HttpRequest(MagicMock(),lambda r,c:c,uri,method=method)
  request.execute=MagicMock(return_value={'values':[['latest']]})
  return request
 def quota_error(self):return HttpError(Response({'status':'429'}),b'{"error":{"message":"quota"}}')
 def test_shared_cache_reduces_concurrent_reads_and_returns_copies(self):
  request=self.request()
  with ThreadPoolExecutor(max_workers=8) as pool:
   results=list(pool.map(lambda _:self.gateway._execute(request),range(20)))
  request.execute.assert_called_once()
  results[0]['values'][0][0]='changed'
  self.assertEqual(self.gateway._execute(request)['values'][0][0],'latest')
 def test_quota_uses_last_snapshot_without_retry_storm(self):
  request=self.request();self.gateway._execute(request);self.now[0]=40
  request.execute.side_effect=self.quota_error()
  for _ in range(12):self.assertEqual(self.gateway._execute(request)['values'][0][0],'latest')
  self.assertEqual(request.execute.call_count,2)
  self.assertTrue(self.gateway.read_status)
  with fresh_reads(self.gateway):
   with self.assertRaises(SheetsReadUnavailable):self.gateway._execute(request)
  self.assertEqual(request.execute.call_count,2)
  self.now[0]=106;request.execute.side_effect=None;request.execute.return_value={'values':[['recovered']]}
  self.assertEqual(self.gateway._execute(request)['values'][0][0],'recovered')
  self.assertEqual(self.gateway.read_status,'')
 def test_writes_invalidate_reads_and_are_not_retried(self):
  read=self.request();self.gateway._execute(read)
  write=self.request('POST');self.gateway._execute(write)
  self.gateway._execute(read)
  self.assertEqual(read.execute.call_count,2)
  write.execute.side_effect=self.quota_error()
  with self.assertRaises(HttpError):self.gateway._execute(write)
  self.assertEqual(write.execute.call_count,2)
 def test_fresh_preflight_bypasses_cache(self):
  read=self.request();self.gateway._execute(read)
  with fresh_reads(self.gateway):self.gateway._execute(read)
  self.assertEqual(read.execute.call_count,2)
 def test_no_snapshot_returns_safe_error_and_cools_down(self):
  read=self.request();read.execute.side_effect=self.quota_error()
  for _ in range(2):
   with self.assertRaises(SheetsReadUnavailable):self.gateway._execute(read)
  read.execute.assert_called_once()
 def test_resource_proxy_wraps_real_requests(self):
  read=self.request()
  raw=SimpleNamespace(spreadsheets=lambda:SimpleNamespace(get=lambda **kwargs:read))
  gateway=SheetsGateway(raw)
  gateway.spreadsheets().get(spreadsheetId='S').execute()
  gateway.spreadsheets().get(spreadsheetId='S').execute()
  read.execute.assert_called_once()
