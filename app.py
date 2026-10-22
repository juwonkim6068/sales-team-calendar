import calendar
import json
import uuid
from datetime import date, datetime
from html import escape

import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

st.set_page_config(page_title='영업팀 대시보드', page_icon='📊', layout='wide', initial_sidebar_state='expanded')
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap');
:root{--ink:#172641;--muted:#7283a0;--line:#e3eaf3;--blue:#2169ef}
html,body,.stApp,[class*="css"]{font-family:'Noto Sans KR',sans-serif}
.stApp{background:#f8fafd;color:var(--ink)}
.block-container{max-width:1900px;padding:1.65rem 2rem 3rem}
h1,h2,h3{color:#172641!important;letter-spacing:-.04em;font-weight:800!important}
h1{font-size:1.8rem!important;margin-bottom:.2rem!important}
[data-testid="stSidebar"]{background:linear-gradient(155deg,#19273d,#111d30);border-right:0}
[data-testid="stSidebar"] [data-testid="stSidebarContent"]{padding-top:1.5rem}
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3,[data-testid="stSidebar"] p,[data-testid="stSidebar"] label{color:#eaf1ff!important}
[data-testid="stSidebar"] [role="radiogroup"] label{padding:10px 12px;margin:3px 0;border-radius:9px}
[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:#273f62}
[data-testid="stSidebar"] [data-testid="stAlert"]{background:#253750;color:white;border:1px solid #435572}
[data-testid="stSidebar"] button{background:#273b57;color:#fff;border:1px solid #3b506c}
[data-testid="stSidebar"] button:hover{color:white;border-color:#6d9fff}
[data-testid="stVerticalBlockBorderWrapper"],[data-testid="stMetric"]{background:#fff;border:1px solid var(--line)!important;border-radius:11px!important;box-shadow:0 4px 20px rgba(30,55,90,.035)}
[data-testid="stMetric"]{padding:14px 18px}
.stButton button{border-radius:8px;font-weight:700;border-color:#dce4f0;min-height:38px}
.stButton button[kind="primary"],button[kind="primary"]{background:#2169ef;color:white;border-color:#2169ef}
[data-testid="stExpander"]{border-radius:10px;background:white;border:1px solid var(--line)}
[data-testid="stTextInput"] input,[data-testid="stSelectbox"]>div>div,[data-testid="stTextArea"] textarea{border-radius:8px;border-color:#dce5f1}
.dashboard-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:15px}
.dashboard-head h1{margin:0!important}
.dashboard-head p{color:#657895;font-size:13px;margin:4px 0 0}
.cal-shell{background:#fff;border:1px solid #dfe7f1;border-radius:11px;overflow:hidden;box-shadow:0 6px 24px rgba(23,45,77,.04);margin-top:12px}
.cal-weekdays{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));background:#f7f9fc;border-bottom:1px solid #dfe7f1}
.cal-weekdays div{text-align:center;padding:13px 0;color:#506481;font-size:12px;font-weight:700;border-right:1px solid #e2e9f2}
.cal-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr))}
.cal-day{min-height:139px;border-right:1px solid #e2e9f2;border-bottom:1px solid #e2e9f2;padding:10px 8px;min-width:0;background:white}
.cal-day.outside{background:#fafbfd}
.cal-day .day-num{font-size:13px;color:#243754;font-weight:750;margin-bottom:8px}
.cal-day.outside .day-num{color:#a8b6cb}
.cal-day .day-num.today{display:inline-block;background:#2169ef;color:#fff;padding:3px 8px;border-radius:20px}
.cal-event{border-radius:7px;padding:7px 7px 6px;margin:4px 0;font-size:11px;line-height:1.45;overflow:hidden}
.cal-event .event-title{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:700}
.cal-event .event-sub{display:flex;align-items:center;justify-content:space-between;gap:4px;margin-top:5px;font-size:10px}
.cal-event .track{height:5px;border-radius:8px;background:rgba(70,100,145,.13);flex:1;overflow:hidden}
.cal-event .fill{height:100%;border-radius:8px}
.cal-more{font-size:11px;color:#7385a0;margin:5px}
.cal-legend{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:15px;padding:12px 2px;color:#50627e;font-size:12px}
.cal-legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px}
.sidebar-mini{border-top:1px solid #35465d;padding-top:16px;margin-top:20px;color:#e9f0ff}
.sidebar-mini h4{font-size:13px;margin:0 0 9px;color:white}
.sidebar-mini .mini-week{display:grid;grid-template-columns:repeat(7,1fr);gap:4px;text-align:center;font-size:11px;color:#b7c8e2}
.sidebar-mini .mini-week span{padding:5px 0}
.sidebar-mini .mini-week .on{background:#2169ef;border-radius:50%;color:white}
@media(max-width:1050px){.block-container{padding:1rem .7rem}.cal-day{min-height:108px;padding:5px 3px}.cal-event{font-size:9px;padding:4px}.cal-event .event-sub{font-size:9px}}
</style>""",unsafe_allow_html=True)
SID='1cvkG3hyxVyIkMUdcDxUVMZbTPFn0bj0huJ8nTPA-Sko'
TAB='통합업무'
HEAD=['통합ID','원본시트','원본ID','업무명','상세내용','거래처','담당자','업무구분','시작일','마감일','시작시간','진행상태','우선순위','진행률','메모','첨부파일URL','작성일','수정일']
STATES=['미진행','진행중','거의완료','완료','보류']
CATS=['일반업무','거래처 방문','견적/계약','납품/출고','매출마감','미수금/수금','회의','교육','ERP/시스템','기타']

def secrets_credential():
    for k in ('gcp_service_account','google_service_account','service_account'):
        try:
            val=st.secrets.get(k)
            if val:return json.loads(val) if isinstance(val,str) else dict(val)
        except Exception:pass
    try:
        val=st.secrets['gcp']['service_account_json']
        return json.loads(val) if isinstance(val,str) else dict(val)
    except Exception:return None

@st.cache_resource
def api_for(key):
    creds=Credentials.from_service_account_info(json.loads(key),scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return build('sheets','v4',credentials=creds,cache_discovery=False)

def api():
    cred=secrets_credential()
    if not cred:raise RuntimeError('Streamlit Secrets의 Google 서비스 계정 정보를 확인하세요.')
    return api_for(json.dumps(cred,sort_keys=True))

def tab_names(svc):
    meta=svc.spreadsheets().get(spreadsheetId=SID,fields='sheets(properties(title))').execute()
    return [x['properties']['title'] for x in meta.get('sheets',[])]

def read_tab(svc,name,cols='A:R'):
    vals=svc.spreadsheets().values().get(spreadsheetId=SID,range=f"'{name}'!{cols}").execute().get('values',[])
    if not vals:return pd.DataFrame()
    hdr=[str(x).strip() for x in vals[0]]
    data=[dict(zip(hdr,row+['']*(len(hdr)-len(row)))) for row in vals[1:] if any(str(v).strip() for v in row)]
    return pd.DataFrame(data,columns=hdr).fillna('')

def create_tab(svc):
    if TAB not in tab_names(svc):
        svc.spreadsheets().batchUpdate(spreadsheetId=SID,body={'requests':[{'addSheet':{'properties':{'title':TAB}}}]}).execute()
    vals=svc.spreadsheets().values().get(spreadsheetId=SID,range=f"'{TAB}'!A1:R1").execute().get('values',[])
    if not vals:
        svc.spreadsheets().values().update(spreadsheetId=SID,range=f"'{TAB}'!A1:R1",valueInputOption='RAW',body={'values':[HEAD]}).execute()
    elif vals[0]!=HEAD:raise RuntimeError('통합업무 시트의 열 구조가 예상과 달라 작업을 중단했습니다. 기존 내용은 변경하지 않았습니다.')

def safe(v):
    if v is None:return ''
    return str(v).strip()

def canonical_date(v):
    try:
        x=pd.to_datetime(v,errors='coerce')
        return x.strftime('%Y-%m-%d') if pd.notna(x) else ''
    except Exception:return ''

def normalize(row,source):
    r={k:'' for k in HEAD}
    original=safe(row.get('업무ID' if source=='업무일정' else '일정ID'))
    if not original:return None
    r.update({'통합ID':str(uuid.uuid5(uuid.NAMESPACE_URL,f'{SID}/{source}/{original}')),
      '원본시트':source,'원본ID':original,'업무명':safe(row.get('업무명')),
      '상세내용':safe(row.get('상세내용') or row.get('메모')),
      '거래처':safe(row.get('거래처')),'담당자':safe(row.get('담당자')),
      '업무구분':safe(row.get('업무구분')) or '기타',
      '시작일':canonical_date(row.get('발송일') if source=='업무일정' else row.get('시작일')),
      '마감일':canonical_date(row.get('마감일')),
      '시작시간':safe(row.get('시작시간')),'진행상태':safe(row.get('진행상태')) or '미진행',
      '우선순위':safe(row.get('우선순위')) or '보통',
      '진행률':safe(row.get('진행률(%)') if source=='업무일정' else row.get('진행률')) or '0',
      '메모':safe(row.get('확인사항') if source=='업무일정' else row.get('메모')),
      '첨부파일URL':safe(row.get('첨부파일URL')),
      '작성일':safe(row.get('작성일')),'수정일':safe(row.get('최종수정일시') if source=='업무일정' else row.get('수정일'))})
    return r

def append_rows(svc,records):
    if not records:return
    svc.spreadsheets().values().append(spreadsheetId=SID,range=f"'{TAB}'!A:R",valueInputOption='RAW',insertDataOption='INSERT_ROWS',body={'values':[[safe(r.get(k)) for k in HEAD] for r in records]}).execute()

def save_record(svc,record,old_id=None):
    rows=read_tab(svc,TAB)
    if old_id:
        matches=rows.index[rows['통합ID']==old_id].tolist() if not rows.empty else []
        if len(matches)!=1:raise RuntimeError('수정 대상 ID가 없거나 중복되어 저장을 중단했습니다.')
        line=matches[0]+2
        svc.spreadsheets().values().update(spreadsheetId=SID,range=f"'{TAB}'!A{line}:R{line}",valueInputOption='RAW',body={'values':[[safe(record.get(k)) for k in HEAD]]}).execute()
    else:append_rows(svc,[record])

def migration(svc):
    create_tab(svc)
    existing=read_tab(svc,TAB)
    known=set(zip(existing.get('원본시트',pd.Series(dtype=str)),existing.get('원본ID',pd.Series(dtype=str))))
    additions=[];counts={}
    for source in ('업무일정','일정관리'):
        source_df=read_tab(svc,source,'A:P' if source=='업무일정' else 'A:M')
        counts[source]=0
        for row in source_df.to_dict('records'):
            r=normalize(row,source)
            if r and (source,r['원본ID']) not in known:
                additions.append(r);known.add((source,r['원본ID']));counts[source]+=1
    append_rows(svc,additions)
    return counts

def dt(v):
    d=pd.to_datetime(v,errors='coerce')
    return d.date() if pd.notna(d) else None

def form(svc,people,existing=None,key='new'):
    old=existing or {}
    with st.form('edit_'+key):
        title=st.text_input('업무명 *',value=safe(old.get('업무명')))
        detail=st.text_area('상세내용',value=safe(old.get('상세내용')))
        c1,c2,c3=st.columns(3)
        company=c1.text_input('거래처',value=safe(old.get('거래처')))
        options=list(dict.fromkeys(people+([safe(old.get('담당자'))] if safe(old.get('담당자')) else [])))
        options=['미지정']+ [p for p in options if p and p!='미지정']
        owner=c2.selectbox('담당자',options,index=options.index(safe(old.get('담당자'))) if safe(old.get('담당자')) in options else 0)
        cat_options=list(dict.fromkeys(CATS+([safe(old.get('업무구분'))] if safe(old.get('업무구분')) else [])))
        category=c3.selectbox('업무구분',cat_options,index=cat_options.index(safe(old.get('업무구분'))) if safe(old.get('업무구분')) in cat_options else 0)
        c1,c2,c3=st.columns(3)
        start=c1.date_input('시작일',value=dt(old.get('시작일')) or date.today())
        due=c2.date_input('마감일',value=dt(old.get('마감일')) or date.today())
        tm=c3.text_input('시작시간 (HH:MM)',value=safe(old.get('시작시간')))
        c1,c2,c3=st.columns(3)
        state_opts=list(dict.fromkeys(STATES+([safe(old.get('진행상태'))] if safe(old.get('진행상태')) else [])))
        status=c1.selectbox('진행상태',state_opts,index=state_opts.index(safe(old.get('진행상태'))) if safe(old.get('진행상태')) in state_opts else 0)
        priority=c2.selectbox('우선순위',['낮음','보통','높음','긴급'],index=['낮음','보통','높음','긴급'].index(safe(old.get('우선순위'))) if safe(old.get('우선순위')) in ['낮음','보통','높음','긴급'] else 1)
        try:p=int(float(old.get('진행률') or 0))
        except (ValueError,TypeError):p=0
        progress=c3.slider('진행률',0,100,max(0,min(100,p)))
        memo=st.text_area('메모',value=safe(old.get('메모')))
        link=st.text_input('첨부파일 URL',value=safe(old.get('첨부파일URL')))
        if st.form_submit_button('Google Sheets에 저장',type='primary'):
            if not title.strip():st.error('업무명을 입력하세요.');return
            if due<start:st.error('마감일은 시작일 이후여야 합니다.');return
            if tm:
                try:datetime.strptime(tm,'%H:%M')
                except ValueError:st.error('시작시간은 14:00 형식으로 입력하세요.');return
            now=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            rec={k:safe(old.get(k)) for k in HEAD}
            rec.update({'통합ID':safe(old.get('통합ID')) or uuid.uuid4().hex,'원본시트':safe(old.get('원본시트')) or '통합업무',
             '원본ID':safe(old.get('원본ID')) or uuid.uuid4().hex,'업무명':title.strip(),'상세내용':detail,
             '거래처':company,'담당자':'' if owner=='미지정' else owner,'업무구분':category,
             '시작일':start.isoformat(),'마감일':due.isoformat(),'시작시간':tm,'진행상태':status,
             '우선순위':priority,'진행률':str(progress),'메모':memo,'첨부파일URL':link,
             '작성일':safe(old.get('작성일')) or now,'수정일':now})
            try:save_record(svc,rec,safe(old.get('통합ID')) or None);st.success('저장되었습니다.');st.rerun()
            except Exception as exc:st.error(f'저장 실패: {exc}')

def display_table(data):
    cols=['업무명','담당자','업무구분','시작일','마감일','진행상태','진행률','거래처']
    if data.empty:st.info('표시할 업무가 없습니다.')
    else:st.dataframe(data[[x for x in cols if x in data.columns]],hide_index=True,use_container_width=True)

try:svc=api();tabs=tab_names(svc)
except Exception as exc:st.error(f'Google Sheets 연결 실패: {exc}');st.stop()

st.sidebar.markdown('### ▥  영업팀 대시보드')
st.sidebar.divider()
page=st.sidebar.radio('메뉴',['🗓️ 달력','📋 업무현황','📝 회의록','🏢 거래처 특이사항','⚙️ 데이터 통합/설정'],label_visibility='collapsed')
if st.sidebar.button('↻ 데이터 새로고침',use_container_width=True):st.rerun()
if TAB not in tabs:
    st.warning('통합업무 시트가 아직 생성되지 않았습니다. 설정 메뉴에서 최초 통합을 실행하세요.')
    if page!='⚙️ 데이터 통합/설정':st.stop()
    df=pd.DataFrame(columns=HEAD)
else:
    try:
        df=read_tab(svc,TAB)
        if df.empty:df=pd.DataFrame(columns=HEAD)
        if list(df.columns)!=HEAD:raise RuntimeError('통합업무 헤더가 변경되었습니다.')
    except Exception as exc:st.error(str(exc));st.stop()

try:
    team=read_tab(svc,'팀원정보','A:H')
    people=[safe(x) for x in team.get('이름',pd.Series(dtype=str)).tolist() if safe(x)]
except Exception:people=[]
people=list(dict.fromkeys(people+[safe(x) for x in df.get('담당자',pd.Series(dtype=str)).tolist() if safe(x)]))

st.sidebar.caption('Google Sheets 연결 · 기존 원본 보존')
st.sidebar.warning('현재는 공유 편집형입니다. 팀원별 로그인/수정 권한은 아직 적용되지 않았습니다.')
if page=='⚙️ 데이터 통합/설정':
    st.title('데이터 통합 및 설정')
    st.write('원본 업무일정·일정관리 시트는 수정하지 않습니다. 통합업무 시트에만 신규 데이터를 추가합니다.')
    st.info('원본시트 + 원본ID 조합으로 가져온 이력을 식별합니다. 동일 업무처럼 보여도 ID가 다르면 자동 삭제하지 않습니다.')
    if st.button('기존 업무를 통합업무 시트로 가져오기',type='primary'):
        try:
            result=migration(svc)
            st.success('통합 완료: '+', '.join(f'{k} {v}건 신규 반영' for k,v in result.items()))
            st.rerun()
        except Exception as exc:st.error(f'통합 중단: {exc}')
    st.subheader('현재 통합 현황')
    st.metric('통합업무 건수',len(df))
    if not df.empty:st.dataframe(df.groupby('원본시트').size().rename('건수'),use_container_width=True)
else:
    if 'person_filter' not in st.session_state:st.session_state.person_filter='전체'
    choices=['전체']+people
    if st.session_state.person_filter not in choices:st.session_state.person_filter='전체'
    person=st.sidebar.selectbox('담당자 선택',choices,key='person_filter')
    shown=df if person=='전체' else df[df['담당자']==person]
    st.sidebar.markdown(f'<div class="sidebar-mini"><h4>{date.today().year}년 {date.today().month}월</h4></div>',unsafe_allow_html=True)
    mini=calendar.Calendar(firstweekday=6).monthdayscalendar(date.today().year,date.today().month)
    mini_html='<div class="sidebar-mini" style="border:0;padding-top:0"><div class="mini-week">'+''.join(f'<span>{x}</span>' for x in '일월화수목금토')
    for week in mini:
        for d in week:mini_html+=f'<span class={"on" if d==date.today().day else ""}>{d or ""}</span>'
    mini_html+='</div></div>'
    st.sidebar.markdown(mini_html,unsafe_allow_html=True)
    st.sidebar.markdown('#### 팀원 보기')
    st.sidebar.caption('담당자 필터를 변경하면 달력과 업무 목록에 적용됩니다.')
    if page=='🗓️ 달력':
        st.markdown('<div class="dashboard-head"><div><h1>캘린더</h1><p>영업팀의 일정을 한눈에 확인하고 일정을 공유하세요.</p></div></div>',unsafe_allow_html=True)
        if 'month' not in st.session_state:st.session_state.month=date.today().replace(day=1)
        m=st.session_state.month
        left,title,right,todaycol,spacer,add=st.columns([.65,2.2,.65,.85,3.2,1.4],vertical_alignment='center')
        if left.button('❮',key='month_prev',use_container_width=True):
            st.session_state.month=(pd.Timestamp(m)-pd.DateOffset(months=1)).date();st.rerun()
        title.markdown(f'### {m.year}년 {m.month}월')
        if right.button('❯',key='month_next',use_container_width=True):
            st.session_state.month=(pd.Timestamp(m)+pd.DateOffset(months=1)).date();st.rerun()
        if todaycol.button('오늘',use_container_width=True):st.session_state.month=date.today().replace(day=1);st.rerun()
        with add.popover('＋ 일정 추가',use_container_width=True):form(svc,people,key='calendar_new')
        # HTML은 표시 전용이며, 일정 등록·수정은 Streamlit 위젯으로 수행합니다.
        palette=['#377af4','#7b45f4','#f59d26','#27bd6a','#ed6978','#23a8bb','#9861db','#dc8a41']
        def owner_color(owner):
            if not owner:return '#6c87b4'
            return palette[sum(ord(ch) for ch in owner)%len(palette)]
        def pct(row):
            try:return max(0,min(100,int(float(row.get('진행률') or 0))))
            except (ValueError,TypeError):return 0
        def cal_entries(day):
            daystr=day.isoformat()
            d=shown[((shown['시작일']!='')&(shown['시작일']<=daystr)&(shown['마감일']>=daystr))|((shown['시작일']=='')&(shown['마감일']==daystr))]
            return d.sort_values(['시작시간','업무명'],kind='stable')
        html=['<div class="cal-shell"><div class="cal-weekdays">']
        html += [f'<div>{d}</div>' for d in ['일','월','화','수','목','금','토']]
        html.append('</div><div class="cal-grid">')
        weeks=calendar.Calendar(firstweekday=6).monthdatescalendar(m.year,m.month)
        for week in weeks:
            for day in week:
                outside=' outside' if day.month!=m.month else ''
                todaycls=' today' if day==date.today() else ''
                html.append(f'<div class="cal-day{outside}"><div class="day-num{todaycls}">{day.day}</div>')
                daily=cal_entries(day)
                for _,r in daily.head(3).iterrows():
                    owner=safe(r.get('담당자')) or '미지정';color=owner_color(owner)
                    progress=pct(r)
                    # 상태별 강조색, 담당자별 식별 색상은 상단 왼쪽 선에 사용
                    status=safe(r.get('진행상태'))
                    bg='#e9f9f0' if status=='완료' else '#f0ebff' if status=='진행중' else '#eaf2ff' if status=='미진행' else '#fff3e4' if status=='거의완료' else '#f4f6fa'
                    fg='#15934c' if status=='완료' else '#7140db' if status=='진행중' else '#2367d6' if status=='미진행' else '#ae6b13' if status=='거의완료' else '#5e7395'
                    task=escape(safe(r.get('업무명')));owner_html=escape(owner)
                    tm=escape(safe(r.get('시작시간')))
                    html.append(f'<div class="cal-event" title="{task} · {owner_html}" style="background:{bg};color:{fg};border-left:3px solid {color}"><div class="event-title">{tm+" " if tm else ""}{task}</div><div class="event-sub"><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:48%">{owner_html}</span><div class="track"><div class="fill" style="width:{progress}%;background:{fg}"></div></div><b>{progress}%</b></div></div>')
                if len(daily)>3:html.append(f'<div class="cal-more">+ {len(daily)-3}건 더보기</div>')
                html.append('</div>')
        html.append('</div></div>')
        st.markdown(''.join(html),unsafe_allow_html=True)
        if people:
            legend=''.join(f'<span><i style="background:{owner_color(p)}"></i>{escape(p)}</span>' for p in people)
            st.markdown(f'<div class="cal-legend">{legend}</div>',unsafe_allow_html=True)
        st.markdown('#### 날짜별 일정 확인')
        day_choice=st.date_input('확인할 날짜',value=date.today() if date.today().month==m.month and date.today().year==m.year else m,key='calendar_day_select')
        daily=cal_entries(day_choice)
        display_table(daily)
        st.markdown('#### 이번 달 업무 목록')
        month_start=m.isoformat();next_month=(pd.Timestamp(m)+pd.DateOffset(months=1)).date().isoformat()
        month_df=shown[((shown['마감일']>=month_start)&(shown['시작일']<next_month))|((shown['시작일']=='')&(shown['마감일']>=month_start)&(shown['마감일']<next_month))]
        display_table(month_df)
    elif page=='📋 업무현황':
        st.title('업무현황')
        a,b,c=st.columns(3)
        a.metric('조회 업무',len(shown))
        b.metric('진행 중',int(shown['진행상태'].isin(['진행중','거의완료']).sum()))
        c.metric('완료',int((shown['진행상태']=='완료').sum()))
        q=st.text_input('업무명·거래처 검색')
        if q:shown=shown[shown['업무명'].str.contains(q,case=False,regex=False,na=False)|shown['거래처'].str.contains(q,case=False,regex=False,na=False)]
        display_table(shown)
        with st.expander('＋ 업무 추가'):form(svc,people,key='task_new')
    elif page=='📝 회의록':
        st.title('회의록')
        st.info('2차 개발에서 전용 회의록 시트와 작성·수정 화면을 연결합니다. 현재는 업무구분이 회의인 항목을 표시합니다.')
        display_table(shown[shown['업무구분']=='회의'])
    else:
        st.title('거래처 특이사항')
        st.info('2차 개발에서 거래처별 특이사항 기록 기능을 추가합니다. 현재는 거래처가 입력된 업무를 조회할 수 있습니다.')
        display_table(shown[shown['거래처']!=''])
    if page in ('🗓️ 달력','📋 업무현황') and not shown.empty:
        st.subheader('선택 업무 수정')
        # Index is display-only; write target is always resolved by stable 통합ID.
        ids=shown['통합ID'].tolist()
        selected=st.selectbox('수정할 업무',ids,format_func=lambda x: (lambda r:f"{r['업무명']} · {r['담당자']} · {r['마감일']}")(shown[shown['통합ID']==x].iloc[0]))
        with st.expander('✏️ 업무 수정'):form(svc,people,shown[shown['통합ID']==selected].iloc[0].to_dict(),key='modify_'+selected)
