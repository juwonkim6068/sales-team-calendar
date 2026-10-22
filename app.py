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


st.markdown("""<style>
.block-container{max-width:1700px;padding-top:1.5rem;padding-bottom:3rem}
[data-testid="stSidebar"]{background:linear-gradient(155deg,#15233b,#101b2e)}
[data-testid="stSidebar"] [data-testid="stRadio"] label{color:#e6eeff}
[data-testid="stSidebar"] button{border-radius:9px}
h1,h2,h3{color:#142846;letter-spacing:-.03em}
[data-testid="stVerticalBlockBorderWrapper"]{border-color:#e1e8f3}
[data-testid="stButton"] button[kind="primary"]{background:#1769ec}
div[data-testid="stMetric"]{box-shadow:0 4px 16px rgba(22,46,81,.04)}
</style>""",unsafe_allow_html=True)

def person_palette(name):
    palette=["#3b82f6","#a78bfa","#fb923c","#fb7185","#34d399","#60a5fa","#fbbf24","#c084fc","#2dd4bf"]
    return palette[sum(ord(ch) for ch in str(name))%len(palette)]

def month_shift(first,delta):
    y=first.year+(first.month-1+delta)//12
    m=(first.month-1+delta)%12+1
    return date(y,m,1)

def calendar_card(row):
    stat=state(row)
    bg,fg={
        "미시작":("#eaf2ff","#1556a8"),
        "진행중":("#eae8ff","#6941c6"),
        "거의완료":("#fff1dd","#a15d00"),
        "완료":("#e4f8eb","#137e46"),
        "지연":("#ffe8ea","#b42332")
    }.get(stat,("#eaf2ff","#1556a8"))
    title=escape(str(row.get("업무명","")))
    company=escape(str(row.get("거래처","")))
    owner=escape(str(row.get("담당자","")))
    tm=escape(str(row.get("시작시간","")))
    try: progress=max(0,min(100,int(float(row.get("진행률") or 0))))
    except (ValueError,TypeError):progress=0
    return f"""<div style="background:{bg};border-radius:8px;padding:7px 8px;margin:5px 0;color:{fg};font-size:12px;line-height:1.45">
      <div style="font-weight:700">{tm} {title}</div>
      <div style="font-size:11px;opacity:.8">{company or '내부업무'} · {owner}</div>
      <div style="display:flex;align-items:center;gap:5px;margin-top:4px">
       <div style="height:5px;border-radius:5px;background:#ffffffa8;flex:1;overflow:hidden"><div style="height:5px;width:{progress}%;background:{fg}"></div></div>
       <span style="font-size:10px">{progress}%</span></div></div>"""


st.sidebar.markdown("## 📊 영업팀 일정 관리")
page=st.sidebar.radio("관리 메뉴",["🏠 홈","🗓️ 캘린더","📋 업무 현황","🏢 거래처 관리","👥 담당자별 현황","⚙️ 설정"],label_visibility="collapsed")
if st.sidebar.button("🔄 데이터 새로고침",use_container_width=True):
    st.rerun()
st.sidebar.caption("Google Sheets · 일정 자동 저장")

try:
    api,sid,df=connect()
except Exception as exc:
    st.error(f"Google Sheets 연결 실패: {exc}")
    st.info("Secrets에 [team_calendar] spreadsheet_id 및 [gcp_service_account] 인증 정보를 확인하고, 서비스 계정에 시트 편집 권한을 부여하세요.")
    st.stop()

today=date.today()
people=sorted([str(x) for x in df["담당자"].dropna().unique() if str(x).strip()])
companies=sorted([str(x) for x in df["거래처"].dropna().unique() if str(x).strip()])
if "view_person" not in st.session_state:st.session_state.view_person="전체"
if st.session_state.view_person not in ["전체"]+people:st.session_state.view_person="전체"
if "cal_month" not in st.session_state:st.session_state.cal_month=today.replace(day=1)

st.sidebar.divider()
st.sidebar.markdown("#### 담당자")
for person in ["전체"]+people:
    count=len(df) if person=="전체" else int((df["담당자"]==person).sum())
    mark="🔵" if st.session_state.view_person==person else "▫️"
    if st.sidebar.button(f"{mark}  {person}  ({count})",key="side_person_"+person,use_container_width=True):
        st.session_state.view_person=person
        st.rerun()

st.sidebar.divider()
st.sidebar.markdown(f"**{st.session_state.cal_month.year}년 {st.session_state.cal_month.month}월**")
small=calendar.monthcalendar(st.session_state.cal_month.year,st.session_state.cal_month.month)
st.sidebar.caption("월   화   수   목   금   토   일")
for week in small:
    st.sidebar.caption("   ".join(f"{x:2d}" if x else "  " for x in week))

def filtered_rows(key,show_search=True):
    data=df.copy()
    person=st.session_state.view_person
    if person!="전체":data=data[data["담당자"]==person]
    if show_search:
        q=st.text_input("🔎 업무명, 거래처, 메모 검색",key="query_"+key,placeholder="검색어 입력")
        if q:
            mask=pd.Series(False,index=data.index)
            for col in ("업무명","거래처","메모"):
                mask |= data[col].astype(str).str.contains(q,case=False,regex=False,na=False)
            data=data[mask]
    return data

def table(data):
    if data.empty:
        st.info("조건에 해당하는 일정이 없습니다.")
    else:
        cols=["마감일","시작시간","업무명","거래처","담당자","업무구분","진행상태","진행률"]
        st.dataframe(data[cols],hide_index=True,use_container_width=True,height=min(500,70+len(data)*35))

def edit_pick(data,key):
    if data.empty:return
    ids=data.index.tolist()
    idx=st.selectbox("수정할 업무 선택",ids,key="pick_"+key,
        format_func=lambda i:f"{data.loc[i,'마감일']} · {data.loc[i,'담당자']} · {data.loc[i,'업무명']}")
    with st.expander("✏️ 선택한 업무 수정"):
        editor(data.loc[idx].to_dict(),key="edit_"+key+"_"+str(idx))

if page=="🗓️ 캘린더":
    st.title("캘린더")
    st.caption("영업팀의 일정을 한눈에 확인하고 담당자별로 관리하세요.")
    with st.container(border=True):
        nav1,nav2,nav3,nav4,nav5,nav6=st.columns([.55,2,.55,.9,1.5,1.5])
        if nav1.button("❮",use_container_width=True):
            st.session_state.cal_month=month_shift(st.session_state.cal_month,-1);st.rerun()
        nav2.markdown(f"### {st.session_state.cal_month.year}년 {st.session_state.cal_month.month}월")
        if nav3.button("❯",use_container_width=True):
            st.session_state.cal_month=month_shift(st.session_state.cal_month,1);st.rerun()
        if nav4.button("오늘",use_container_width=True):
            st.session_state.cal_month=today.replace(day=1);st.rerun()
        person_choice=nav5.selectbox("담당자",["전체"]+people,
            index=(["전체"]+people).index(st.session_state.view_person),key="calendar_person")
        if person_choice!=st.session_state.view_person:
            st.session_state.view_person=person_choice;st.rerun()
        cat_choice=nav6.selectbox("업무 구분",["전체"]+CATS,key="calendar_category")
        s1,s2,s3=st.columns([1.5,1.5,1])
        stat_choice=s1.selectbox("진행 상태",["전체"]+STATES+["지연"],key="calendar_status")
        keyword=s2.text_input("검색",placeholder="업무명 · 거래처",key="calendar_search")
        with s3.popover("＋ 일정 추가",use_container_width=True):
            editor(key="calendar_add")
        st.caption("🔵 미시작　🟣 진행중　🟠 거의완료　🟢 완료　🔴 지연")
        shown=df.copy()
        if st.session_state.view_person!="전체":
            shown=shown[shown["담당자"]==st.session_state.view_person]
        if cat_choice!="전체":shown=shown[shown["업무구분"]==cat_choice]
        if stat_choice!="전체":shown=shown[shown.apply(state,axis=1)==stat_choice]
        if keyword:
            shown=shown[shown[["업무명","거래처","메모"]].astype(str).apply(
                lambda s:s.str.contains(keyword,case=False,regex=False,na=False)).any(axis=1)]
        weeknames=["일","월","화","수","목","금","토"]
        for col,name in zip(st.columns(7,gap="small"),weeknames):
            col.markdown(f"<div style='text-align:center;font-weight:700;color:#405878;padding:7px'>{name}</div>",unsafe_allow_html=True)
        month=st.session_state.cal_month
        for week in calendar.Calendar(firstweekday=6).monthdatescalendar(month.year,month.month):
            for col,day in zip(st.columns(7,gap="small"),week):
                with col:
                    with st.container(border=True):
                        is_current=day.month==month.month
                        color="#1d4ed8" if day==today else ("#273d5b" if is_current else "#b3bfd0")
                        st.markdown(f"<div style='font-size:14px;font-weight:700;color:{color}'>{day.day}</div>",unsafe_allow_html=True)
                        entries=shown[shown["마감일"]==day.isoformat()]
                        if len(entries):
                            for _,row in entries.head(3).iterrows():
                                st.markdown(calendar_card(row),unsafe_allow_html=True)
                            if len(entries)>3:st.caption(f"+ {len(entries)-3}건 더보기")
                        else:st.markdown("<div style='height:37px'></div>",unsafe_allow_html=True)
                        if len(entries):
                            if st.button(f"상세 {len(entries)}건",key="day_"+day.isoformat(),use_container_width=True):
                                st.session_state.selected_day=day.isoformat()
        selected=st.session_state.get("selected_day")
        if selected:
            daydata=shown[shown["마감일"]==selected]
            with st.expander(f"📅 {selected} 일정 상세",expanded=True):
                table(daydata)
                edit_pick(daydata,"calendar_day")
    st.subheader("이번 달 일정 목록")
    month_data=shown[shown["마감일"].str.startswith(f"{month.year}-{month.month:02d}",na=False)]
    table(month_data)
    edit_pick(month_data,"calendar_month")

elif page=="🏠 홈":
    st.title("영업팀 업무 대시보드")
    st.caption("전체 업무 진행 현황과 담당자별 일정 요약")
    data=filtered_rows("home",False)
    unfinished=data[data["진행상태"]!="완료"]
    late=unfinished[unfinished.apply(state,axis=1)=="지연"]
    today_due=data[data["마감일"]==today.isoformat()]
    for col,label,value in zip(st.columns(4),["전체 업무","진행·미시작","지연 업무","오늘 마감"],
        [len(data),len(unfinished),len(late),len(today_due)]):
        col.metric(label,f"{value:,}건")
    st.subheader("다가오는 일정")
    upcoming=data[(data["마감일"]>=today.isoformat()) & (data["진행상태"]!="완료")].sort_values("마감일")
    table(upcoming.head(20))
    with st.expander("＋ 업무 등록"):editor(key="home_add")

elif page=="📋 업무 현황":
    st.title("업무 현황")
    data=filtered_rows("tasks")
    a,b=st.columns(2)
    category=a.selectbox("업무 구분",["전체"]+CATS,key="task_category")
    status=b.selectbox("진행 상태",["전체"]+STATES+["지연"],key="task_status")
    if category!="전체":data=data[data["업무구분"]==category]
    if status!="전체":data=data[data.apply(state,axis=1)==status]
    table(data)
    with st.expander("＋ 업무 등록"):editor(key="tasks_add")
    edit_pick(data,"tasks")

elif page=="🏢 거래처 관리":
    st.title("거래처별 일정")
    if companies:
        company=st.selectbox("거래처 선택",companies)
        data=df[df["거래처"]==company]
        if st.session_state.view_person!="전체":data=data[data["담당자"]==st.session_state.view_person]
        st.metric("등록 업무",f"{len(data):,}건")
        table(data)
        edit_pick(data,"company")
    else:st.info("등록된 거래처가 없습니다.")

elif page=="👥 담당자별 현황":
    st.title("담당자별 업무 현황")
    if len(df):
        rows=[]
        for person in people:
            part=df[df["담당자"]==person]
            rows.append({"담당자":person,"전체":len(part),"완료":sum(part["진행상태"]=="완료"),
                "지연":sum(part.apply(state,axis=1)=="지연")})
        st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
        table(filtered_rows("people"))
    else:st.info("등록된 업무가 없습니다.")

else:
    st.title("설정")
    st.success("Google Sheets 연결 정상")
    st.write("저장 시트: `일정관리`")
    st.caption("일정은 Google Sheets에 직접 저장됩니다. 기존 데이터는 유지합니다.")
    st.warning("현재는 공유 편집형입니다. 사용자별 Google 로그인과 본인 업무만 수정하는 권한은 별도 구현이 필요합니다.")
