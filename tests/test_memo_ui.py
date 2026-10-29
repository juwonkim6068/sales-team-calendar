from datetime import date
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from memo_ui import filter_memos
from streamlit.testing.v1 import AppTest

RECORDS=[{'ID':'a','작성자':'김주원','날짜':'2026-10-29','제목':'거래처 통화','내용':'확인 사항\n다음 주 회의','수정일':'2026-10-29T09:00:00'},
         {'ID':'b','작성자':'김주원','날짜':'2026-10-28','제목':'정산','내용':'지난달 정산','수정일':'2026-10-28T09:00:00'},
         {'ID':'c','작성자':'이상인','날짜':'2026-10-29','제목':'영업','내용':'별도 메모','수정일':'2026-10-29T10:00:00'}]
SOURCE='''
import streamlit as st
from memo_ui import render_memos
if 'records' not in st.session_state: st.session_state['records']=RECORDS
def save(record):
 if st.session_state.get('fail'):raise RuntimeError('test failure')
 st.session_state['records']=[r for r in st.session_state['records'] if r['ID']!=record['ID']]+[record]
def delete(item):
 st.session_state['records']=[r for r in st.session_state['records'] if r['ID']!=item]
render_memos(st.session_state['records'],['김주원','이상인'],lambda x:x,save,delete)
'''.replace('RECORDS',repr(RECORDS))

class MemoUITests(unittest.TestCase):
 def app(self):
  at=AppTest.from_string(SOURCE)
  at.session_state['memo_selected_day']=date(2026,10,29)
  at.run()
  self.assertFalse(at.exception)
  return at

 def test_search_author_and_date(self):
  self.assertEqual([r['ID'] for r in filter_memos(RECORDS,'김주원',date(2026,10,29))],['a'])
  self.assertEqual([r['ID'] for r in filter_memos(RECORDS,'김주원',date(2026,10,29),True,'정산')],['b'])
  self.assertEqual(filter_memos(RECORDS,'김주원',date(2026,10,29),False,'영업'),[])

 def test_new_memo_save_returns_to_reading(self):
  at=self.app()
  at.button(key='memo_ui_new').click().run()
  next(x for x in at.text_input if x.label=='제목').set_value('새 기록')
  at.text_area[0].set_value('첫째 줄\n둘째 줄')
  next(b for b in at.button if b.label=='저장').click().run()
  self.assertFalse(at.exception)
  saved=next(r for r in at.session_state['records'] if r['제목']=='새 기록')
  self.assertEqual(saved['작성자'],'김주원')
  self.assertEqual(saved['날짜'],'2026-10-29')
  self.assertEqual(saved['내용'],'첫째 줄\n둘째 줄')
  self.assertEqual(at.session_state['memo_ui_mode'],'read')

 def test_edit_and_failed_save_preserve_input(self):
  at=self.app()
  at.button(key='memo_ui_edit').click().run()
  next(x for x in at.text_input if x.label=='제목').set_value('수정된 기록')
  at.session_state['fail']=True
  next(b for b in at.button if b.label=='저장').click().run()
  self.assertFalse(at.exception)
  self.assertTrue(at.error)
  self.assertEqual(next(x for x in at.text_input if x.label=='제목').value,'수정된 기록')
  self.assertEqual(at.session_state['memo_ui_selected'],'a')
  at.session_state['fail']=False
  next(b for b in at.button if b.label=='저장').click().run()
  self.assertFalse(at.exception)
  self.assertEqual(next(r for r in at.session_state['records'] if r['ID']=='a')['제목'],'수정된 기록')

 def test_delete_requires_confirmation(self):
  at=self.app()
  self.assertTrue(at.button(key='memo_delete_a').disabled)
  at.checkbox(key='memo_confirm_a').check().run()
  at.button(key='memo_delete_a').click().run()
  self.assertFalse(at.exception)
  self.assertFalse(any(r['ID']=='a' for r in at.session_state['records']))

 def test_blank_memo_retains_form(self):
  at=self.app()
  at.button(key='memo_ui_new').click().run()
  next(x for x in at.text_input if x.label=='제목').set_value('제목만')
  next(b for b in at.button if b.label=='저장').click().run()
  self.assertFalse(at.exception)
  self.assertTrue(at.warning)
  self.assertEqual(len(at.session_state['records']),len(RECORDS))
  self.assertEqual(next(x for x in at.text_input if x.label=='제목').value,'제목만')

if __name__=='__main__':unittest.main()
