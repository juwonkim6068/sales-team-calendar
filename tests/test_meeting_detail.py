import ast
from pathlib import Path
from unittest.mock import patch, MagicMock
import unittest
import streamlit as st
from streamlit.testing.v1 import AppTest

APP=Path(__file__).resolve().parents[1]/'app.py'
CONSTANTS={}
for node in ast.parse(APP.read_text()).body:
 if isinstance(node,ast.Assign):
  for target in node.targets:
   if isinstance(target,ast.Name) and target.id in ('HEAD','MEETING_FIELDS'):
    CONSTANTS[target.id]=ast.literal_eval(node.value)
FIELDS=CONSTANTS['MEETING_FIELDS']
RECORDS=[]
for index in (1,2):
 record={k:'' for k in FIELDS}
 record.update({'ID':f'm{index}','제목':f'회의 {index}','구분':'정기회의','부서':'영업부','날짜':'2026-10-29','시작':'10:00','종료':'11:00','장소':'회의실','참석자':'김주원, 이상인','작성자':'김주원','회의내용':f'회의 {index}의 전체 내용\n두 번째 문단','결정사항':f'결정 {index}','후속조치':f'담당자 확인 {index}'})
 RECORDS.append(record)

class MeetingDetailTests(unittest.TestCase):
 def setUp(self):
  st.cache_resource.clear()
  self.service=MagicMock()
  self.service.spreadsheets.return_value.get.return_value.execute.return_value={'sheets':[{'properties':{'title':'통합업무'}},{'properties':{'title':'회의록DB'}}]}
  def get(**kwargs):
   request=MagicMock()
   request.execute.return_value={'values':[FIELDS]+[[r[k] for k in FIELDS] for r in RECORDS]} if '회의록DB' in kwargs['range'] else {'values':[CONSTANTS['HEAD']]}
   return request
  self.service.spreadsheets.return_value.values.return_value.get.side_effect=get
  for patcher in (patch('google.oauth2.service_account.Credentials.from_service_account_info',return_value=MagicMock()),patch('googleapiclient.discovery.build',return_value=self.service)):
   patcher.start();self.addCleanup(patcher.stop)
  self.addCleanup(st.cache_resource.clear)

 def app(self):
  at=AppTest.from_file(str(APP))
  at.secrets['gcp_service_account']={'offline':True}
  at.run(timeout=30)
  at.sidebar.radio[0].set_value('📝 회의록').run(timeout=30)
  self.assertFalse(at.exception)
  return at

 def test_detail_opens_selected_meeting_and_closes(self):
  at=self.app()
  at.button(key='meeting_m2').click().run(timeout=30)
  self.assertFalse(at.exception)
  self.assertEqual(at.session_state['meeting_view_id'],'m2')
  self.assertTrue(any(d.proto.dialog.title=='회의록 상세' for d in at.get('dialog')))
  bodies=''.join(x.value for x in at.markdown if 'meeting-body' in x.value and '<div class="meeting-section">' in x.value)
  self.assertIn('회의 2의 전체 내용\n두 번째 문단',bodies)
  self.assertIn('결정 2',bodies)
  self.assertIn('담당자 확인 2',bodies)
  at.button(key='meeting_detail_close').click().run(timeout=30)
  self.assertFalse(at.exception)
  self.assertNotIn('meeting_view_id',at.session_state)

 def test_edit_save_closes_detail(self):
  at=self.app()
  at.button(key='meeting_m1').click().run(timeout=30)
  next(x for x in reversed(list(at.text_input)) if x.label=='회의 제목 *').set_value('수정한 회의')
  next(b for b in reversed(list(at.button)) if b.label=='💾 회의록 저장').click().run(timeout=30)
  self.assertFalse(at.exception)
  self.assertNotIn('meeting_view_id',at.session_state)
  saved=self.service.spreadsheets.return_value.values.return_value.update.call_args.kwargs['body']['values'][0]
  self.assertEqual(saved[0],'m1')
  self.assertEqual(saved[1],'수정한 회의')
