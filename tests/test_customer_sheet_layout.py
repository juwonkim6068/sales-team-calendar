import unittest
from copy import deepcopy
from customer_data import CustomerStore, SCHEMAS
from test_customer_management import fake_service

class CustomLayoutTests(unittest.TestCase):
 def tables(self):
  return {
   '거래처DB':[SCHEMAS['거래처DB']+['FAX'],['02015','테스트','직거래처']+['']*13+['02-123-4567']],
   '거래처연락처DB':[['거래처코드','거래처명','성명1','직급1','연락처1','성명2','직급2','연락처2','수정일'],['02015','테스트','첫째','과장','010-1111','둘째','대리','010-2222',''],['02015','테스트']],
   'BULK탱크DB':[[h for h in SCHEMAS['BULK탱크DB'] if h!='탱크ID']+['거래처명'],['02015']+['']*15+['테스트']],
  }
 def test_two_contacts_and_placeholder_rows(self):
  store=CustomerStore(fake_service(self.tables()),'sid');data=store.read_all()
  self.assertEqual(data['거래처DB'][0]['거래처코드'],'02015')
  self.assertEqual(data['거래처DB'][0]['FAX'],'02-123-4567')
  self.assertEqual([r['성명'] for r in data['거래처연락처DB']],['첫째','둘째'])
  self.assertEqual(data['BULK탱크DB'],[])
 def test_contact_update_preserves_other_contact_and_headers(self):
  tables=self.tables();headers=deepcopy(tables['거래처연락처DB'][0]);store=CustomerStore(fake_service(tables),'sid')
  row=store.read_all()['거래처연락처DB'][1];row['연락처']='010-3333'
  store.save('거래처연락처DB',row,row['연락처ID'])
  self.assertEqual(tables['거래처연락처DB'][0],headers)
  self.assertEqual(tables['거래처연락처DB'][1][4],'010-1111')
  self.assertEqual(tables['거래처연락처DB'][1][7],'010-3333')
 def test_new_contact_does_not_overwrite_prefilled_company_rows(self):
  tables=self.tables();before=deepcopy(tables['거래처연락처DB'][:3]);store=CustomerStore(fake_service(tables),'sid')
  store.save('거래처연락처DB',{'거래처코드':'02015','성명':'신규'})
  self.assertEqual(tables['거래처연락처DB'][:3],before)
  self.assertEqual(tables['거래처연락처DB'][3][2],'신규')
