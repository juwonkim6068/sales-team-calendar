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


# 공개 배포에서는 인증되지 않은 사용자에게 회사 시트 데이터를 노출하지 않습니다.
# 로그인 전에는 브라우저 세션 내에서만 유지되는 샘플 데이터로 디자인을 시험합니다.
def demo_rows():
    today = date.today()
    items = [
        ('월간 FC 가마감 예상 매출 확인', '마감업무', '김대리', 2, '진행중', '높음', 65),
        ('거래처별 마감 자료 검토', '거래처', '이차장', -1, '확인필요', '긴급', 80),
        ('영업부 주간회의 준비', '회의', '조부장', 1, '예정', '보통', 0),
        ('미수금 회수 일정 점검', '채권관리', '김대리', 5, '진행중', '높음', 30),
        ('신규 거래처 정보 정리', '거래처', '박사원', 9, '완료', '보통', 100),
        ('월말 비용 결재 확인', '비용처리', '박사원', 12, '예정', '보통', 0),
    ]
    return [dict(zip(['업무ID','업무명','업무구분','담당자','마감일','진행상태','우선순위','진행률(%)','상세내용','확인사항'],
        [f'DEMO-{i:03}',title,cat,owner,(today+timedelta(days=offset)).isoformat(),status,priority,progress,'예시 데이터입니다.','']))
        for i,(title,cat,owner,offset,status,priority,progress) in enumerate(items,1)]


def render_demo():
    import html
    if 'demo_tasks' not in st.session_state:
        st.session_state.demo_tasks = demo_rows()
    if 'demo_comments' not in st.session_state:
        st.session_state.demo_comments = []
    st.markdown("""<style>
    .stApp{background:#edf5fd} .block-container{max-width:1750px;padding-top:.55rem}
    [data-testid="stSidebar"]{background:linear-gradient(160deg,#204d80,#0e294b);border-right:0}
    [data-testid="stSidebar"] *{color:#fff!important}
    [data-testid="stSidebar"] [role="radiogroup"] label{border-radius:7px;padding:10px 12px}
    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:#2d72cc}
    [data-testid="stSidebar"] [role="radiogroup"] label:hover{background:#326398}
    .dash-head{background:linear-gradient(100deg,#092747,#194e82);color:white;padding:18px 23px;border-radius:11px;margin-bottom:12px;display:flex;justify-content:space-between;align-items:center}
    .dash-head h1{color:white!important;margin:0;font-size:1.8rem!important}.dash-head small{color:#d8e8fa}
    .metric-card{background:#fff;border:1px solid #d6e3f1;border-radius:9px;padding:13px 14px;box-shadow:0 2px 7px #183b6010;min-height:110px}
    .metric-label{font-weight:750;font-size:13px;color:#254567}.metric-num{font-size:29px;font-weight:850;color:#132f52;text-align:center;margin:5px 0}.metric-foot{text-align:center;color:#5e7186;font-size:12px}
    .dash-panel{background:white;border:1px solid #d8e5f2;border-radius:9px;padding:12px 13px;margin:8px 0}
    .panel-title{font-size:15px;font-weight:850;color:#163961;margin:0 0 9px}
    .tiny-table{width:100%;border-collapse:collapse;font-size:12px}.tiny-table th{background:#edf4fc;color:#284b75;text-align:left}.tiny-table td,.tiny-table th{padding:8px 7px;border-bottom:1px solid #e8eef6}.tiny-table td{color:#233f5f}
    .tag{display:inline-block;border-radius:5px;padding:3px 7px;font-size:11px;font-weight:750;background:#e4f0ff;color:#2161ae}
    .tag.red{background:#ffe3e7;color:#c42e43}.tag.orange{background:#fff0cc;color:#b76a00}.tag.green{background:#d7f5e8;color:#188453}
    .section-title{font-size:17px;font-weight:850;color:#173b66;margin:13px 0 8px}
    [data-testid="stDataFrame"]{border-radius:8px}
    </style>""",unsafe_allow_html=True)
    menu=['📅 전체 일정','📋 업무 목록','🗓️ 월간 캘린더','⏰ 마감임박 일정','🗒️ 회의 일정','👤 거래처 관련','🧮 ERP / 마감 업무','🎓 교육 / 외부 일정','📁 팀 공유 자료','☑️ 완료된 업무','💬 팀 확인사항','➕ 일정 추가']
    st.sidebar.markdown('### 📅 영업부 업무관리')
    page=st.sidebar.radio('메뉴',menu,label_visibility='collapsed')
    st.sidebar.caption('🧪 디자인 미리보기 · 구글시트 저장 안 됨')
    if st.sidebar.button('🔄 예시 데이터 초기화'):
        st.session_state.demo_tasks=demo_rows();st.session_state.demo_comments=[];st.rerun()
    today=date.today()
    esc=lambda v:html.escape(str(v if v is not None else ''))
    df=pd.DataFrame(st.session_state.demo_tasks)
    df['D-Day']=df['마감일'].apply(lambda x:(date.fromisoformat(str(x))-today).days if x else 99999)
    df['마감상태']=df.apply(lambda r:'완료' if r['진행상태']=='완료' else '지연' if r['D-Day']<0 else '오늘 마감' if r['D-Day']==0 else '마감 임박' if r['D-Day']<=30 else '여유',axis=1)
    st.markdown(f'<div class="dash-head"><h1>🗓️ 영업부 업무 일정 대시보드</h1><small>오늘은 {today.year}년 {today.month}월 {today.day}일 · PSG CHEM</small></div>',unsafe_allow_html=True)
    st.caption('🧪 공개 디자인 테스트 · 아래 자료는 가상 데이터이며 수정 내용은 현재 브라우저에서만 유지됩니다. 실제 회사 정보는 입력하지 마세요.')
    if page=='📅 전체 일정':
        total=len(df);done=int((df['진행상태']=='완료').sum());inprogress=int((df['진행상태']=='진행중').sum());planned=int((df['진행상태']=='예정').sum());urgent=int(((df['D-Day']>=0)&(df['D-Day']<=30)&(df['진행상태']!='완료')).sum())
        cards=[('▦ 전체 일정',total,'등록된 전체 업무','#163961'),('⏰ 마감임박 (D-30)',urgent,'30일 이내 마감','#e83b48'),('⚙ 진행중',inprogress,'처리중인 업무','#e99c00'),('▣ 예정',planned,'예정된 업무','#2165d0'),('✔ 완료',done,'완료된 업무','#1cae7a')]
        cols=st.columns([1,1,1,1,1,1.55],gap='small')
        for c,(label,n,desc,color) in zip(cols[:5],cards):
            with c:st.markdown(f'<div class="metric-card"><div class="metric-label" style="color:{color}">{label}</div><div class="metric-num" style="color:{color}">{n}<span style="font-size:14px">건</span></div><div class="metric-foot">{desc}</div></div>',unsafe_allow_html=True)
        with cols[5]:
            pct=round(done/total*100) if total else 0
            st.markdown(f'<div class="metric-card"><div class="metric-label">이번 달 업무 진행률</div><div class="metric-num" style="font-size:25px">{pct}%</div><div style="height:11px;background:#e6ebf2;border-radius:8px;overflow:hidden"><div style="background:#29bb85;width:{pct}%;height:100%"></div></div><div class="metric-foot">완료 {done}건 / 전체 {total}건</div></div>',unsafe_allow_html=True)
        left,mid,right=st.columns([1.35,1.2,0.9],gap='small')
        with left:
            st.markdown('<div class="section-title">🚨 마감 임박 일정 (D-30 이내)</div>',unsafe_allow_html=True)
            upcoming=df[(df['진행상태']!='완료')&(df['D-Day']<=30)].sort_values('D-Day').head(6)
            rows=''.join(f'<tr><td><span class="tag {"red" if r["D-Day"]<=1 else "orange"}">{"D+"+str(abs(r["D-Day"])) if r["D-Day"]<0 else "D-"+str(r["D-Day"])}</span></td><td>{esc(r["마감일"])}</td><td>{esc(r["업무명"])}</td><td>{esc(r["담당자"])}</td></tr>' for _,r in upcoming.iterrows())
            st.markdown('<div class="dash-panel"><table class="tiny-table"><tr><th>D-Day</th><th>마감일</th><th>업무명</th><th>담당자</th></tr>'+rows+'</table></div>',unsafe_allow_html=True)
        with mid:
            st.markdown('<div class="section-title">⏰ 금주 주요 일정</div>',unsafe_allow_html=True)
            week=df[(df['D-Day']>=0)&(df['D-Day']<=7)&(df['진행상태']!='완료')].sort_values('D-Day').head(6)
            rows=''.join(f'<tr><td>{esc(r["마감일"])}</td><td>{esc(r["업무명"])}</td><td><span class="tag orange">{esc(r["진행상태"])}</span></td></tr>' for _,r in week.iterrows())
            st.markdown('<div class="dash-panel"><table class="tiny-table"><tr><th>날짜</th><th>업무명</th><th>상태</th></tr>'+rows+'</table></div>',unsafe_allow_html=True)
        with right:
            st.markdown(f'<div class="section-title">🗓️ {today.year}년 {today.month}월</div>',unsafe_allow_html=True)
            cal=calendar.monthcalendar(today.year,today.month)
            heads='<tr>'+''.join(f'<th>{x}</th>' for x in ['일','월','화','수','목','금','토'])+'</tr>'
            rows=''
            for weekrow in cal:
                rows+='<tr>'+''.join(f'<td style="text-align:center;{("background:#dceafe;border-radius:50%;font-weight:850" if d==today.day else "")}">{d or ""}</td>' for d in weekrow)+'</tr>'
            st.markdown('<div class="dash-panel"><table class="tiny-table">'+heads+rows+'</table><div style="font-size:11px;color:#627a93;margin-top:8px">● 오늘 기준 · 월간 캘린더 메뉴에서 상세 확인</div></div>',unsafe_allow_html=True)
        st.markdown('<div class="section-title">📋 전체 업무 목록</div>',unsafe_allow_html=True)
        filters=st.columns([1.25,1,1,1,2])
        category=filters[0].selectbox('업무 구분',['전체']+CATEGORIES)
        status=filters[1].selectbox('진행 상태',['전체']+STATES)
        owners=sorted(df['담당자'].dropna().unique().tolist())
        owner=filters[2].selectbox('담당자',['전체']+owners)
        priority=filters[3].selectbox('우선순위',['전체']+PRIORITIES)
        query=filters[4].text_input('업무명 또는 키워드 검색')
        view=df.copy()
        for key,val in [('업무구분',category),('진행상태',status),('담당자',owner),('우선순위',priority)]:
            if val!='전체':view=view[view[key]==val]
        if query:view=view[view['업무명'].str.contains(query,case=False,regex=False)]
        view=view.sort_values('마감일')
        st.dataframe(view[['업무ID','마감일','업무구분','업무명','담당자','진행상태','우선순위','확인사항','마감상태']],hide_index=True,use_container_width=True,height=280)
        c1,c2,c3,c4=st.columns(4,gap='small')
        with c1:
            st.markdown('<div class="section-title">업무 진행 현황</div>',unsafe_allow_html=True)
            if not df.empty:
                fig=px.pie(df,names='진행상태',hole=.64)
                fig.update_layout(height=245,margin=dict(l=0,r=0,t=0,b=0),legend=dict(orientation='h',y=-.15))
                st.plotly_chart(fig,use_container_width=True)
        with c2:
            st.markdown('<div class="section-title">업무 구분별 현황</div>',unsafe_allow_html=True)
            counts=df['업무구분'].value_counts().reset_index();counts.columns=['구분','건수']
            fig=px.bar(counts,x='건수',y='구분',orientation='h',text='건수');fig.update_layout(height=245,margin=dict(l=0,r=0,t=0,b=0),yaxis={'categoryorder':'total ascending'});st.plotly_chart(fig,use_container_width=True)
        with c3:
            st.markdown('<div class="section-title">담당자별 업무 현황</div>',unsafe_allow_html=True)
            counts=df['담당자'].value_counts().reset_index();counts.columns=['담당자','건수']
            fig=px.bar(counts,x='건수',y='담당자',orientation='h',text='건수');fig.update_layout(height=245,margin=dict(l=0,r=0,t=0,b=0),yaxis={'categoryorder':'total ascending'});st.plotly_chart(fig,use_container_width=True)
        with c4:
            st.markdown('<div class="section-title">최근 업데이트</div>',unsafe_allow_html=True)
            st.markdown('<div class="dash-panel"><table class="tiny-table"><tr><th>구분</th><th>내용</th></tr><tr><td>안내</td><td>테스트 데이터 표시 중</td></tr><tr><td>저장</td><td>브라우저 세션 전용</td></tr><tr><td>협업</td><td>로그인 연동 후 활성화</td></tr></table></div>',unsafe_allow_html=True)
    elif page=='🗓️ 월간 캘린더':
        a,b=st.columns(2);yr=int(a.number_input('연도',2020,2100,today.year));mo=int(b.selectbox('월',list(range(1,13)),index=today.month-1))
        st.subheader(f'{yr}년 {mo}월 마감 캘린더')
        for week in calendar.monthcalendar(yr,mo):
            cols=st.columns(7)
            for i,d in enumerate(week):
                with cols[i]:
                    with st.container(border=True):
                        st.markdown(f'**{d or "　"}**')
                        if d:
                            for _,r in df[df['마감일']==f'{yr}-{mo:02d}-{d:02d}'].iterrows():st.caption(('✅ ' if r['진행상태']=='완료' else '📌 ')+str(r['업무명'])[:18])
    elif page=='💬 팀 확인사항':
        st.subheader('💬 팀 확인사항')
        selected=st.selectbox('업무 선택',df['업무ID'].tolist(),format_func=lambda x:next((t['업무명'] for t in st.session_state.demo_tasks if t['업무ID']==x),x))
        comments=[c for c in st.session_state.demo_comments if c['업무ID']==selected]
        if comments:st.dataframe(pd.DataFrame(comments),hide_index=True,use_container_width=True)
        with st.form('demo_comments_new'):
            writer=st.text_input('작성자',value='테스트 사용자');message=st.text_area('확인사항 또는 의견')
            if st.form_submit_button('확인사항 등록',type='primary') and message.strip():
                st.session_state.demo_comments.append({'업무ID':selected,'작성자':writer,'작성일시':datetime.now().strftime('%Y-%m-%d %H:%M'),'확인내용':message});st.rerun()
    elif page=='➕ 일정 추가':
        st.subheader('➕ 신규 일정 등록')
        with st.form('new_demo_task'):
            title=st.text_input('업무명 *');detail=st.text_area('업무 내용')
            a,b,c=st.columns(3);due=a.date_input('마감일',today+timedelta(days=7));owner=b.text_input('담당자',value='담당자 A');cat=c.selectbox('업무 구분',CATEGORIES)
            priority=st.selectbox('우선순위',PRIORITIES,index=2)
            if st.form_submit_button('예시 일정 등록',type='primary'):
                if not title.strip():st.warning('업무명을 입력하세요.')
                else:
                    st.session_state.demo_tasks.append({'업무ID':'DEMO-'+uuid4().hex[:6].upper(),'업무명':title.strip(),'업무구분':cat,'담당자':owner,'마감일':due.isoformat(),'진행상태':'예정','우선순위':priority,'진행률(%)':0,'상세내용':detail,'확인사항':''});st.rerun()
    else:
        subset=df.copy()
        if page=='⏰ 마감임박 일정':subset=subset[(subset['D-Day']<=30)&(subset['진행상태']!='완료')]
        elif page=='☑️ 완료된 업무':subset=subset[subset['진행상태']=='완료']
        elif page=='🗒️ 회의 일정':subset=subset[subset['업무구분']=='회의']
        elif page=='👤 거래처 관련':subset=subset[subset['업무구분'].isin(['거래처','채권관리'])]
        elif page=='🧮 ERP / 마감 업무':subset=subset[subset['업무구분'].isin(['마감업무','ERP/시스템','비용처리'])]
        elif page=='🎓 교육 / 외부 일정':subset=subset[subset['업무구분']=='교육']
        st.subheader(page)
        if page=='📁 팀 공유 자료':st.info('첨부파일 링크 목록은 실제 Google Sheets 연결 이후 활성화할 수 있습니다.')
        st.dataframe(subset[['업무ID','업무명','업무구분','담당자','마감일','진행상태','우선순위','확인사항','마감상태']],hide_index=True,use_container_width=True)
        if page in ['📋 업무 목록','⏰ 마감임박 일정','🗒️ 회의 일정','👤 거래처 관련','🧮 ERP / 마감 업무','🎓 교육 / 외부 일정'] and not subset.empty:
            selected=st.selectbox('수정할 업무 선택',subset['업무ID'].tolist(),format_func=lambda x:next((t['업무명'] for t in st.session_state.demo_tasks if t['업무ID']==x),x))
            item=next(t for t in st.session_state.demo_tasks if t['업무ID']==selected)
            with st.form('edit_demo_task'):
                a,b=st.columns(2)
                new_status=a.selectbox('진행상태',STATES,index=STATES.index(item['진행상태']))
                new_priority=b.selectbox('우선순위',PRIORITIES,index=PRIORITIES.index(item['우선순위']))
                new_owner=st.text_input('담당자',value=item['담당자']);new_due=st.date_input('마감일',date.fromisoformat(item['마감일']));note=st.text_area('확인사항',value=item.get('확인사항',''))
                if st.form_submit_button('예시 업무 수정',type='primary'):
                    item.update({'진행상태':new_status,'우선순위':new_priority,'담당자':new_owner,'마감일':new_due.isoformat(),'확인사항':note});st.rerun()
    st.caption('※ 현재는 공개 테스트 화면입니다. 실제 Google Sheets 저장 및 팀원 로그인은 추후 설정합니다.')

# 로그인 설정이 끝나기 전에는 누구나 예시 화면만 볼 수 있습니다.
try:
    logged_in = bool(st.user.is_logged_in)
except Exception:
    logged_in = False
if not logged_in:
    if 'auth' in st.secrets:
        with st.sidebar:
            if st.button('🔐 팀원 로그인 (추후 설정)'):
                st.login()
    render_demo()
    st.stop()

def configured():
    return all(k in st.secrets for k in ('spreadsheet_id','gcp_service_account','auth','admin_emails'))

if not configured():
    st.error('서버 설정이 완료되지 않았습니다. 관리자에게 Secrets 및 OIDC 설정을 요청하세요.')
    st.stop()

# App authentication is mandatory; do not permit anonymous fallback.
try:
    if not st.user.is_logged_in:
        st.title('🔐 영업부 업무 일정')
        st.info('승인된 회사 구성원만 이용할 수 있습니다.')
        if st.button('회사 계정으로 로그인', type='primary'):
            st.login()
        st.stop()
    email = str(st.user.get('email','')).strip().lower()
    if not email or st.user.get('email_verified') is False:
        st.error('인증된 이메일 주소를 확인할 수 없습니다.')
        st.stop()
except Exception:
    st.error('로그인 설정을 확인할 수 없습니다. 관리자에게 문의하세요.')
    st.stop()

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
    members, _ = fetch('팀원정보', MEMBER)
    admins = {str(x).strip().lower() for x in st.secrets['admin_emails']}
    authorized = members[(members['이메일'].str.strip().str.lower() == email) & (members['사용여부'].str.strip() == '사용')]
    if email not in admins and authorized.empty:
        st.error('로그인은 성공했지만 팀원 접근 권한이 없습니다. 관리자에게 팀원정보 시트 등록을 요청하세요.')
        if st.button('로그아웃'):
            st.logout()
        st.stop()
    username = display_name(authorized.iloc[0]) if not authorized.empty else email
    is_admin = email in admins
    tasks, tasks_ws = fetch('업무일정', TASK)
    comments, comments_ws = fetch('업무확인내역', COMMENT)
    _, history_ws = fetch('변경이력', HISTORY)
except Exception as exc:
    st.error(f'구글시트 연결 또는 권한 확인 오류: {exc}')
    st.stop()

# Stable lookup based on ID, not filtered dataframe index.
def update_task(task_id, changes, reason=''):
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
    data['업무ID'] = 'TASK-' + uuid4().hex[:10].upper()
    data['최종수정일시'] = nowstr()
    tasks_ws.append_row([str(data.get(h,'')) for h in TASK],value_input_option='RAW')
    history_ws.append_row([uuid4().hex[:12],data['업무ID'],nowstr(),email,'업무 생성','','신규 등록',''],value_input_option='RAW')

st.sidebar.title('📅 영업부 일정')
page = st.sidebar.radio('메뉴', ['📊 전체 현황','📋 업무 목록','👥 팀원별 업무','🗓️ 월간 캘린더','⏰ 마감 임박','💬 팀 확인사항','➕ 일정 등록','🕘 변경 이력'])
st.sidebar.divider()
st.sidebar.caption(f'접속자: {username} ({email})')
if st.sidebar.button('🔄 최신 데이터 새로고침'):
    st.rerun()
if st.sidebar.button('로그아웃'):
    st.logout()

st.title('영업부 업무 일정 대시보드')
st.caption(f'조회일 {date.today().isoformat()} · Google Sheets 연결 · 접속자 {username}')
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
        with st.form('comment_form'):
            kind=st.selectbox('확인 유형',['확인요청','의견','진행보고','완료보고'])
            message=st.text_area('내용',placeholder='확인 요청 또는 진행 상황을 작성하세요.')
            state=st.selectbox('처리 상태',['미처리','처리중','완료'])
            assignee=st.text_input('처리 담당자')
            if st.form_submit_button('확인 내용 등록',type='primary'):
                if not message.strip():st.warning('내용을 입력하세요.')
                else:
                    try:
                        comments_ws.append_row([uuid4().hex[:12],task_id,nowstr(),email,kind,message.strip(),state,assignee,'',''],value_input_option='RAW')
                        st.success('등록했습니다.');st.rerun()
                    except Exception as exc:st.error(f'저장 실패: {exc}')

elif page=='➕ 일정 등록':
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
        owner=c4.text_input('담당자',value=username)
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

st.caption('※ 변경 내용은 Google Sheets에 저장됩니다. 동시 수정이 많은 환경에서는 별도 데이터베이스와 트랜잭션 처리를 권장합니다.')
