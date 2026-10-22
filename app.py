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
