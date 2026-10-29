"""Customer schemas and non-destructive Google Sheets storage."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import uuid

SCHEMA_VERSION = '20261029-customer-6'

SCHEMAS = {
 '거래처DB': ['거래처코드','거래처명','거래구분','거래상태','당사담당자','업종','회사소개','주요제품','취급가스','공급형태','대표전화','사업장주소','납품주소','결제조건','방문출입주의사항','수정일'],
 '거래처연락처DB': ['연락처ID','거래처코드','부서','직급','성명','담당역할','연락처','이메일','주담당여부','비고','수정일'],
 'BULK탱크DB': ['탱크ID','거래처코드','가스종류','탱크번호','용량','용량단위','소유구분','임대상태','월임대료','계약시작일','계약종료일','최근검사일','차기검사일','설치위치','설비담당자','특이사항','수정일'],
 '거래처특이사항DB': ['특이사항ID','거래처코드','등록일','유형','중요도','내용','후속조치','조치담당자','완료예정일','처리상태','수정일'],
 '직원담당업무DB': ['업무ID','직원명','담당업무','업무구분','주기','협업자','대체담당자','비고','수정일'],
}
LABELS={'거래처DB':'거래처','거래처연락처DB':'연락처','BULK탱크DB':'BULK 탱크','거래처특이사항DB':'특이사항','직원담당업무DB':'직원 담당업무'}
REQUIRED={'거래처DB':['거래처코드','거래처명','거래구분'], '거래처연락처DB':['거래처코드','성명'], 'BULK탱크DB':['거래처코드','가스종류','탱크번호','소유구분'], '거래처특이사항DB':['거래처코드','내용'], '직원담당업무DB':['직원명','담당업무']}
CHOICES={
 '거래구분':['직거래처','대리점'], '거래상태':['거래중','신규검토','거래중단'],
 '공급형태':['BULK','실린더','BULK+실린더','기타'], '담당역할':['구매','생산','설비','안전','결제','기타'], '주담당여부':['예','아니오'],
 '용량단위':['L','m³','ton'], '소유구분':['당사임대','거래처소유','타사임대'], '임대상태':['운영중','회수예정','회수완료'],
 '유형':['영업','공급','설비안전','수금','품질','기타'], '중요도':['일반','중요','긴급'], '처리상태':['미처리','진행중','완료'],
 '업무구분':['영업','납품','설비','안전','수금','사무','기타'], '주기':['상시','매일','매주','매월','수시'],
}
DATE_FIELDS={'계약시작일','계약종료일','최근검사일','차기검사일','등록일','완료예정일'}
LONG_FIELDS={'회사소개','주요제품','취급가스','결제조건','방문출입주의사항','비고','특이사항','내용','후속조치','담당업무'}
PEOPLE_FIELDS={'당사담당자','설비담당자','조치담당자','직원명','대체담당자'}
DEFAULTS={'거래상태':'거래중','등록일':None,'중요도':'일반','처리상태':'미처리','주담당여부':'아니오','임대상태':'운영중','주기':'수시'}


def text_value(value):
 if value is None:return ''
 if isinstance(value,(date,datetime)):return value.date().isoformat() if isinstance(value,datetime) else value.isoformat()
 return str(value).strip()


def normalize_record(sheet, record, customer_codes):
 result={k:text_value(record.get(k)) for k in SCHEMAS[sheet]}
 for field in REQUIRED[sheet]:
  if not result[field]:raise ValueError(f'{LABELS[sheet]}: {field}은(는) 필수입니다.')
 if sheet not in ('거래처DB','직원담당업무DB') and result['거래처코드'] not in customer_codes:
  raise ValueError(f'{sheet}: 등록되지 않은 거래처코드입니다: {result["거래처코드"]}')
 for field,value in result.items():
  if len(value)>20000:raise ValueError(f'{field}: 내용은 20,000자 이내로 입력하세요.')
  if field in CHOICES and value and value not in CHOICES[field]:raise ValueError(f'{field}: 허용된 목록에서 선택해 주세요.')
  if field in DATE_FIELDS and value:
   try:result[field]=date.fromisoformat(value).isoformat()
   except ValueError:raise ValueError(f'{field}: 날짜는 YYYY-MM-DD 형식입니다.') from None
  if field in ('용량','월임대료') and value:
   try:
    amount=Decimal(value)
    if not amount.is_finite() or amount<0:raise InvalidOperation
   except InvalidOperation:raise ValueError(f'{field}: 0 이상의 숫자만 입력하세요.') from None
 if result.get('계약시작일') and result.get('계약종료일') and result['계약종료일']<result['계약시작일']:
  raise ValueError('계약종료일은 계약시작일보다 빠를 수 없습니다.')
 key=SCHEMAS[sheet][0]
 if not result[key]:result[key]=uuid.uuid4().hex
 result['수정일']=datetime.now().isoformat(timespec='seconds')
 return result


def upcoming_tanks(records, today=None):
 today=today or date.today()
 alerts=[]
 for r in records:
  if r.get('임대상태')=='회수완료':continue
  for field in ('계약종료일','차기검사일'):
   try:due=date.fromisoformat(r.get(field,''))
   except ValueError:continue
   days=(due-today).days
   if days<=30:alerts.append((r,field,days))
 return alerts


def owner_customer_summary(customers):
 groups={}
 for row in customers:
  owner=row.get('당사담당자','').strip() or '미지정'
  groups.setdefault(owner,[]).append(row)
 return [
  {'담당자':owner,'담당 거래처':len(rows),
   '직거래처':sum(r.get('거래구분')=='직거래처' for r in rows),
   '대리점':sum(r.get('거래구분')=='대리점' for r in rows),
   '거래처 목록':' · '.join(sorted(r.get('거래처명','') for r in rows))}
  for owner,rows in sorted(groups.items())
 ]


class CustomerStore:
 def __init__(self, service, spreadsheet_id):
  self.service,self.sid=service,spreadsheet_id

 def read_all(self):
  names={x['properties']['title'] for x in self.service.spreadsheets().get(spreadsheetId=self.sid,fields='sheets(properties(title))').execute().get('sheets',[])}
  self._titles={}
  for sheet in SCHEMAS:
   matches=[name for name in names if ''.join(name.split())==sheet]
   if len(matches)>1:raise ValueError(f'{sheet}: 같은 용도의 시트가 여러 개 있습니다. 중복 시트 이름을 확인해 주세요.')
   if matches:self._titles[sheet]=matches[0]
  self.sheet_names=sorted(names)
  self.missing_sheets=[s for s in SCHEMAS if s not in self._titles]
  result={}
  self._available={}
  self._layouts={}
  self._last_rows={}
  for sheet,headers in SCHEMAS.items():
   if sheet not in self._titles:
    result[sheet]=[];continue
   values=self.service.spreadsheets().values().get(spreadsheetId=self.sid,range=self._range(sheet,'A:Z')).execute().get('values',[])
   if not values:
    result[sheet]=[];continue
   actual=[text_value(v) for v in values[0]]
   self._layouts[sheet]=actual
   self._last_rows[sheet]=max((i for i,r in enumerate(values,1) if any(text_value(v) for v in r)),default=1)
   wide=sheet=='거래처연락처DB' and {'거래처코드','성명1','성명2','연락처1','연락처2'}.issubset(actual)
   generated=sheet in ('BULK탱크DB','거래처특이사항DB') and headers[0] not in actual and '거래처코드' in actual
   required=set(headers)-({headers[0]} if generated else set())
   if not wide and not required.issubset(actual):raise ValueError(f'{sheet}의 필수 열이 없습니다. 시트 이름과 열 이름을 확인해 주세요.')
   if len(actual)!=len(set(actual)) or any(not v for v in actual):raise ValueError(f'{sheet}에 비어 있거나 중복된 열 이름이 있습니다.')
   rows=[]
   for rownum,row in enumerate(values[1:],2):
    if not any(text_value(v) for v in row):continue
    raw=dict(zip(actual,[text_value(v) for v in row]+['']*len(actual)))
    slots=(1,2) if wide else (None,)
    for slot in slots:
     r={k:raw.get(k,'') for k in headers}
     if wide:
      for field in ('성명','직급','연락처'):r[field]=raw.get(field+str(slot),'')
      if not any(r[k] for k in ('성명','직급','연락처')):
       self._available.setdefault(sheet,[]).append({'_row':rownum,'_raw':raw,'_slot':slot})
       continue
      r[headers[0]]=f'row-{rownum}-contact-{slot}'
     if generated:
      meaningful=[k for k in headers if k not in (headers[0],'거래처코드','수정일')]
      if not any(r[k] for k in meaningful):
       self._available.setdefault(sheet,[]).append({'_row':rownum,'_raw':raw,'_slot':None})
       continue
      r[headers[0]]=f'row-{rownum}'
     if not r[headers[0]]:raise ValueError(f'{sheet}에 식별코드가 없는 행이 있습니다. 먼저 코드를 입력하세요.')
     r.update({k:v for k,v in raw.items() if k not in headers})
     r.update({'_row':rownum,'_headers':actual,'_raw':raw,'_slot':slot,'_generated':generated})
     rows.append(r)
   ids=[r[headers[0]] for r in rows]
   if len(ids)!=len(set(ids)):raise ValueError(f'{sheet}에 중복된 식별코드가 있습니다.')
   result[sheet]=rows
  return result

 def _range(self,sheet,cells):
  title=getattr(self,'_titles',{}).get(sheet,sheet).replace("'","''")
  return f"'{title}'!{cells}"

 def _ensure_sheets(self, requested):
  meta=self.service.spreadsheets().get(spreadsheetId=self.sid,fields='sheets(properties(title))').execute()
  names={x['properties']['title'] for x in meta.get('sheets',[])}
  missing=[sheet for sheet in requested if getattr(self,'_titles',{}).get(sheet,sheet) not in names]
  if missing:
   self.service.spreadsheets().batchUpdate(spreadsheetId=self.sid,body={'requests':[{'addSheet':{'properties':{'title':s}}} for s in missing]}).execute()

 def save(self,sheet,record,old_id=None):
  data=self.read_all()
  codes={r['거래처코드'] for r in data['거래처DB']}
  normalized=normalize_record(sheet,record,codes)
  key=SCHEMAS[sheet][0]
  ids=[r[key] for r in data[sheet]]
  if old_id:
   if ids.count(old_id)!=1:raise ValueError('수정 대상이 없거나 중복되었습니다.')
   if normalized[key]!=old_id:raise ValueError('기존 식별코드는 변경할 수 없습니다.')
   rownum=data[sheet][ids.index(old_id)]['_row']
  else:
   if normalized[key] in ids:raise ValueError('이미 존재하는 식별코드입니다.')
   rownum=max(max((r['_row'] for r in data[sheet]),default=1),self._last_rows.get(sheet,1))+1
  self._ensure_sheets([sheet])
  reference=data[sheet][ids.index(old_id)] if old_id else next(iter(data[sheet]),{})
  actual=self._layouts.get(sheet,reference.get('_headers',SCHEMAS[sheet]))
  if not data[sheet]:
   present=self.service.spreadsheets().values().get(spreadsheetId=self.sid,range=self._range(sheet,'A:Z')).execute().get('values',[])
   if present:actual=present[0]
   else:self.service.spreadsheets().values().batchUpdate(spreadsheetId=self.sid,body={'valueInputOption':'RAW','data':[{'range':self._range(sheet,'A1'),'values':[actual]}]}).execute()
  reusable=next((r for r in self._available.get(sheet,[]) if r['_raw'].get('거래처코드')==normalized.get('거래처코드')),None) if not old_id else None
  if reusable:
   reference=reusable
   rownum=reusable['_row']
  raw=dict(reference.get('_raw',{})) if old_id or reusable else {}
  slot=reference.get('_slot')
  if not old_id and not reusable and '성명1' in actual:slot=1
  for field,value in normalized.items():
   target=field+str(slot) if slot and field in ('성명','직급','연락처') else field
   if target in actual:raw[target]=value
  if 'FAX' in actual:raw['FAX']=text_value(record.get('FAX',raw.get('FAX','')))
  if '거래처명' in actual and sheet!='거래처DB':
   raw['거래처명']=next((r['거래처명'] for r in data['거래처DB'] if r['거래처코드']==normalized['거래처코드']),raw.get('거래처명',''))
  self.service.spreadsheets().values().batchUpdate(spreadsheetId=self.sid,body={'valueInputOption':'RAW','data':[
   {'range':self._range(sheet,f'A{rownum}'),'values':[[raw.get(k,'') for k in actual]]}]}).execute()
  return normalized

 def plan_import(self,incoming):
  existing=self.read_all()
  for sheet in incoming:
   if self._layouts.get(sheet,SCHEMAS[sheet])!=SCHEMAS[sheet]:
    raise ValueError(f'{sheet}: 사용자 지정 열이 연결되어 있습니다. 기존 시트를 보호하기 위해 엑셀 추가 대신 화면의 등록 기능을 사용해 주세요.')
  codes={r['거래처코드'] for r in existing['거래처DB']}|{text_value(r.get('거래처코드')) for r in incoming.get('거래처DB',[])}
  plan={}
  for sheet,records in incoming.items():
   known={r[SCHEMAS[sheet][0]] for r in existing[sheet]}
   result=[]
   for record in records:
    row=normalize_record(sheet,record,codes)
    key=row[SCHEMAS[sheet][0]]
    if key in known:raise ValueError(f'{sheet}: 중복 코드 {key}입니다. 엑셀 가져오기는 신규 추가만 지원합니다.')
    known.add(key);result.append(row)
   if result:plan[sheet]=result
  return existing,plan

 def import_new(self,incoming):
  existing,plan=self.plan_import(incoming)
  if not plan:raise ValueError('추가할 데이터가 없습니다.')
  self._ensure_sheets(plan)
  updates=[]
  for sheet,records in plan.items():
   updates.extend([{'range':self._range(sheet,'A1'),'values':[SCHEMAS[sheet]]},
                   {'range':self._range(sheet,"A"+str(max((r['_row'] for r in existing[sheet]),default=1)+1)),'values':[[r[k] for k in SCHEMAS[sheet]] for r in records]}])
  self.service.spreadsheets().values().batchUpdate(spreadsheetId=self.sid,body={'valueInputOption':'RAW','data':updates}).execute()
  return sum(map(len,plan.values()))
