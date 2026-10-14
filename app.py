"""PSG 영업부 일정 대시보드: Google Sheets + OIDC, fail-closed authentication."""
from __future__ import annotations
import calendar
from datetime import date, datetime, timedelta
from uuid import uuid4

import gspread
import pandas as pd
import plotly.express as px
import streamlit as st
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="영업부 업무 일정", page_icon="📅", layout="wide", initial_sidebar_state="expanded")
st.markdown("""<style>
:root {--navy:#193c62;--muted:#63758c;--line:#e2eaf2}
.stApp {background:#f8fafc}
.block-container {padding-top:1.2rem;padding-bottom:2.5rem;max-width:1510px}
h1,h2,h3 {color:#193c62;letter-spacing:-.035em}
h1 {font-size:2.05rem!important;font-weight:800!important}
h3 {font-size:1.17rem!important}
[data-testid="stSidebar"] {background:#eef3f9;border-right:1px solid #dce6f0}
[data-testid="stSidebar"] * {color:#223b57!important}
[data-testid="stSidebar"] [role="radiogroup"] label {padding:7px 9px;border-radius:8px}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {background:#dfeaf6}
[data-testid="stMetric"] {background:white;border:1px solid #dce6f0;border-radius:13px;padding:14px 18px;box-shadow:0 2px 10px rgba(28,55,85,.035)}
[data-testid="stMetricLabel"] {color:#64748b}
[data-testid="stMetricValue"] {color:#173a60;font-weight:750}
[data-testid="stDataFrame"] {border:1px solid #e1e8f0;border-radius:11px;overflow:hidden;background:#fff}
[data-testid="stForm"] {background:white;border:1px solid #dce6f0;border-radius:14px;padding:20px}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:14px}
.stButton>button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] {background:#245b98;border-radius:8px}
.section-note {font-size:.91rem;color:#65758a;margin-top:-6px;margin-bottom:14px}
.page-intro {background:white;border:1px solid #e2eaf2;border-radius:14px;padding:19px 23px;margin:4px 0 19px}
.page-intro .eyebrow {font-size:.76rem;color:#527aa4;font-weight:750;letter-spacing:.08em}
.page-intro .main {font-size:1.65rem;color:#193c62;font-weight:800;margin:3px 0}
.page-intro .sub {font-size:.89rem;color:#64748b}
</style>""", unsafe_allow_html=True)

TASK = ['업무ID','발송일','마감일','업무구분','업무명','상세내용','담당자','진행예정자(주/부)','진행상태','우선순위','진행률(%)','확인사항','최종확인자','최종확인일','첨부파일URL','최종수정일시','D-Day','마감구분','비고']
COMMENT = ['확인ID','업무ID','작성일시','작성자','확인유형','확인내용','처리상태','처리담당자','처리완료일','첨부파일URL']
MEMBER = ['팀원ID','이름','부서','직급','담당구분','이메일','사용여부','비고']
HISTORY = ['변경ID','업무ID','변경일시','수정자','변경항목','변경전','변경후','변경사유']
CATEGORIES = ['회의','교육','거래처','채권관리','마감업무','ERP/시스템','비용처리','기타']
STATES = ['예정','진행중','확인필요','보류','완료']
PRIORITIES = ['긴급','높음','보통','낮음']


# 공개 링크 접근: 로그인 없이 조회합니다. Google Sheets 서비스 계정은 서버에서만 사용합니다.
# 공개 수정은 위험하므로 기본적으로 차단합니다. 필요 시 Secrets에 allow_public_edit = true를 설정하세요.
def configured():
    return all(k in st.secrets for k in ('spreadsheet_id', 'gcp_service_account'))

if not configured():
    st.title('📅 영업부 업무 일정 대시보드')
    st.warning('Google Sheets 연결 정보가 아직 없습니다. Streamlit Secrets에 spreadsheet_id와 gcp_service_account를 설정하세요.')
    st.stop()

ALLOW_EDIT = bool(st.secrets.get('allow_public_edit', False))
email = '공개 링크 사용자'
username = '방문자'

@st.cache_resource(show_spinner=False)
def sheet_client():
    creds = Credentials.from_service_account_info(dict(st.secrets['gcp_service_account']), scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return gspread.authorize(creds).open_by_key(st.secrets['spreadsheet_id'])

def tab(name):
    return sheet_client().worksheet(name)

def fetch(name, headers):
    ws = tab(name)
    values = ws.get_all_values()
    if not values:
        raise ValueError(f'{name} 시트에 헤더가 없습니다.')
    missing = [x for x in headers if x not in values[0]]
    if missing:
        raise ValueError(f'{name} 시트 열 누락: {", ".join(missing)}')
    indices = [values[0].index(h) for h in headers]
    rows = [[row[i] if i < len(row) else '' for i in indices] for row in values[1:] if any(v.strip() for v in row)]
    return pd.DataFrame(rows, columns=headers), ws

def nowstr():
    return datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S')

def dateval(value):
    if value is None or str(value).strip() == '':
        return None
    try:
        if str(value).strip().replace('.','',1).isdigit():
            return (datetime(1899,12,30) + timedelta(days=float(value))).date()
        return pd.to_datetime(value, errors='raise').date()
    except Exception:
        return None

def fmt_date(value):
    d = dateval(value)
    return d.isoformat() if d else ''

def deadline(row):
    if str(row.get('진행상태','')).strip() == '완료':
        return '완료', None
    due = dateval(row.get('마감일'))
    if not due:
        return '기한 미기재', None
    days = (due - date.today()).days
    return ('지연' if days < 0 else '오늘 마감' if days == 0 else '마감 임박' if days <= 3 else '여유'), days

def display_name(member):
    return str(member.get('이름','')).strip() or str(member.get('이메일','')).strip()

try:
    tasks, tasks_ws = fetch('업무일정', TASK)
    comments, comments_ws = fetch('업무확인내역', COMMENT)
    _, history_ws = fetch('변경이력', HISTORY)
except Exception as exc:
    st.error(f'Google Sheets 연결 오류: {exc}')
    st.stop()

# Stable lookup based on ID, not filtered dataframe index.
def update_task(task_id, changes, reason=''):
    if not ALLOW_EDIT: raise PermissionError('현재 공개 링크는 조회 전용입니다.')
    ids = tasks_ws.col_values(1)
    if task_id not in ids:
        raise ValueError('업무ID를 찾지 못했습니다. 화면을 새로고침하세요.')
    row_no = ids.index(task_id) + 1
    # Re-read just before writing to reduce stale updates; serialize writes by application if strict consistency is needed.
    header = tasks_ws.row_values(1)
    original = tasks_ws.row_values(row_no)
    old = {h: original[i] if i < len(original) else '' for i,h in enumerate(header)}
    if old.get('업무ID') != task_id:
        raise ValueError('원본 업무가 변경되었습니다. 다시 조회하세요.')
    changes = dict(changes)
    changes['최종수정일시'] = nowstr()
    changed = [(k,old.get(k,''),str(v)) for k,v in changes.items() if str(old.get(k,'')) != str(v)]
    for field,_,new in changed:
        if field in header:
            tasks_ws.update_cell(row_no, header.index(field)+1, new)
    for field,before,after in changed:
        history_ws.append_row([uuid4().hex[:12],task_id,nowstr(),email,field,before,after,reason],value_input_option='RAW')

def append_task(data):
    if not ALLOW_EDIT: raise PermissionError('현재 공개 링크는 조회 전용입니다.')
    data['업무ID'] = 'TASK-' + uuid4().hex[:10].upper()
    data['최종수정일시'] = nowstr()
    tasks_ws.append_row([str(data.get(h,'')) for h in TASK],value_input_option='RAW')
    history_ws.append_row([uuid4().hex[:12],data['업무ID'],nowstr(),email,'업무 생성','','신규 등록',''],value_input_option='RAW')

st.sidebar.title('📅 영업부 일정')
page = st.sidebar.radio('메뉴', ['📊 전체 현황','📋 업무 목록','👥 팀원별 업무','🗓️ 월간 캘린더','⏰ 마감 임박','💬 팀 확인사항','➕ 일정 등록','🕘 변경 이력'])
st.sidebar.divider()
st.sidebar.caption('공개 링크 접속 · ' + ('등록/수정 허용' if ALLOW_EDIT else '조회 전용'))
if st.sidebar.button('🔄 최신 데이터 새로고침'):
    st.rerun()


st.title('영업부 업무 일정 대시보드')
st.caption(f'조회일 {date.today().isoformat()} · Google Sheets 실시간 조회 · 로그인 불필요')
if ALLOW_EDIT:
    st.warning('현재 공개 링크에서 누구나 업무를 등록·수정할 수 있습니다. 링크 외부 유출에 주의하세요.')
if not tasks.empty:
    tasks['발송일'] = tasks['발송일'].map(fmt_date)
    tasks['마감일'] = tasks['마감일'].map(fmt_date)
    tasks['마감상태'] = tasks.apply(lambda r: deadline(r)[0],axis=1)
    tasks['D-Day'] = tasks.apply(lambda r: deadline(r)[1],axis=1)
    tasks['진행률(%)'] = pd.to_numeric(tasks['진행률(%)'],errors='coerce').fillna(0).clip(0,100)
else:
    tasks['마감상태'] = pd.Series(dtype='str')
    tasks['D-Day'] = pd.Series(dtype='float')

if page == '📊 전체 현황':
    total=len(tasks)
    done=int((tasks['진행상태']=='완료').sum())
    urgent=int(tasks['마감상태'].isin(['마감 임박','오늘 마감']).sum())
    late=int((tasks['마감상태']=='지연').sum())
    a,b,c,d,e=st.columns(5)
    a.metric('전체 업무',total);b.metric('마감 임박 / 오늘',urgent);c.metric('지연',late);d.metric('진행중',int((tasks['진행상태']=='진행중').sum()));e.metric('완료율',f'{done/total:.0%}' if total else '0%')
    l,r=st.columns([1.4,1])
    with l:
        st.subheader('🚨 우선 확인할 업무')
        alert=tasks[tasks['마감상태'].isin(['지연','오늘 마감','마감 임박'])].copy()
        alert=alert.sort_values('D-Day',na_position='last')
        st.dataframe(alert[['업무명','담당자','마감일','마감상태','D-Day','진행상태']],hide_index=True,use_container_width=True)
    with r:
        st.subheader('진행 상태별 현황')
        if total:
            count=tasks['진행상태'].replace('','미지정').value_counts().reset_index()
            count.columns=['상태','건수']
            st.plotly_chart(px.pie(count,names='상태',values='건수',hole=.55),use_container_width=True)
    st.subheader('이번 주 마감 일정')
    end=date.today()+timedelta(days=7)
    week=tasks[tasks['마감일'].apply(lambda x: bool(dateval(x) and date.today()<=dateval(x)<=end)) & (tasks['진행상태']!='완료')]
    st.dataframe(week[['마감일','업무명','담당자','진행상태','우선순위']],hide_index=True,use_container_width=True)

elif page == '👥 팀원별 업무':
    st.subheader('👥 팀원별 업무 현황')
    if tasks.empty:
        st.info('등록된 업무가 없습니다.')
    else:
        summary=tasks.groupby('담당자',dropna=False).agg(전체=('업무ID','count'),완료=('진행상태',lambda s:(s=='완료').sum()),진행중=('진행상태',lambda s:(s=='진행중').sum()),지연=('마감상태',lambda s:(s=='지연').sum())).reset_index()
        st.dataframe(summary,hide_index=True,use_container_width=True)
        member=st.selectbox('담당자 선택',['전체']+sorted(tasks['담당자'].dropna().unique().tolist()))
        view=tasks if member=='전체' else tasks[tasks['담당자']==member]
        st.dataframe(view[['업무ID','업무명','업무구분','담당자','마감일','진행상태','우선순위','마감상태']],hide_index=True,use_container_width=True)

elif page in ('📋 업무 목록','⏰ 마감 임박'):
    st.subheader('업무 검색 및 상세 관리')
    f1,f2,f3,f4=st.columns(4)
    keyword=f1.text_input('업무명 검색')
    status=f2.selectbox('진행 상태',['전체']+STATES)
    owner=f3.selectbox('담당자',['전체']+sorted([x for x in tasks['담당자'].unique() if x]))
    category=f4.selectbox('업무 구분',['전체']+CATEGORIES)
    df=tasks.copy()
    if page=='⏰ 마감 임박':df=df[df['마감상태'].isin(['지연','오늘 마감','마감 임박'])]
    if keyword:df=df[df['업무명'].str.contains(keyword,case=False,regex=False,na=False)]
    if status!='전체':df=df[df['진행상태']==status]
    if owner!='전체':df=df[df['담당자']==owner]
    if category!='전체':df=df[df['업무구분']==category]
    st.dataframe(df[['업무ID','마감일','업무구분','업무명','담당자','진행상태','우선순위','진행률(%)','마감상태','D-Day']],hide_index=True,use_container_width=True)
    if not df.empty:
        task_id=st.selectbox('상세 확인 / 수정할 업무',df['업무ID'].tolist(),format_func=lambda x:f'{x} · {tasks.loc[tasks["업무ID"]==x,"업무명"].iloc[0]}')
        item=tasks[tasks['업무ID']==task_id].iloc[0]
        st.info(str(item['상세내용']) or str(item['업무명']))
        if item['비고']:st.caption('비고: '+str(item['비고']))
        if item['첨부파일URL'] and str(item['첨부파일URL']).startswith('https://'):
            st.link_button('📎 첨부파일 열기',str(item['첨부파일URL']))
        if not ALLOW_EDIT:
            st.info('현재는 조회 전용입니다. 등록·수정을 허용하려면 관리자 설정이 필요합니다.')
            st.stop()
        with st.form('update_task'):
            c1,c2,c3=st.columns(3)
            new_status=c1.selectbox('진행상태',STATES,index=STATES.index(item['진행상태']) if item['진행상태'] in STATES else 0)
            new_priority=c2.selectbox('우선순위',PRIORITIES,index=PRIORITIES.index(item['우선순위']) if item['우선순위'] in PRIORITIES else 2)
            new_progress=c3.slider('진행률(%)',0,100,int(item['진행률(%)']))
            new_owner=st.text_input('담당자',str(item['담당자']))
            new_due=st.date_input('마감일',value=dateval(item['마감일']) or date.today())
            new_note=st.text_area('확인사항',str(item['확인사항']))
            reason=st.text_input('수정 사유 (선택)')
            if st.form_submit_button('변경사항 저장',type='primary'):
                try:
                    update_task(task_id,{'진행상태':new_status,'우선순위':new_priority,'진행률(%)':new_progress,'담당자':new_owner,'마감일':new_due.isoformat(),'확인사항':new_note},reason)
                    st.success('저장했습니다.');st.rerun()
                except Exception as exc:st.error(f'저장 실패: {exc}')

elif page=='🗓️ 월간 캘린더':
    a,b=st.columns(2)
    yr=a.number_input('연도',min_value=2020,max_value=2100,value=date.today().year,step=1)
    mo=b.selectbox('월',list(range(1,13)),index=date.today().month-1)
    st.subheader(f'{yr}년 {mo}월 마감 일정')
    month=tasks[tasks['마감일'].str.startswith(f'{yr}-{mo:02d}',na=False)].copy()
    for week in calendar.monthcalendar(int(yr),int(mo)):
        cols=st.columns(7)
        for i,day in enumerate(week):
            with cols[i]:
                if day:
                    d=f'{yr}-{mo:02d}-{day:02d}'
                    st.markdown(f'**{day}일**')
                    for _,item in month[month['마감일']==d].iterrows():
                        st.caption(('✅ ' if item['진행상태']=='완료' else '🔴 ' if item['마감상태']=='지연' else '📌 ')+str(item['업무명'])[:24])
                else:st.write(' ')
        st.divider()

elif page=='💬 팀 확인사항':
    st.subheader('업무별 확인 의견')
    if tasks.empty:st.info('먼저 업무를 등록하세요.')
    else:
        task_id=st.selectbox('업무 선택',tasks['업무ID'].tolist(),format_func=lambda x:f'{x} · {tasks.loc[tasks["업무ID"]==x,"업무명"].iloc[0]}')
        matched=comments[comments['업무ID']==task_id]
        st.dataframe(matched[['작성일시','작성자','확인유형','확인내용','처리상태','처리담당자']],hide_index=True,use_container_width=True)
        if not ALLOW_EDIT:
            st.info('현재는 조회 전용입니다.')
            st.stop()
        with st.form('comment_form'):
            writer=st.text_input('작성자 이름 *')
            kind=st.selectbox('확인 유형',['확인요청','의견','진행보고','완료보고'])
            message=st.text_area('내용',placeholder='확인 요청 또는 진행 상황을 작성하세요.')
            state=st.selectbox('처리 상태',['미처리','처리중','완료'])
            assignee=st.text_input('처리 담당자')
            if st.form_submit_button('확인 내용 등록',type='primary'):
                if not writer.strip() or not message.strip():st.warning('작성자 이름과 내용을 입력하세요.')
                else:
                    try:
                        comments_ws.append_row([uuid4().hex[:12],task_id,nowstr(),writer.strip(),kind,message.strip(),state,assignee,'',''],value_input_option='RAW')
                        st.success('등록했습니다.');st.rerun()
                    except Exception as exc:st.error(f'저장 실패: {exc}')

elif page=='➕ 일정 등록':
    if not ALLOW_EDIT:
        st.info('현재는 조회 전용입니다. 공개 수정 기능은 관리자 설정 후 사용할 수 있습니다.')
        st.stop()
    st.subheader('신규 업무 등록')
    with st.form('new_task'):
        title=st.text_input('업무명 *')
        detail=st.text_area('상세 내용')
        c1,c2=st.columns(2)
        sent=c1.date_input('발송일 / 등록 기준일',date.today())
        has_due=c2.checkbox('마감일 지정',value=True)
        due=c2.date_input('마감일',date.today()+timedelta(days=7),disabled=not has_due)
        c3,c4=st.columns(2)
        cat=c3.selectbox('업무 구분',CATEGORIES)
        owner=c4.text_input('담당자')
        priority=st.selectbox('우선순위',PRIORITIES,index=2)
        note=st.text_area('비고')
        link=st.text_input('첨부파일 URL (선택)')
        if st.form_submit_button('업무 등록',type='primary'):
            if not title.strip():st.warning('업무명을 입력하세요.')
            elif has_due and due<sent:st.warning('마감일이 발송일보다 빠릅니다.')
            else:
                try:
                    append_task({'발송일':sent.isoformat(),'마감일':due.isoformat() if has_due else '', '업무구분':cat,'업무명':title.strip(),'상세내용':detail,'담당자':owner,'진행예정자(주/부)':'','진행상태':'예정','우선순위':priority,'진행률(%)':0,'첨부파일URL':link,'비고':note})
                    st.success('업무를 등록했습니다.');st.rerun()
                except Exception as exc:st.error(f'등록 실패: {exc}')

elif page=='🕘 변경 이력':
    st.subheader('최근 변경 내역')
    try:
        history,_=fetch('변경이력',HISTORY)
        st.dataframe(history.iloc[::-1].head(200),hide_index=True,use_container_width=True)
    except Exception as exc:st.error(f'이력 조회 실패: {exc}')

st.caption('※ 실제 Google Sheets 데이터만 사용합니다. 공개 편집을 켠 경우 변경 내용은 Google Sheets에 저장됩니다. 동시 수정이 많은 환경에서는 별도 데이터베이스와 트랜잭션 처리를 권장합니다.')
