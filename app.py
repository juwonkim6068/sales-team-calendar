"""Public-safe demo. No Google Sheets credentials or production data are used."""
from datetime import date, timedelta
from uuid import uuid4
import calendar
import pandas as pd
import streamlit as st

st.set_page_config(page_title='영업부 일정 | 테스트', page_icon='📅', layout='wide')
st.markdown('''<style>.block-container{max-width:1450px;padding-top:1.5rem} [data-testid="stMetric"]{border:1px solid #d9e3ee;padding:14px;border-radius:12px}</style>''',unsafe_allow_html=True)
TODAY=date.today()
STATES=['예정','진행중','확인필요','보류','완료']
CATS=['회의','교육','거래처','채권관리','마감업무','ERP/시스템','기타']
if 'tasks' not in st.session_state:
    st.session_state.tasks=[
        {'id':'DEMO-001','name':'월간 업무 일정 점검 (예시)','due':TODAY,'owner':'담당자 A','state':'진행중','category':'회의','note':'가상의 테스트 업무입니다.'},
        {'id':'DEMO-002','name':'가마감 자료 확인 (예시)','due':TODAY+timedelta(days=2),'owner':'담당자 B','state':'예정','category':'마감업무','note':'실제 회사 데이터가 아닙니다.'},
        {'id':'DEMO-003','name':'거래처 자료 검토 (예시)','due':TODAY-timedelta(days=1),'owner':'담당자 A','state':'확인필요','category':'거래처','note':'지연 일정 표시 테스트입니다.'},
    ]
if 'comments' not in st.session_state:st.session_state.comments=[]

def dd(t):
    if t['state']=='완료':return '완료'
    d=(t['due']-TODAY).days
    return '지연' if d<0 else '오늘 마감' if d==0 else '마감 임박' if d<=3 else '여유'

def frame(items):
    return pd.DataFrame([{'업무ID':x['id'],'업무명':x['name'],'마감일':str(x['due']),'담당자':x['owner'],'진행상태':x['state'],'마감상태':dd(x),'업무구분':x['category']} for x in items])

st.title('📅 영업부 업무 일정 대시보드')
st.warning('🧪 공개 테스트 버전 · 가상 데이터만 사용 · 입력한 내용은 현재 브라우저 세션에서만 유지되며 Google Sheets에 저장되지 않습니다.')
st.caption('실제 업무자료·거래처명·개인정보는 입력하지 마세요. 링크를 아는 누구나 앱에 접근할 수 있습니다.')
menu=st.sidebar.radio('메뉴',['📊 전체 현황','📋 업무 목록 / 수정','🗓️ 월간 캘린더','⏰ 마감 임박','💬 팀 확인사항','➕ 일정 등록'])
st.sidebar.caption('로그인 없음 · Google Sheets 연결 차단')
items=st.session_state.tasks
if menu=='📊 전체 현황':
    a,b,c,d=st.columns(4)
    a.metric('전체 업무',len(items));b.metric('마감 임박 / 오늘',sum(dd(t) in ('오늘 마감','마감 임박') for t in items));c.metric('지연',sum(dd(t)=='지연' for t in items));d.metric('완료',sum(t['state']=='완료' for t in items))
    st.subheader('우선 확인할 업무')
    priority=sorted([t for t in items if dd(t) in ('지연','오늘 마감','마감 임박')],key=lambda t:t['due'])
    if priority:st.dataframe(frame(priority),hide_index=True,use_container_width=True)
    else:st.info('마감 임박 업무가 없습니다.')
    st.subheader('전체 업무')
    st.dataframe(frame(items),hide_index=True,use_container_width=True)
elif menu in ('📋 업무 목록 / 수정','⏰ 마감 임박'):
    shown=[t for t in items if menu!='⏰ 마감 임박' or dd(t) in ('지연','오늘 마감','마감 임박')]
    q=st.text_input('업무명 검색')
    shown=[t for t in shown if q.lower() in t['name'].lower()]
    if shown:
        st.dataframe(frame(shown),hide_index=True,use_container_width=True)
        chosen=st.selectbox('수정할 업무 선택',[t['id'] for t in shown],format_func=lambda v:next(t['name'] for t in shown if t['id']==v))
        task=next(t for t in items if t['id']==chosen)
        with st.form('edit'):
            name=st.text_input('업무명',task['name']);owner=st.text_input('담당자',task['owner']);due=st.date_input('마감일',task['due']);state=st.selectbox('진행상태',STATES,index=STATES.index(task['state']));note=st.text_area('확인사항',task['note'])
            if st.form_submit_button('테스트 수정 저장'):
                if name.strip():task.update(name=name.strip(),owner=owner,due=due,state=state,note=note);st.rerun()
                else:st.error('업무명을 입력하세요.')
    else:st.info('표시할 업무가 없습니다.')
elif menu=='🗓️ 월간 캘린더':
    c1,c2=st.columns(2);year=c1.number_input('연도',2020,2100,TODAY.year);month=c2.selectbox('월',list(range(1,13)),index=TODAY.month-1)
    st.subheader(f'{year}년 {month}월')
    st.caption('월요일부터 일요일까지의 마감 일정입니다.')
    st.write('월　　화　　수　　목　　금　　토　　일')
    for week in calendar.monthcalendar(year,month):
        cols=st.columns(7)
        for col,day in zip(cols,week):
            with col:
                if day:
                    st.markdown(f'**{day}일**')
                    for t in items:
                        if t['due']==date(year,month,day):st.caption(('✅ ' if t['state']=='완료' else '📌 ')+t['name'][:22])
                else:st.write(' ')
        st.divider()
elif menu=='💬 팀 확인사항':
    if items:
        chosen=st.selectbox('업무 선택',[t['id'] for t in items],format_func=lambda v:next(t['name'] for t in items if t['id']==v))
        rows=[x for x in st.session_state.comments if x['업무ID']==chosen]
        if rows:st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
        else:st.info('등록된 테스트 의견이 없습니다.')
        with st.form('comment'):
            author=st.text_input('작성자 (가명 사용)');msg=st.text_area('의견 (테스트 내용만 입력)')
            if st.form_submit_button('테스트 의견 등록'):
                if author.strip() and msg.strip():st.session_state.comments.append({'업무ID':chosen,'작성자':author,'확인내용':msg});st.rerun()
                else:st.warning('작성자와 내용을 입력하세요.')
elif menu=='➕ 일정 등록':
    with st.form('add'):
        name=st.text_input('업무명 *');owner=st.text_input('담당자 (가명)');due=st.date_input('마감일',TODAY+timedelta(days=7));cat=st.selectbox('업무구분',CATS);note=st.text_area('확인사항')
        if st.form_submit_button('테스트 일정 등록',type='primary'):
            if name.strip():st.session_state.tasks.append({'id':'DEMO-'+uuid4().hex[:8].upper(),'name':name.strip(),'due':due,'owner':owner,'state':'예정','category':cat,'note':note});st.rerun()
            else:st.warning('업무명을 입력하세요.')
st.divider()
if st.button('🔄 테스트 데이터 초기화'):
    del st.session_state.tasks
    st.session_state.comments=[]
    st.rerun()
