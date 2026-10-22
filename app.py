import calendar
import json
import uuid
from datetime import date, datetime, timedelta
from html import escape

import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

st.set_page_config(page_title="영업팀 일정 관리", page_icon="🗓️", layout="wide")
st.markdown('''<style>
.stApp{background:#f4f7fc}
[data-testid="stSidebar"]{background:#15243d}
[data-testid="stSidebar"] *{color:#f0f5ff}
[data-testid="stMetric"]{background:white;border:1px solid #e0e7f2;border-radius:12px;padding:15px}
[data-testid="stVerticalBlockBorderWrapper"]{background:white;border-radius:12px}
.cal{font-weight:750;color:#263d61}
.event{border-radius:6px;padding:5px 7px;margin:4px 0;font-size:12px;overflow-wrap:anywhere}
.todo{background:#e6f0ff;color:#1859a9}
.active{background:#eee8ff;color:#6941c6}
.near{background:#fff0d8;color:#965400}
.done{background:#e3f8eb;color:#137444}
.late{background:#ffe7e8;color:#b42332}
</style>''',unsafe_allow_html=True)

HEADERS=["일정ID","업무명","거래처","담당자","업무구분","시작일","마감일","시작시간","진행상태","진행률","메모","작성일","수정일"]
STATES=["미시작","진행중","거의완료","완료"]
CATS=["일반업무","거래처 방문","견적/계약","납품/출고","매출마감","미수금/수금","회의","기타"]

def service_account():
    for name in ("gcp_service_account","google_service_account","service_account"):
        try:
            obj=st.secrets.get(name)
            if obj:return json.loads(obj) if isinstance(obj,str) else dict(obj)
        except Exception:pass
    try:
        obj=st.secrets["gcp"]["service_account_json"]
        return json.loads(obj) if isinstance(obj,str) else dict(obj)
    except Exception:return None

def spreadsheet_id():
    for name in ("team_calendar","sales_team_calendar"):
        try:
            val=st.secrets[name]["spreadsheet_id"]
            return str(val).split("/d/")[-1].split("/")[0].split("?")[0]
        except Exception:pass
    return ""

@st.cache_resource
def get_api(credential_text):
    credentials=Credentials.from_service_account_info(json.loads(credential_text),
        scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return build("sheets","v4",credentials=credentials,cache_discovery=False)

def connect():
    cred=service_account()
    sid=spreadsheet_id()
    if not cred or not sid:
        raise RuntimeError("Secrets에 [team_calendar] spreadsheet_id 및 서비스 계정이 필요합니다.")
    api=get_api(json.dumps(cred,sort_keys=True))
    meta=api.spreadsheets().get(spreadsheetId=sid,fields="sheets(properties(title,sheetId))").execute()
    tabs=[s["properties"]["title"] for s in meta.get("sheets",[])]
    if "일정관리" not in tabs:
        api.spreadsheets().batchUpdate(spreadsheetId=sid,body={"requests":[{"addSheet":{"properties":{"title":"일정관리"}}}]}).execute()
        api.spreadsheets().values().update(spreadsheetId=sid,range="'일정관리'!A1:M1",
            valueInputOption="RAW",body={"values":[HEADERS]}).execute()
    values=api.spreadsheets().values().get(spreadsheetId=sid,range="'일정관리'!A1:M").execute().get("values",[])
    if values and values[0]!=HEADERS:
        raise RuntimeError("기존 '일정관리' 시트의 헤더가 다릅니다. 기존 데이터를 보호하기 위해 중단했습니다. 현재 헤더: "+str(values[0]))
    rows=[]
    for row_num,row in enumerate(values[1:],2):
        if not any(row):continue
        item=dict(zip(HEADERS,row+[""]*(len(HEADERS)-len(row))))
        item["_row"]=row_num
        rows.append(item)
    return api,sid,pd.DataFrame(rows,columns=HEADERS+["_row"])

def save(record,row=None):
    values=[[str(record.get(k,"")) for k in HEADERS]]
    if row:
        api.spreadsheets().values().update(spreadsheetId=sid,
            range=f"'일정관리'!A{row}:M{row}",valueInputOption="RAW",body={"values":values}).execute()
    else:
        api.spreadsheets().values().append(spreadsheetId=sid,range="'일정관리'!A:M",
            valueInputOption="RAW",insertDataOption="INSERT_ROWS",body={"values":values}).execute()

def to_date(value):
    d=pd.to_datetime(value,errors="coerce")
    return d.date() if pd.notna(d) else None

def state(row):
    if row["진행상태"]=="완료":return "완료"
    d=to_date(row["마감일"])
    return "지연" if d and d<date.today() else (row["진행상태"] or "미시작")

def editor(existing=None,key="new"):
    existing=existing or {}
    with st.form("form_"+key):
        title=st.text_input("업무명 *",value=existing.get("업무명",""))
        a,b,c=st.columns(3)
        company=a.text_input("거래처",value=existing.get("거래처",""))
        person=b.text_input("담당자 *",value=existing.get("담당자",""))
        oldcat=existing.get("업무구분","")
        category=c.selectbox("업무 구분",CATS,index=CATS.index(oldcat) if oldcat in CATS else 0)
        a,b,c=st.columns(3)
        start=a.date_input("시작일",value=to_date(existing.get("시작일")) or date.today())
        due=b.date_input("마감일",value=to_date(existing.get("마감일")) or date.today())
        time=c.text_input("시작 시간",value=existing.get("시작시간",""),placeholder="14:00")
        a,b=st.columns(2)
        oldstate=existing.get("진행상태","미시작")
        progress_state=a.selectbox("진행 상태",STATES,index=STATES.index(oldstate) if oldstate in STATES else 0)
        progress=b.slider("진행률",0,100,int(float(existing.get("진행률") or 0)))
        memo=st.text_area("메모",value=existing.get("메모",""))
        if st.form_submit_button("Google Sheets에 저장",type="primary"):
            if not title.strip() or not person.strip():
                st.warning("업무명과 담당자는 필수입니다.")
            elif due<start:
                st.warning("마감일은 시작일 이후여야 합니다.")
            else:
                now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                record={"일정ID":existing.get("일정ID") or uuid.uuid4().hex,
                    "업무명":title.strip(),"거래처":company.strip(),"담당자":person.strip(),
                    "업무구분":category,"시작일":str(start),"마감일":str(due),
                    "시작시간":time.strip(),"진행상태":progress_state,"진행률":str(progress),
                    "메모":memo,"작성일":existing.get("작성일") or now,"수정일":now}
                try:
                    save(record,existing.get("_row"))
                    st.success("저장 완료")
                    st.rerun()
                except Exception as exc:st.error(f"저장 실패: {exc}")

st.sidebar.title("▣ 영업팀 일정 관리")
page=st.sidebar.radio("메뉴",["🏠 홈","🗓️ 캘린더","📋 업무 현황","🏢 거래처 관리","👥 담당자별 현황","⚙️ 설정"],label_visibility="collapsed")
if st.sidebar.button("🔄 데이터 새로고침",use_container_width=True):st.rerun()
st.sidebar.caption("Google Sheets 저장 / 공유 업무 일정")

try:
    api,sid,df=connect()
except Exception as exc:
    st.error(f"연결 또는 초기화 실패: {exc}")
    st.code('[team_calendar]\nspreadsheet_id = "구글시트_ID"',language="toml")
    st.info("기존 서비스 계정 설정을 유지하고 [team_calendar]를 추가하세요. 서비스 계정을 Google Sheets 편집자로 공유해야 합니다.")
    st.stop()

today=date.today()
people=sorted(v for v in df["담당자"].unique() if v)
companies=sorted(v for v in df["거래처"].unique() if v)

def filters(prefix):
    a,b,c=st.columns([2,1,1])
    query=a.text_input("검색",placeholder="업무명 / 거래처 / 메모",key=prefix+"q")
    person=b.selectbox("담당자",["전체"]+people,key=prefix+"p")
    status=c.selectbox("상태",["전체"]+STATES+["지연"],key=prefix+"s")
    out=df.copy()
    if query:
        mask=pd.Series(False,index=out.index)
        for name in ["업무명","거래처","메모"]:
            mask|=out[name].str.contains(query,case=False,regex=False,na=False)
        out=out[mask]
    if person!="전체":out=out[out["담당자"]==person]
    if status!="전체":out=out[out.apply(state,axis=1)==status]
    return out

def table(data):
    if data.empty:
        st.info("표시할 일정이 없습니다.")
        return
    st.dataframe(data[["마감일","시작시간","업무명","거래처","담당자","업무구분","진행상태","진행률"]],
        hide_index=True,use_container_width=True)

def edit_selection(data,prefix):
    if data.empty:return
    ids=data.index.tolist()
    selected=st.selectbox("수정할 일정 선택",ids,key=prefix,
        format_func=lambda i:f"{data.loc[i,'마감일']} · {data.loc[i,'담당자']} · {data.loc[i,'업무명']}")
    with st.expander("선택 일정 수정"):
        editor(data.loc[selected].to_dict(),key=prefix+str(selected))

if page=="🏠 홈":
    st.title("영업팀 업무 현황")
    incomplete=df[df["진행상태"]!="완료"]
    overdue=incomplete[incomplete.apply(state,axis=1)=="지연"]
    due_today=df[df["마감일"]==str(today)]
    for col,label,value in zip(st.columns(4),["전체 일정","미완료","지연","오늘 마감"],[len(df),len(incomplete),len(overdue),len(due_today)]):
        col.metric(label,f"{value:,}건")
    st.subheader("최근 업무")
    table(df.tail(20))
    with st.expander("＋ 새 일정 등록"):editor(key="home")

elif page=="🗓️ 캘린더":
    st.title("캘린더")
    st.caption("담당자별 일정, 진행률, 거래처 정보를 월간 달력에서 확인합니다.")
    if "cal_month" not in st.session_state:st.session_state["cal_month"]=today.replace(day=1)
    month=st.session_state["cal_month"]
    a,b,c,d=st.columns([1,3,1,1])
    if a.button("❮ 이전"):
        st.session_state["cal_month"]=(month-timedelta(days=1)).replace(day=1);st.rerun()
    b.markdown(f"### {month.year}년 {month.month}월")
    if c.button("다음 ❯"):
        st.session_state["cal_month"]=(month.replace(day=28)+timedelta(days=4)).replace(day=1);st.rerun()
    if d.button("오늘"):
        st.session_state["cal_month"]=today.replace(day=1);st.rerun()
    shown=filters("calendar")
    monthly=shown[shown["마감일"].str.startswith(f"{month.year}-{month.month:02d}-")]
    for col,label,num in zip(st.columns(4),["월간 일정","미완료","지연","완료"],[
        len(monthly),sum(monthly["진행상태"]!="완료"),sum(monthly.apply(state,axis=1)=="지연"),sum(monthly["진행상태"]=="완료")]):
        col.metric(label,f"{num:,}건")
    st.caption("🔵 미시작　🟣 진행중　🟠 거의완료　🟢 완료　🔴 지연")
    for col,weekday in zip(st.columns(7),["일","월","화","수","목","금","토"]):col.markdown(f"**{weekday}**")
    for week in calendar.Calendar(firstweekday=6).monthdatescalendar(month.year,month.month):
        for col,day in zip(st.columns(7,gap="small"),week):
            with col:
                with st.container(border=True):
                    st.markdown(f'<div class="cal">{day.day}</div>',unsafe_allow_html=True)
                    dayrows=shown[shown["마감일"]==day.isoformat()]
                    for _,r in dayrows.head(3).iterrows():
                        cls={"미시작":"todo","진행중":"active","거의완료":"near","완료":"done","지연":"late"}.get(state(r),"todo")
                        label=escape((r["시작시간"]+" "+r["거래처"]+" "+r["업무명"]).strip())
                        st.markdown(f'<div class="event {cls}">{label}<br>{escape(r["담당자"])} · {escape(r["진행률"])}%</div>',unsafe_allow_html=True)
                        if st.button("상세",key=f"detail_{day}_{r['일정ID']}"):
                            st.session_state["selected_id"]=r["일정ID"]
                    if len(dayrows)>3:st.caption(f"+{len(dayrows)-3}건")
                    if dayrows.empty:st.markdown('<div style="height:28px"></div>',unsafe_allow_html=True)
    selected_id=st.session_state.get("selected_id")
    if selected_id and selected_id in df["일정ID"].values:
        with st.expander("선택한 일정 수정",expanded=True):
            row=df[df["일정ID"]==selected_id].iloc[0]
            editor(row.to_dict(),key="cal_selected_"+selected_id)
    with st.expander("＋ 일정 등록"):editor(key="calendar_new")
    st.subheader("월간 전체 일정")
    table(monthly)
    edit_selection(monthly,"calendar_edit")

elif page=="📋 업무 현황":
    st.title("업무 현황")
    shown=filters("tasks")
    table(shown)
    with st.expander("＋ 새 업무 등록"):editor(key="tasks_new")
    edit_selection(shown,"tasks_edit")

elif page=="🏢 거래처 관리":
    st.title("거래처 관리")
    st.caption("현재 일정에 등록된 거래처 기준입니다.")
    if companies:
        company=st.selectbox("거래처",companies)
        chosen=df[df["거래처"]==company]
        st.metric("관련 일정",f"{len(chosen):,}건")
        table(chosen)
        edit_selection(chosen,"company_edit")
    else:st.info("등록된 거래처가 없습니다.")

elif page=="👥 담당자별 현황":
    st.title("담당자별 현황")
    if not df.empty:
        summary=df.groupby("담당자").agg(전체=("일정ID","count"),완료=("진행상태",lambda x:sum(x=="완료"))).reset_index()
        summary["미완료"]=summary["전체"]-summary["완료"]
        st.dataframe(summary,hide_index=True,use_container_width=True)
        table(filters("people"))
    else:st.info("등록된 업무가 없습니다.")

else:
    st.title("설정")
    st.success("Google Sheets 연결 성공")
    st.write("사용 시트: 일정관리")
    st.warning("현재는 공유 편집형입니다. 구글 계정별 로그인과 본인 업무만 수정하는 권한은 구현되어 있지 않습니다.")
    st.caption("기존 시트를 삭제하거나 덮어쓰지 않으며 일정관리 시트가 없을 때만 새로 생성합니다.")
