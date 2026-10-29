import unittest
from copy import deepcopy
from customer_data import CustomerStore, SCHEMAS, owner_customer_summary
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
 def test_new_contact_reuses_matching_blank_company_row(self):
  tables=self.tables();before=deepcopy(tables['거래처연락처DB'][:3]);store=CustomerStore(fake_service(tables),'sid')
  store.save('거래처연락처DB',{'거래처코드':'02015','성명':'신규'})
  self.assertEqual(tables['거래처연락처DB'][:2],before[:2])
  self.assertEqual(tables['거래처연락처DB'][2][2],'신규')
  self.assertEqual(len(tables['거래처연락처DB']),3)

 def test_owner_summary_comes_from_customers_without_staff_rows(self):
  rows=[{'거래처명':'가','당사담당자':'김주원','거래구분':'직거래처'},
        {'거래처명':'나','당사담당자':'김주원','거래구분':'대리점'}]
  summary=owner_customer_summary(rows)
  self.assertEqual(summary[0]['담당 거래처'],2)
  self.assertEqual(summary[0]['직거래처'],1)
  self.assertEqual(summary[0]['대리점'],1)

 def test_spaced_sheet_title_is_used_for_reads_and_writes(self):
  tables=self.tables()
  tables['거래처 DB']=tables.pop('거래처DB')
  store=CustomerStore(fake_service(tables),'sid')
  row=store.read_all()['거래처DB'][0]
  row['거래처명']='변경'
  store.save('거래처DB',row,row['거래처코드'])
  self.assertEqual(tables['거래처 DB'][1][1],'변경')
  self.assertNotIn('거래처DB',tables)

 def test_second_contact_fills_empty_slot_without_replacing_first(self):
  tables=self.tables()
  tables['거래처연락처DB'][1][5:8]=['','','']
  store=CustomerStore(fake_service(tables),'sid')
  store.save('거래처연락처DB',{'거래처코드':'02015','성명':'추가','연락처':'010-3333'})
  self.assertEqual(tables['거래처연락처DB'][1][2],'첫째')
  self.assertEqual(tables['거래처연락처DB'][1][5],'추가')

 def test_note_uses_existing_customer_row(self):
  tables=self.tables()
  headers=['거래처코드','거래처명']+[h for h in SCHEMAS['거래처특이사항DB'] if h not in ('특이사항ID','거래처코드')]
  tables['거래처특이사항DB']=[headers,['02015','테스트']]
  store=CustomerStore(fake_service(tables),'sid')
  store.save('거래처특이사항DB',{'거래처코드':'02015','내용':'후속조치 확인'})
  self.assertEqual(len(tables['거래처특이사항DB']),2)
  self.assertEqual(tables['거래처특이사항DB'][1][headers.index('내용')],'후속조치 확인')
