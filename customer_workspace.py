"""Customer directory, BULK lease register and responsibilities UI."""
from datetime import date
import hashlib
import json
from html import escape
import uuid
import re
from urllib.parse import urlparse, parse_qs
import pandas as pd
import streamlit as st
from customer_data import SCHEMAS, LABELS, REQUIRED, CHOICES, DATE_FIELDS, LONG_FIELDS, PEOPLE_FIELDS, DEFAULTS, upcoming_tanks, owner_customer_summary
from customer_excel import workbook_bytes, read_workbook

UI_VERSION = '20261029-customer-7'

CSS='''<style>
.customer-heading h1{font-size:27px!important;letter-spacing:-.045em;margin:0!important;padding:0!important}
.customer-heading p{font-size:13px;color:#8290a3;margin:8px 0 22px}
.customer-title{font-size:23px;font-weight:750;color:#243b59;overflow-wrap:anywhere;margin:3px 0 12px}
.customer-meta{color:#8190a4;font-size:12px;margin-bottom:20px}
.customer-copy{font-size:13px;line-height:1.8;white-space:pre-wrap;overflow-wrap:anywhere;color:#425773;margin-bottom:16px}
[class*="st-key-customer_staff_pick_"] button,[class*="st-key-customer_pick_"] button{justify-content:flex-start;text-align:left;min-height:42px}
[class*="st-key-customer_staff_pick_"] button p,[class*="st-key-customer_pick_"] button p{text-align:left;font-size:13px!important;overflow-wrap:anywhere}
</style>'''


@st.cache_data(show_spinner=False)
def template_bytes():
 return workbook_bytes()


def drive_file_id(value):
 value=value.strip()
 parsed=urlparse(value)
 if parsed.scheme:
  if parsed.scheme!='https' or parsed.hostname not in ('drive.google.com','docs.google.com'):
   raise ValueError('Google Drive 파일의 HTTPS 링크를 입력해 주세요.')
  match=re.search(r'/d/([A-Za-z0-9_-]+)',parsed.path)
  value=match.group(1) if match else parse_qs(parsed.query).get('id',[''])[0]
 if not re.fullmatch(r'[A-Za-z0-9_-]{10,}',value):
  raise ValueError('폴더가 아닌 엑셀 파일의 링크 또는 파일 ID를 입력해 주세요.')
 return value


def load_drive_workbook(value,credential_info):
 from shared_files import drive_client, metadata, download
 oauth=st.secrets.get('drive_oauth')
 if credential_info is None and oauth is None:
  for key in ('gcp_service_account','google_service_account','service_account'):
   value=st.secrets.get(key)
   if value:
    credential_info=json.loads(value) if isinstance(value,str) else dict(value)
    break
  if credential_info is None:
   value=st.secrets.get('gcp',{}).get('service_account_json')
   if value:credential_info=json.loads(value) if isinstance(value,str) else dict(value)
 client=drive_client(credential_info,oauth=oauth)
 item=metadata(client,drive_file_id(value))
 if not item['name'].lower().endswith('.xlsx'):
  raise ValueError('작성한 .xlsx 엑셀 파일을 선택해 주세요. Google 스프레드시트는 엑셀로 다운로드 후 올려 주세요.')
 if int(item.get('size',0))>10*1024*1024:
  raise ValueError('엑셀 파일은 10MB 이하만 불러올 수 있습니다.')
 payload=download(client,item)
 read_workbook(payload)
 return item['name'],payload


def contact_phone_parts(value):
 parts=re.split(r'\s*/\s*|[\r\n]+',str(value or '').strip(),maxsplit=1)
 return (parts[0],parts[1] if len(parts)>1 else '')


def contact_table_rows(records):
 result=[]
 for record in records:
  first,second=contact_phone_parts(record.get('연락처',''))
  result.append({**{field:record.get(field,'') for field in ('부서','직급','성명')},
                 '연락처1':first,'연락처2':second,
                 **{field:record.get(field,'') for field in ('이메일','비고')}})
 return result


def show_table(records,sheet,person_label):
 if not records:
  st.info('등록된 정보가 없습니다. 추가 버튼으로 입력할 수 있습니다.');return
 frame=pd.DataFrame(contact_table_rows(records)) if sheet=='거래처연락처DB' else pd.DataFrame(records)[SCHEMAS[sheet]].copy()
 for col in PEOPLE_FIELDS:
  if col in frame:frame[col]=frame[col].map(person_label)
 st.dataframe(frame,hide_index=True,use_container_width=True)


def open_editor(sheet,record=None,code=''):
 st.session_state['customer_editor']={'sheet':sheet,'record':record,'code':code}


def editor(store,data,people,person_label):
 state=st.session_state.get('customer_editor')
 if not state:return
 sheet=state['sheet'];old=state.get('record') or {};headers=list(SCHEMAS[sheet]);key=headers[0]
 if sheet=='거래처연락처DB':
  headers=[h for h in headers if h not in ('담당역할','주담당여부')]
  i=headers.index('연락처');headers[i:i+1]=['연락처1','연락처2']
 if sheet=='거래처DB' and ('FAX' in old or 'FAX' in getattr(store,'_layouts',{}).get(sheet,[])):headers.insert(headers.index('대표전화')+1,'FAX')
 def dismiss():st.session_state.pop('customer_editor',None)
 @st.dialog(('수정 · ' if old else '등록 · ')+LABELS[sheet],width='large',on_dismiss=dismiss)
 def dialog():
  initial={**old}
  if sheet=='거래처연락처DB':initial['연락처1'],initial['연락처2']=contact_phone_parts(old.get('연락처',''))
  if not old:
   initial[key]=('C-'+uuid.uuid4().hex[:8].upper()) if sheet=='거래처DB' else ''
   initial['거래처코드']=state['code'] or initial.get('거래처코드','')
  with st.form('customer_form_'+sheet+'_'+str(old.get(key,'new'))):
   fields={}
   for field in headers:
    if field=='수정일':continue
    if field==key and sheet=='거래처DB' and not old:
     fields[field]=initial[field];continue
    if field==key and sheet!='거래처DB':
     fields[field]=initial.get(field,'');continue
    if field=='거래처코드' and sheet!='거래처DB':
     fields[field]=state['code'] or initial.get(field,'')
     if sheet!='거래처연락처DB':st.caption('거래처코드: '+fields[field])
     continue
    value=initial.get(field,DEFAULTS.get(field,'')) or ''
    label=field+(' *' if field in REQUIRED[sheet] else '')
    if field in DATE_FIELDS:
     try:default=date.fromisoformat(value) if value else (date.today() if field=='등록일' else None)
     except ValueError:default=None
     chosen=st.date_input(label,value=default,key='cf_'+sheet+'_'+field)
     fields[field]=chosen.isoformat() if chosen else ''
    elif field in CHOICES:
     opts=['']+CHOICES[field]
     if value and value not in opts:opts.append(value)
     fields[field]=st.selectbox(label,opts,index=opts.index(value) if value in opts else 0,format_func=lambda x:x or '선택',key='cf_'+sheet+'_'+field)
    elif field in PEOPLE_FIELDS:
     opts=list(dict.fromkeys(['']+people+([value] if value else [])))
     fields[field]=st.selectbox(label,opts,index=opts.index(value) if value in opts else 0,format_func=lambda x:person_label(x) if x else '선택',key='cf_'+sheet+'_'+field)
    elif field in LONG_FIELDS:
     fields[field]=st.text_area(label,value=value,height=85,key='cf_'+sheet+'_'+field)
    else:
     fields[field]=st.text_input(label,value=value,disabled=bool(old and field==key),key='cf_'+sheet+'_'+field)
   if sheet=='BULK탱크DB':st.caption('금액·용량은 숫자로 입력하세요. 검사일은 안전관리자가 확인한 날짜를 입력하며 법정주기를 자동 산정하지 않습니다.')
   submitted=st.form_submit_button('저장',type='primary',use_container_width=True)
  if submitted:
   if sheet=='거래처연락처DB':
    fields['연락처']=' / '.join(fields[field].strip() for field in ('연락처1','연락처2') if fields[field].strip())
    fields['담당역할']=old.get('담당역할','')
    fields['주담당여부']=old.get('주담당여부','')
   try:store.save(sheet,fields,old.get(key))
   except ValueError as exc:st.error(str(exc))
   except Exception:st.error('저장하지 못했습니다. 연결·권한을 확인한 후 다시 시도하세요. 입력 내용은 유지됩니다.')
   else:
    dismiss();st.session_state['customer_notice']='저장했습니다.';st.rerun()
 dialog()


def related_tab(sheet,code,data,person_label,prefix="directory"):
 rows=[r for r in data[sheet] if r['거래처코드']==code]
 cols=st.columns([3,1],vertical_alignment='center')
 cols[0].caption(f'{LABELS[sheet]} {len(rows)}건')
 if cols[1].button('추가',key='customer_add_'+prefix+sheet,use_container_width=True):
  open_editor(sheet,code=code);st.rerun()
 show_table(rows,sheet,person_label)
 if rows:
  key=SCHEMAS[sheet][0]
  names={'거래처연락처DB':'성명','BULK탱크DB':'탱크번호','거래처특이사항DB':'내용'}
  selected=st.selectbox('수정할 항목',range(len(rows)),format_func=lambda i:((rows[i].get('성명') or '이름 미입력')+' · '+(rows[i].get('직급') or rows[i].get('부서') or '연락처')) if sheet=='거래처연락처DB' else (rows[i].get(names[sheet],'') or rows[i][key])[:70]+' · '+rows[i][key][:8],key='customer_modify_pick_'+prefix+sheet)
  if st.button('선택 항목 수정',key='customer_modify_'+prefix+sheet):
   open_editor(sheet,rows[selected],code);st.rerun()


def customer_snapshot(data):
 return hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()


def watch_customer_changes(store,data):
 baseline=customer_snapshot(data)
 first=True
 @st.fragment(run_every='30s')
 def watch():
  nonlocal first
  if first:
   first=False
   return
  if st.session_state.get('customer_editor'):
   st.caption('작성 중 · 입력을 마친 뒤 최신 시트를 반영합니다.')
   return
  try:latest=store.read_all()
  except Exception:
   st.caption('자동 갱신 대기 · 연결을 다시 확인하고 있습니다.')
   return
  if customer_snapshot(latest)!=baseline:st.rerun(scope='app')
  # No layout changes when the data has not changed.
 watch()


def customer_detail(chosen,data,person_label,prefix="directory"):
 if chosen:
  code=chosen['거래처코드']
  with st.container(border=True):
   st.markdown(f'<div class="customer-title">{escape(chosen["거래처명"])}</div><div class="customer-meta">{escape(chosen["거래구분"])} · {escape(chosen["거래상태"] or "상태 미입력")} · {escape(person_label(chosen["당사담당자"]) or "담당자 미지정")} · {escape(code)}</div>',unsafe_allow_html=True)
   if st.button('거래처 정보 수정',key='customer_edit_main_'+prefix):open_editor('거래처DB',chosen);st.rerun()
   info,contacts,tanks,notes,work=st.tabs(['회사 정보','연락처','BULK 탱크','특이사항','연결 업무'])
   with info:
    for label in ['업종','회사소개','주요제품','취급가스','공급형태','대표전화','FAX','사업장주소','납품주소','결제조건','방문출입주의사항']:
     st.markdown(f'**{label}**')
     st.markdown('<div class="customer-copy">'+escape(chosen.get(label,'') or '미입력')+'</div>',unsafe_allow_html=True)
   with contacts:related_tab('거래처연락처DB',code,data,person_label,prefix)
   with tanks:related_tab('BULK탱크DB',code,data,person_label,prefix)
   with notes:related_tab('거래처특이사항DB',code,data,person_label,prefix)
   with work:
    st.caption('업무현황에서 거래처명을 동일하게 입력한 업무를 연결합니다.')
    # The application supplies existing task data separately; this tab never writes it.
    tasks=st.session_state.get('customer_linked_tasks',[])
    related=[r for r in tasks if r.get('거래처','').strip()==chosen['거래처명'].strip()]
    if related:st.dataframe(pd.DataFrame(related)[['업무명','담당자','마감일','진행상태']],hide_index=True,use_container_width=True)
    else:st.info('연결된 업무가 없습니다.')
 else:
  st.info('거래처 등록 버튼으로 정보를 입력하면 저장 후 바로 조회할 수 있습니다.')


def render_customers(store,people,person_label,credential_info=None):
 st.markdown(CSS,unsafe_allow_html=True)
 header,refresh=st.columns([5,1],vertical_alignment='center')
 with header:
  st.markdown('<div class="customer-heading"><h1>거래처 관리</h1><p>거래처를 등록하고 연락처·탱크·특이사항을 한곳에서 관리하세요.</p></div>',unsafe_allow_html=True)
 if refresh.button('새로고침',key='customer_sheet_refresh',use_container_width=True):st.rerun()
 try:data=store.read_all()
 except ValueError as exc:st.error(str(exc));return
 except Exception:st.error('거래처 정보를 불러오지 못했습니다. Google Sheets 연결과 권한을 확인해 주세요.');return
 if isinstance(getattr(store.service,"read_status",None),str) and store.service.read_status:st.warning(store.service.read_status)
 watch_customer_changes(store,data)
 if st.session_state.get('customer_notice'):st.success(st.session_state.pop('customer_notice'))
 directory,responsibilities=st.tabs(['거래처 관리','직원 담당업무'])
 with directory:
  customers=data['거래처DB']
  controls=st.columns([2.5,1,1.3,1.1],vertical_alignment='bottom')
  query=controls[0].text_input('거래처 검색',placeholder='상호·업종·제품·가스·주소 검색')
  category=controls[1].selectbox('거래구분',['전체','직거래처','대리점'])
  owners=list(dict.fromkeys(people+[r['당사담당자'] for r in customers if r['당사담당자']]))
  owner=controls[2].selectbox('당사 담당자',['전체']+owners,format_func=person_label)
  if controls[3].button('거래처 등록',type='primary',use_container_width=True):open_editor('거래처DB');st.rerun()
  visible=[r for r in customers if (category=='전체' or r['거래구분']==category) and (owner=='전체' or r['당사담당자']==owner) and (not query.strip() or query.strip().casefold() in ' '.join(r.get(k,'') for k in SCHEMAS['거래처DB']).casefold())]
  visible.sort(key=lambda r:r['거래처명'])
  alerts=upcoming_tanks(data['BULK탱크DB'])
  if alerts:
   with st.expander(f'확인 필요 · 계약종료/검사일 30일 이내 또는 경과 {len(alerts)}건'):
    names={r['거래처코드']:r['거래처명'] for r in customers}
    st.dataframe([{'거래처':names.get(r['거래처코드'],r['거래처코드']),'탱크번호':r['탱크번호'],'항목':field,'예정일':r[field],'남은 일수':days} for r,field,days in alerts],hide_index=True,use_container_width=True)
    st.caption('입력된 날짜 기준입니다. 법정 검사주기나 적합 여부를 자동 판단하지 않습니다.')
  listing,detail=st.columns([1.1,2.9],gap='large')
  with listing:
   st.markdown('#### 거래처 목록')
   with st.container(border=True,height=540):
    if not visible:st.caption('등록된 거래처가 없거나 검색 결과가 없습니다.')
    for r in visible:
     if st.button(r['거래처명'],key='customer_pick_'+r['거래처코드'],use_container_width=True,type='primary' if st.session_state.get('customer_selected')==r['거래처코드'] else 'secondary'):
      st.session_state['customer_selected']=r['거래처코드'];st.rerun()
     st.caption(r['거래구분']+' · '+(person_label(r['당사담당자']) or '담당자 미지정'))
  chosen=next((r for r in visible if r['거래처코드']==st.session_state.get('customer_selected')),visible[0] if visible else None)
  with detail:
   customer_detail(chosen,data,person_label)
 with responsibilities:
  st.markdown('#### 담당 거래처 조회')
  filter_cols=st.columns([1,2])
  owner_options=list(dict.fromkeys(people+[r['당사담당자'] for r in data['거래처DB'] if r['당사담당자']]))
  staff_owner=filter_cols[0].selectbox('담당자',['전체']+owner_options,format_func=person_label,key='customer_staff_owner')
  staff_search=filter_cols[1].text_input('거래처명 검색',placeholder='찾으실 거래처명을 입력하세요',key='customer_staff_search')
  staff_rows=sorted([r for r in data['거래처DB'] if (staff_owner=='전체' or r['당사담당자']==staff_owner) and staff_search.strip().casefold() in r['거래처명'].casefold()],key=lambda r:r['거래처명'])
  staff_list,staff_detail=st.columns([1.2,2.8],gap='large')
  with staff_list:
   st.markdown('##### 거래처 목록')
   with st.container(border=True,height=480):
    if not staff_rows:st.caption('조건에 맞는 거래처가 없습니다.')
    for row in staff_rows:
     if st.button(row['거래처명'],key='customer_staff_pick_'+row['거래처코드'],use_container_width=True,type='primary' if st.session_state.get('customer_staff_selected')==row['거래처코드'] else 'secondary'):
      st.session_state['customer_staff_selected']=row['거래처코드'];st.rerun()
  staff_chosen=next((r for r in staff_rows if r['거래처코드']==st.session_state.get('customer_staff_selected')),staff_rows[0] if staff_rows else None)
  with staff_detail:customer_detail(staff_chosen,data,person_label,"staff")
  st.markdown('#### 별도 담당업무와 대체 담당')
  if st.button('담당업무 추가',key='customer_add_staff'):open_editor('직원담당업무DB');st.rerun()
  if data['직원담당업무DB']:show_table(data['직원담당업무DB'],'직원담당업무DB',person_label)
  else:st.caption('직원담당업무DB에 별도로 작성된 업무는 없습니다. 담당 거래처는 위 목록에서 확인할 수 있습니다.')
  if data['직원담당업무DB']:
   records=data['직원담당업무DB']
   picked=st.selectbox('수정할 담당업무',range(len(records)),format_func=lambda i:person_label(records[i]['직원명'])+' · '+records[i]['담당업무'][:50])
   if st.button('담당업무 수정'):open_editor('직원담당업무DB',records[picked]);st.rerun()
 with st.expander('연결 설정'):
  st.caption('연결 문서: '+store.sid+' · 화면 버전 '+UI_VERSION)
  st.dataframe([{'시트':name,'상태':'시트 없음' if name in getattr(store,'missing_sheets',[]) else '연결됨','읽은 건수':len(rows)} for name,rows in data.items()],hide_index=True,use_container_width=True)
  if getattr(store,'missing_sheets',[]):
   st.warning('찾지 못한 시트: '+', '.join(store.missing_sheets))
   st.write('현재 문서의 시트 이름: '+', '.join(getattr(store,'sheet_names',[])))
 editor(store,data,people,person_label)
