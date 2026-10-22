from pathlib import Path
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import pandas as pd
import streamlit as st
import plotly.express as px
from openpyxl import load_workbook

st.set_page_config(page_title='담당 거래처 관리',page_icon='📊',layout='wide')
st.markdown('''<style>
.stApp{background:#f5f7fb;color:#172b4d}
[data-testid="stSidebar"]{background:#ffffff;border-right:1px solid #e4eaf2}
[data-testid="stMetric"]{background:white;border:1px solid #dfe7f2;border-radius:13px;padding:16px;box-shadow:0 2px 9px rgba(25,45,75,.035)}
[data-testid="stMetricValue"]{font-weight:700;letter-spacing:-.5px}
[data-testid="stSidebar"] .stButton button{border-radius:9px;text-align:left;justify-content:flex-start}
[data-testid="stSidebar"] details{border:1px solid #e8edf5;border-radius:10px;margin-bottom:7px;background:#fafcff}
[data-testid="stSidebar"] details summary{font-weight:650;color:#263d5d}
.stTabs [data-baseweb="tab"]{font-weight:600}
</style>''',unsafe_allow_html=True)
ROOT=Path(__file__).resolve().parent
LOCAL=ROOT/'data'
AGENCY='거래처_대리점.xlsx'
SALES_FILES=['2025_01월-06월.xls','2025_07월-12월.xls','2026_01월-06월.xls','2026_07월-12월.xls']
ALL_FILES=[AGENCY]+SALES_FILES

def drive_config():
    try:
        section=st.secrets.get('customer_drive',{})
        info=st.secrets.get('gcp_service_account',None)
        if info is None and 'gcp' in st.secrets and 'service_account_json' in st.secrets['gcp']:
            info=json.loads(str(st.secrets['gcp']['service_account_json']))
        if info is None:
            info=st.secrets.get('google_service_account',None)
        if info is None:
            info=st.secrets.get('service_account',None)
        if info is None:
            return section,None
        return section,(json.loads(info) if isinstance(info,str) else dict(info))
    except Exception:
        return {},None

@st.cache_data(show_spinner=False, max_entries=3)
def fetch_drive(folder_id,cred_json):
    """Drive 파일을 병렬 다운로드하며 수동 갱신 전까지 캐시합니다."""
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    import io

    info=json.loads(cred_json)
    credentials=Credentials.from_service_account_info(
        info,scopes=['https://www.googleapis.com/auth/drive.readonly'])
    service=build('drive','v3',credentials=credentials,cache_discovery=False)
    items=[];token=None
    while True:
        resp=service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields='nextPageToken,files(id,name,mimeType,modifiedTime)',
            pageSize=1000,pageToken=token,supportsAllDrives=True,
            includeItemsFromAllDrives=True).execute()
        items.extend(x for x in resp.get('files',[]) if x['name'] in ALL_FILES)
        token=resp.get('nextPageToken')
        if not token:break

    def download(item):
        # googleapiclient service는 스레드 간 공유하지 않습니다.
        own_service=build('drive','v3',credentials=credentials,cache_discovery=False)
        if item['mimeType']=='application/vnd.google-apps.spreadsheet':
            req=own_service.files().export_media(
                fileId=item['id'],mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        else:
            req=own_service.files().get_media(fileId=item['id'],supportsAllDrives=True)
        stream=io.BytesIO()
        dl=MediaIoBaseDownload(stream,req)
        done=False
        while not done:
            _,done=dl.next_chunk()
        return item['name'],stream.getvalue()

    result={}
    if items:
        with ThreadPoolExecutor(max_workers=min(5,len(items))) as pool:
            futures=[pool.submit(download,item) for item in items]
            for future in as_completed(futures):
                name,content=future.result()
                result[name]=content
    return result

@st.cache_data(show_spinner=False, max_entries=3)
def load_sources():
    """클라우드는 Drive, PC 실행은 data 폴더. 둘 다 확인해 출처를 표시합니다."""
    section, info = drive_config()
    folder = str(section.get('folder_id', '')).strip()
    found = {}
    errors = []
