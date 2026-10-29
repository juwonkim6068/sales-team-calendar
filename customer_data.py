"""Customer schemas and non-destructive Google Sheets storage."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import uuid

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


class CustomerStore:
 def __init__(self, service, spreadsheet_id):
  self.service,self.sid=service,spreadsheet_id

 def read_all(self):
  names={x['properties']['title'] for x in self.service.spreadsheets().get(spreadsheetId=self.sid,fields='sheets(properties(title))').execute().get('sheets',[])}
  result={}
  for sheet,headers in SCHEMAS.items():
   if sheet not in names:
    result[sheet]=[];continue
   values=self.service.spreadsheets().values().get(spreadsheetId=self.sid,range=f"'{sheet}'!A:Z").execute().get('values',[])
   if not values:
    result[sheet]=[];continue
   if values[0]!=headers:raise ValueError(f'{sheet}의 열 구성이 양식과 다릅니다. 기존 데이터 보호를 위해 저장하지 않습니다.')
   rows=[]
   for rownum,row in enumerate(values[1:],2):
    if not any(text_value(v) for v in row):continue
    r=dict(zip(headers,[text_value(v) for v in row]+['']*len(headers)))
    if not r[headers[0]]:raise ValueError(f'{sheet}에 식별코드가 없는 행이 있습니다. 먼저 코드를 입력하세요.')
    r['_row']=rownum
    rows.append(r)
   ids=[r[headers[0]] for r in rows]
   if len(ids)!=len(set(ids)):raise ValueError(f'{sheet}에 중복된 식별코드가 있습니다.')
   result[sheet]=rows
  return result

 def _ensure_sheets(self, requested):
  meta=self.service.spreadsheets().get(spreadsheetId=self.sid,fields='sheets(properties(title))').execute()
  names={x['properties']['title'] for x in meta.get('sheets',[])}
  missing=[sheet for sheet in requested if sheet not in names]
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
   rownum=max((r['_row'] for r in data[sheet]),default=1)+1
  self._ensure_sheets([sheet])
  self.service.spreadsheets().values().batchUpdate(spreadsheetId=self.sid,body={'valueInputOption':'RAW','data':[
   {'range':f"'{sheet}'!A1",'values':[SCHEMAS[sheet]]},
   {'range':f"'{sheet}'!A{rownum}",'values':[[normalized[k] for k in SCHEMAS[sheet]]]}]}).execute()
  return normalized

 def plan_import(self,incoming):
  existing=self.read_all()
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
   updates.extend([{'range':f"'{sheet}'!A1",'values':[SCHEMAS[sheet]]},
                   {'range':f"'{sheet}'!A{max((r['_row'] for r in existing[sheet]),default=1)+1}",'values':[[r[k] for k in SCHEMAS[sheet]] for r in records]}])
  self.service.spreadsheets().values().batchUpdate(spreadsheetId=self.sid,body={'valueInputOption':'RAW','data':updates}).execute()
  return sum(map(len,plan.values()))
