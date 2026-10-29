"""Customer directory, BULK lease register and responsibilities UI."""
from datetime import date
import hashlib
from html import escape
import uuid
import re
from urllib.parse import urlparse, parse_qs
import pandas as pd
import streamlit as st
from customer_data import SCHEMAS, LABELS, REQUIRED, CHOICES, DATE_FIELDS, LONG_FIELDS, PEOPLE_FIELDS, DEFAULTS, upcoming_tanks
from customer_excel import workbook_bytes, read_workbook

CSS='''<style>
.customer-heading h1{font-size:27px!important;letter-spacing:-.045em;margin:0!important;padding:0!important}
.customer-heading p{font-size:13px;color:#8290a3;margin:8px 0 22px}
.customer-title{font-size:23px;font-weight:750;color:#243b59;overflow-wrap:anywhere;margin:3px 0 12px}
.customer-meta{color:#8190a4;font-size:12px;margin-bottom:20px}
.customer-copy{font-size:13px;line-height:1.8;white-space:pre-wrap;overflow-wrap:anywhere;color:#425773;margin-bottom:16px}
[class*="st-key-customer_pick_"] button{justify-content:flex-start;text-align:left;min-height:42px}
[class*="st-key-customer_pick_"] button p{text-align:left;font-size:13px!important;overflow-wrap:anywhere}
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
 client=drive_client(credential_info,oauth=st.secrets.get('drive_oauth'))
 item=metadata(client,drive_file_id(value))
 if not item['name'].lower().endswith('.xlsx'):
  raise ValueError('작성한 .xlsx 엑셀 파일을 선택해 주세요. Google 스프레드시트는 엑셀로 다운로드 후 올려 주세요.')
 if int(item.get('size',0))>10*1024*1024:
  raise ValueError('엑셀 파일은 10MB 이하만 불러올 수 있습니다.')
 payload=download(client,item)
 read_workbook(payload)
 return item['name'],payload


def show_table(records,sheet,person_label):
 if not records:
  st.info('등록된 정보가 없습니다. 추가 버튼으로 입력할 수 있습니다.');return
 frame=pd.DataFrame(records)[SCHEMAS[sheet]].copy()
 for col in PEOPLE_FIELDS:
  if col in frame:frame[col]=frame[col].map(person_label)
 st.dataframe(frame,hide_index=True,use_container_width=True)


def open_editor(sheet,record=None,code=''):
 st.session_state['customer_editor']={'sheet':sheet,'record':record,'code':code}


def editor(store,data,people,person_label):
 state=st.session_state.get('customer_editor')
 if not state:return
 sheet=state['sheet'];old=state.get('record') or {};headers=SCHEMAS[sheet];key=headers[0]
 def dismiss():st.session_state.pop('customer_editor',None)
 @st.dialog(('수정 · ' if old else '등록 · ')+LABELS[sheet],width='large',on_dismiss=dismiss)
 def dialog():
  initial={**old}
  if not old:
   initial[key]=('C-'+uuid.uuid4().hex[:8].upper()) if sheet=='거래처DB' else ''
   initial['거래처코드']=state['code'] or initial.get('거래처코드','')
  with st.form('customer_form_'+sheet+'_'+str(old.get(key,'new'))):
   fields={}
   for field in headers:
    if field=='수정일':continue
    if field==key and sheet!='거래처DB':
     fields[field]=initial.get(field,'');continue
    if field=='거래처코드' and sheet!='거래처DB':
     fields[field]=state['code'] or initial.get(field,'');st.caption('거래처코드: '+fields[field]);continue
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
   try:store.save(sheet,fields,old.get(key))
   except ValueError as exc:st.error(str(exc))
   except Exception:st.error('저장하지 못했습니다. 연결·권한을 확인한 후 다시 시도하세요. 입력 내용은 유지됩니다.')
   else:
    dismiss();st.session_state['customer_notice']='저장했습니다.';st.rerun()
 dialog()


def related_tab(sheet,code,data,person_label):
 rows=[r for r in data[sheet] if r['거래처코드']==code]
 cols=st.columns([3,1],vertical_alignment='center')
 cols[0].caption(f'{LABELS[sheet]} {len(rows)}건')
 if cols[1].button('추가',key='customer_add_'+sheet,use_container_width=True):
  open_editor(sheet,code=code);st.rerun()
 show_table(rows,sheet,person_label)
 if rows:
  key=SCHEMAS[sheet][0]
  names={'거래처연락처DB':'성명','BULK탱크DB':'탱크번호','거래처특이사항DB':'내용'}
  selected=st.selectbox('수정할 항목',range(len(rows)),format_func=lambda i:(rows[i].get(names[sheet],'') or rows[i][key])[:70]+' · '+rows[i][key][:8],key='customer_modify_pick_'+sheet)
  if st.button('선택 항목 수정',key='customer_modify_'+sheet):
   open_editor(sheet,rows[selected],code);st.rerun()


def render_customers(store,people,person_label,credential_info=None):
 st.markdown(CSS,unsafe_allow_html=True)
 st.markdown('<div class="customer-heading"><h1>거래처 특이사항</h1><p>거래처 정보와 담당자, BULK 탱크, 후속조치를 함께 관리하세요.</p></div>',unsafe_allow_html=True)
 try:data=store.read_all()
 except ValueError as exc:st.error(str(exc));return
 except Exception:st.error('거래처 정보를 불러오지 못했습니다. Google Sheets 연결과 권한을 확인해 주세요.');return
 if st.session_state.get('customer_notice'):st.success(st.session_state.pop('customer_notice'))
 directory,responsibilities,excel=st.tabs(['거래처 관리','직원 담당업무','엑셀 가져오기'])
 with directory:
  customers=data['거래처DB']
  stats=st.columns(4)
  for col,label,count in zip(stats,['전체 거래처','직거래처','대리점','당사 임대 탱크'],[len(customers),sum(r['거래구분']=='직거래처' for r in customers),sum(r['거래구분']=='대리점' for r in customers),sum(r['소유구분']=='당사임대' and r['임대상태']!='회수완료' for r in data['BULK탱크DB'])]):col.metric(label,count)
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
   st.markdown(f'#### 거래처 {len(visible)}')
   with st.container(border=True,height=540):
    if not visible:st.caption('등록된 거래처가 없거나 검색 결과가 없습니다.')
    for r in visible:
     if st.button(r['거래처명'],key='customer_pick_'+r['거래처코드'],use_container_width=True,type='primary' if st.session_state.get('customer_selected')==r['거래처코드'] else 'secondary'):
      st.session_state['customer_selected']=r['거래처코드'];st.rerun()
     st.caption(r['거래구분']+' · '+(person_label(r['당사담당자']) or '담당자 미지정'))
  chosen=next((r for r in visible if r['거래처코드']==st.session_state.get('customer_selected')),visible[0] if visible else None)
  with detail:
   if chosen:
    code=chosen['거래처코드']
    with st.container(border=True):
     st.markdown(f'<div class="customer-title">{escape(chosen["거래처명"])}</div><div class="customer-meta">{escape(chosen["거래구분"])} · {escape(chosen["거래상태"] or "상태 미입력")} · {escape(person_label(chosen["당사담당자"]) or "담당자 미지정")} · {escape(code)}</div>',unsafe_allow_html=True)
     if st.button('거래처 정보 수정',key='customer_edit_main'):open_editor('거래처DB',chosen);st.rerun()
     info,contacts,tanks,notes,work=st.tabs(['회사 정보','연락처','BULK 탱크','특이사항','연결 업무'])
     with info:
      for label in ['업종','회사소개','주요제품','취급가스','공급형태','대표전화','사업장주소','납품주소','결제조건','방문출입주의사항']:
       st.markdown(f'**{label}**')
       st.markdown('<div class="customer-copy">'+escape(chosen[label] or '미입력')+'</div>',unsafe_allow_html=True)
     with contacts:related_tab('거래처연락처DB',code,data,person_label)
     with tanks:related_tab('BULK탱크DB',code,data,person_label)
     with notes:related_tab('거래처특이사항DB',code,data,person_label)
     with work:
      st.caption('업무현황에서 거래처명을 동일하게 입력한 업무를 연결합니다.')
      # The application supplies existing task data separately; this tab never writes it.
      tasks=st.session_state.get('customer_linked_tasks',[])
      related=[r for r in tasks if r.get('거래처','').strip()==chosen['거래처명'].strip()]
      if related:st.dataframe(pd.DataFrame(related)[['업무명','담당자','마감일','진행상태']],hide_index=True,use_container_width=True)
      else:st.info('연결된 업무가 없습니다.')
   else:
    st.info('거래처 등록 또는 엑셀 가져오기로 거래처 정보를 추가해 주세요.')
 with responsibilities:
  st.markdown('#### 직원별 업무와 대체 담당')
  if st.button('담당업무 추가',key='customer_add_staff'):open_editor('직원담당업무DB');st.rerun()
  show_table(data['직원담당업무DB'],'직원담당업무DB',person_label)
  if data['직원담당업무DB']:
   records=data['직원담당업무DB']
   picked=st.selectbox('수정할 담당업무',range(len(records)),format_func=lambda i:person_label(records[i]['직원명'])+' · '+records[i]['담당업무'][:50])
   if st.button('담당업무 수정'):open_editor('직원담당업무DB',records[picked]);st.rerun()
 with excel:
  st.markdown('#### 엑셀 양식으로 한 번에 정리')
  st.caption('거래처코드를 기준으로 연락처·탱크·특이사항을 연결합니다. 원본 양식의 탭 이름과 열 순서를 유지하세요.')
  st.download_button('엑셀 입력 양식 다운로드',template_bytes(),file_name='거래처관리_입력양식.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
  source=st.radio('자료 위치',['Google Drive','내 컴퓨터'],horizontal=True,key='customer_import_source')
  if source=='Google Drive':
   st.caption('Drive에 올린 거래처관리 엑셀의 파일 링크를 복사해 붙여 넣으세요. 연결된 Google 계정에 파일 접근 권한이 있어야 합니다.')
   with st.form('customer_drive_load'):
    link=st.text_input('Google Drive 엑셀 파일 링크',placeholder='https://drive.google.com/file/d/…/view')
    fetch=st.form_submit_button('Drive에서 불러오기')
   if fetch:
    st.session_state.pop('customer_drive_workbook',None)
    try:
     with st.spinner('엑셀 파일을 불러오고 있습니다…'):
      st.session_state['customer_drive_workbook']=load_drive_workbook(link,credential_info)
    except ValueError as exc:st.error(str(exc))
    except Exception:st.error('파일을 불러오지 못했습니다. 파일 링크와 Drive 연결 계정의 접근 권한을 확인해 주세요.')
  uploaded=st.file_uploader('작성한 엑셀 파일',type=['xlsx'],key='customer_import_file_'+str(st.session_state.get('customer_import_version',0))) if source=='내 컴퓨터' else None
  loaded=st.session_state.get('customer_drive_workbook') if source=='Google Drive' else None
  payload=loaded[1] if loaded else (uploaded.getvalue() if uploaded and source=='내 컴퓨터' else None)
  if loaded:st.caption('불러온 파일: '+loaded[0])
  if payload:
   try:
    incoming=read_workbook(payload)
    _,plan=store.plan_import(incoming)
   except ValueError as exc:st.error(str(exc))
   except Exception:st.error('양식 파일을 읽거나 검증하지 못했습니다. 파일과 시트 연결을 확인해 주세요.')
   else:
    count=sum(map(len,plan.values()))
    st.write(f'검증 완료 · 신규 {count}건')
    for sheet,records in plan.items():
     with st.expander(f'{LABELS[sheet]} {len(records)}건 미리보기'):show_table(records,sheet,person_label)
    confirmed=st.checkbox('검증한 신규 자료를 추가합니다. 기존 자료는 덮어쓰지 않습니다.',key='customer_import_confirm_'+hashlib.sha256(payload).hexdigest()[:16])
    if st.button('검증한 자료 추가',type='primary',disabled=not(confirmed and count)):
     try:added=store.import_new(incoming)
     except ValueError as exc:st.error(str(exc))
     except Exception:st.error('반영을 완료하지 못했습니다. 재시도 전에 현재 목록을 확인해 중복 여부를 점검하세요.')
     else:
      st.session_state.pop('customer_drive_workbook',None)
      st.session_state['customer_import_version']=st.session_state.get('customer_import_version',0)+1
      st.session_state['customer_notice']=f'{added}건을 추가했습니다.'
      st.rerun()
  with st.expander('작성 시 참고사항'):
   st.write('BULK 탱크는 한 대당 한 행, 연락처는 한 사람당 한 행으로 작성합니다. 특이사항은 발생 건별로 작성하고 조치담당자·완료예정일을 함께 남기세요.')
   st.caption('엑셀 가져오기는 신규 추가 전용입니다. 기존 자료 수정은 화면에서 진행하세요. 동시 수정은 마지막 저장이 반영될 수 있습니다.')
 editor(store,data,people,person_label)
