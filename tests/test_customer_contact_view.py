import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
import customer_workspace
from customer_workspace import contact_table_rows
from customer_data import SCHEMAS,CustomerStore
from test_customer_management import customer,fake_service

class ContactViewTests(unittest.TestCase):
 def test_contact_columns_and_split_numbers(self):
  result=contact_table_rows([{'연락처ID':'hidden','거래처코드':'hidden','성명':'담당자','연락처':'055-338-7618 / 010-8461-3027','담당역할':'구매','주담당여부':'예','수정일':'hidden'}])[0]
  self.assertEqual(list(result),['부서','직급','성명','연락처1','연락처2','이메일','비고'])
  self.assertEqual(result['연락처1'],'055-338-7618')
  self.assertEqual(result['연락처2'],'010-8461-3027')
 def test_edit_two_numbers_preserves_hidden_fields(self):
  owner=customer();contact={k:'' for k in SCHEMAS['거래처연락처DB']}
  contact.update({'연락처ID':'N1','거래처코드':'C001','성명':'담당자','연락처':'055-111 / 010-222','담당역할':'구매','주담당여부':'예'})
  tables={'거래처DB':[SCHEMAS['거래처DB'],[owner[k] for k in SCHEMAS['거래처DB']]],'거래처연락처DB':[SCHEMAS['거래처연락처DB'],[contact[k] for k in SCHEMAS['거래처연락처DB']]]}
  store=CustomerStore(fake_service(tables),'sid')
  source='''
import streamlit as st
from customer_workspace import editor,_test_store
if 'initialized' not in st.session_state:
 st.session_state['initialized']=True
 st.session_state['customer_editor']={'sheet':'거래처연락처DB','record':_test_store.read_all()['거래처연락처DB'][0],'code':'C001'}
editor(_test_store,_test_store.read_all(),[],lambda x:x)
'''
  with patch.object(customer_workspace,'_test_store',store,create=True):
   at=AppTest.from_string(source).run()
   self.assertFalse(at.exception)
   self.assertEqual(at.text_input(key='cf_거래처연락처DB_연락처1').value,'055-111')
   self.assertEqual(at.text_input(key='cf_거래처연락처DB_연락처2').value,'010-222')
   self.assertFalse(any(s.label in ('담당역할','주담당여부') for s in at.selectbox))
   at.text_input(key='cf_거래처연락처DB_연락처2').set_value('010-333')
   next(b for b in at.button if b.label=='저장').click().run()
   self.assertFalse(at.exception)
  row=store.read_all()['거래처연락처DB'][0]
  self.assertEqual(row['연락처'],'055-111 / 010-333')
  self.assertEqual(row['담당역할'],'구매')
  self.assertEqual(row['주담당여부'],'예')
