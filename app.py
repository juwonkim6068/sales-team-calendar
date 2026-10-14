"""PSG 영업부 일정 대시보드: Google Sheets + OIDC, fail-closed authentication."""
from __future__ import annotations
import calendar
import html
import io
import json
import mimetypes
import secrets
import time
from urllib.parse import urlencode
import requests
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
.attachment-table-header {background:#e7effd;color:#153e70;font-weight:750;font-size:.79rem;padding:12px 7px;border:1px solid #d8e3f2;border-radius:5px;min-height:44px}
.attachment-table-cell {background:#fff;color:#153a65;font-size:.79rem;padding:11px 7px;min-height:43px;border-bottom:1px solid #e3eaf3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
div[data-testid="stPopover"] button {font-size:.78rem!important;color:#15529b!important;border:1px solid #bfd7f8!important;background:#eef5ff!important;min-height:35px!important}
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
    creds = Credentials.from_service_account_info(dict(st.secrets['gcp_service_account']), scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    return gspread.authorize(creds).open_by_key(st.secrets['spreadsheet_id'])

# 파일은 Google Drive에 저장하고, 연결 정보는 Google Sheets의 '첨부파일' 탭에 저장합니다.
FILE_HEADERS = ['파일ID', '업무ID', '파일명', 'MIME유형', '파일크기', '등록일시', '등록자']
DRIVE_FOLDER_ID = str(st.secrets.get('drive_folder_id', '')).strip()

# Google Sheets는 기존 서비스 계정으로, Drive 업로드는 사용자 OAuth로 처리합니다.
# 일반 개인 Drive에는 서비스 계정의 저장 용량이 없어 사용자 OAuth가 필요합니다.
OAUTH_SCOPE = 'https://www.googleapis.com/auth/drive.file'

def oauth_config():
    cfg = st.secrets.get('google_oauth', {})
    return {k: str(cfg.get(k, '')).strip() for k in ('client_id', 'client_secret', 'redirect_uri')}

def oauth_url():
    cfg = oauth_config()
    if not all(cfg.values()):
        raise ValueError('Secrets의 [google_oauth] client_id, client_secret, redirect_uri 설정이 필요합니다.')
    state = secrets.token_urlsafe(32)
    st.session_state['drive_oauth_state'] = state
    return 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode({
        'client_id': cfg['client_id'], 'redirect_uri': cfg['redirect_uri'],
        'response_type': 'code', 'scope': OAUTH_SCOPE,
        'access_type': 'offline', 'prompt': 'consent', 'state': state,
    })

def process_oauth_callback():
    params = st.query_params
    if 'error' in params:
        st.error('Google 인증이 거부되었습니다: ' + str(params['error']))
        params.clear()
        return
    if 'code' not in params:
        return
    code, state = str(params['code']), str(params.get('state', ''))
    params.clear()
    expected = st.session_state.pop('drive_oauth_state', None)
    if not expected or not secrets.compare_digest(state, expected):
        st.error('OAuth 검증 실패: 로그인 버튼부터 다시 진행하세요.')
        return
    cfg = oauth_config()
    try:
        res = requests.post('https://oauth2.googleapis.com/token', data={
            'code': code, 'client_id': cfg['client_id'],
            'client_secret': cfg['client_secret'], 'redirect_uri': cfg['redirect_uri'],
            'grant_type': 'authorization_code',
        }, timeout=30)
        if not res.ok:
            raise RuntimeError(res.text[:500])
        token = res.json()
        token['expires_at'] = time.time() + int(token.get('expires_in', 3600)) - 60
        st.session_state['drive_oauth_token'] = token
        st.toast('Google Drive 연결 완료')
    except Exception as exc:
        st.error(f'Google 인증 처리 실패: {exc}')

def drive_access_token():
    token = st.session_state.get('drive_oauth_token')
    if not token:
        raise PermissionError('먼저 Google Drive 계정을 연결하세요.')
    if time.time() >= token.get('expires_at', 0):
        if not token.get('refresh_token'):
            st.session_state.pop('drive_oauth_token', None)
            raise PermissionError('Google 인증이 만료되었습니다. 다시 연결하세요.')
        cfg = oauth_config()
        res = requests.post('https://oauth2.googleapis.com/token', data={
            'client_id': cfg['client_id'], 'client_secret': cfg['client_secret'],
            'refresh_token': token['refresh_token'], 'grant_type': 'refresh_token',
        }, timeout=30)
        if not res.ok:
            st.session_state.pop('drive_oauth_token', None)
            raise PermissionError('Google Drive 인증 갱신 실패. 다시 연결하세요.')
        refreshed = res.json()
        token.update(refreshed)
        token['expires_at'] = time.time() + int(refreshed.get('expires_in', 3600)) - 60
        st.session_state['drive_oauth_token'] = token
    return token['access_token']

def drive_request(method, url, **kwargs):
    headers = kwargs.pop('headers', {})
    headers['Authorization'] = 'Bearer ' + drive_access_token()
    return requests.request(method, url, headers=headers, timeout=120, **kwargs)

def drive_connect_ui(key_prefix="global"):
    if st.session_state.get('drive_oauth_token'):
        st.caption('🟢 Google Drive 연결됨')
        if st.button('Drive 연결 해제', key=f'{key_prefix}_drive_disconnect'):
            st.session_state.pop('drive_oauth_token', None)
            st.rerun()
        return True
    try:
        st.link_button('🔐 Google Drive 연결', oauth_url(), use_container_width=True)
    except Exception as exc:
        st.warning(str(exc))
    return False

process_oauth_callback()

def file_sheet():
    book = sheet_client()
    try:
        ws = book.worksheet('첨부파일')
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title='첨부파일', rows=1000, cols=len(FILE_HEADERS))
        ws.append_row(FILE_HEADERS)
    if ws.row_values(1) != FILE_HEADERS:
        raise ValueError("Google Sheets '첨부파일' 탭의 첫 행이 예상 열 구성과 다릅니다.")
    return ws

def file_records():
    try:
        ws = sheet_client().worksheet('첨부파일')
    except gspread.WorksheetNotFound:
        return pd.DataFrame(columns=FILE_HEADERS)
    vals = ws.get_all_records()
    return pd.DataFrame(vals, columns=FILE_HEADERS)

def drive_error(response):
    try:
        message = response.json().get('error', {}).get('message', response.text)
    except Exception:
        message = response.text[:500]
    raise RuntimeError(f'Google Drive 오류 ({response.status_code}): {message}')

def upload_drive_file(upload):
    if not DRIVE_FOLDER_ID:
        raise ValueError("Streamlit Secrets에 drive_folder_id = '본인 Google Drive 폴더 ID'를 추가하세요.")
    content = upload.getvalue()
    if not content:
        raise ValueError('빈 파일은 등록할 수 없습니다.')
    mime = upload.type or mimetypes.guess_type(upload.name)[0] or 'application/octet-stream'
    meta = {'name': upload.name, 'parents': [DRIVE_FOLDER_ID]}
    # 1) Resumable 세션 생성 2) 파일 본문 업로드 (multipart 오류 방지)
    init = drive_request('POST', 'https://www.googleapis.com/upload/drive/v3/files',
        params={'uploadType': 'resumable', 'fields': 'id,name', 'supportsAllDrives': 'true'},
        headers={'Content-Type': 'application/json; charset=UTF-8',
                 'X-Upload-Content-Type': mime, 'X-Upload-Content-Length': str(len(content))},
        json=meta)
    if not init.ok:
        drive_error(init)
    location = init.headers.get('Location')
    if not location or not location.startswith('https://www.googleapis.com/'):
        raise RuntimeError('Google Drive 업로드 세션 URL이 올바르지 않습니다.')
    res = drive_request('PUT', location,
        headers={'Content-Type': mime, 'Content-Length': str(len(content))}, data=content)
    if not res.ok:
        drive_error(res)
    return res.json()['id'], mime, len(content)

def download_drive_file(file_id):
    res = drive_request('GET', f'https://www.googleapis.com/drive/v3/files/{file_id}',
        params={'alt': 'media', 'supportsAllDrives': 'true'})
    if not res.ok:
        drive_error(res)
    return res.content

def attachment_manager(task_id, key_prefix):
    """각 업무별 파일 업로드/다운로드. 업무 수정 허용 여부와 별개로 동작합니다."""
    st.markdown('<div class="panel-title">📎 첨부파일 등록 · 다운로드</div>', unsafe_allow_html=True)
    connected = drive_connect_ui(key_prefix)
    try:
        files = file_records()
    except Exception as exc:
        st.error(f'첨부파일 목록 조회 오류: {exc}')
        return
    matched = files[files['업무ID'].astype(str) == str(task_id)] if not files.empty else files
    if matched.empty:
        st.caption('현재 등록된 파일이 없습니다.')
    else:
        for _, f in matched.iterrows():
            c1, c2 = st.columns([3, 1])
            c1.markdown('📄 **' + html.escape(str(f['파일명'])) + '**')
            c1.caption(str(f['등록일시']) + ' · ' + str(f['파일크기']) + ' bytes')
            if not connected:
                c2.caption('Drive 연결 필요')
                continue
            try:
                file_data = download_drive_file(str(f['파일ID']))
                c2.download_button(
                    '⬇ 다운로드', data=file_data, file_name=str(f['파일명']),
                    mime=str(f['MIME유형']) or 'application/octet-stream',
                    key=f'{key_prefix}_download_{f["파일ID"]}', use_container_width=True
                )
            except Exception as exc:
                c2.error(f'다운로드 불가: {exc}')
    if not connected:
        st.info('Google Drive 연결 후 파일 등록 및 다운로드가 가능합니다.')
        return
    with st.expander('➕ 파일 등록하기', expanded=False):
        uploads = st.file_uploader(
            '파일을 끌어다 놓거나 선택하세요 (여러 개 가능)',
            accept_multiple_files=True, key=f'{key_prefix}_uploader'
        )
        if st.button('선택한 파일 등록', type='primary', key=f'{key_prefix}_upload'):
            if not uploads:
                st.warning('등록할 파일을 선택하세요.')
            else:
                success, failures = 0, []
                for upload in uploads:
                    try:
                        file_id, mime, size = upload_drive_file(upload)
                        try:
                            file_sheet().append_row([
                                file_id, str(task_id), upload.name, mime, str(size), nowstr(), email
                            ], value_input_option='RAW')
                        except Exception:
                            # 연결 정보 기록 실패 시 고아 파일이 남지 않도록 정리 시도
                            drive_request('DELETE',
                                f'https://www.googleapis.com/drive/v3/files/{file_id}',
                                params={'supportsAllDrives': 'true'})
                            raise
                        success += 1
                    except Exception as exc:
                        failures.append(f'{upload.name}: {exc}')
                if success:
                    st.success(f'{success}개 파일이 등록되었습니다.')
                for err in failures:
                    st.error(err)
                if success:
                    st.rerun()

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

# Visual-only redesign. Data is always loaded from the existing Google Sheet.
st.markdown("""<style>
.stApp {background:#edf4fc!important;color:#122d53}
.block-container{max-width:1850px!important;padding:0.7rem 1.15rem 2rem!important}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#24568a,#3372a8)!important;min-width:230px!important}
[data-testid="stSidebar"] *{color:#fff!important}
[data-testid="stSidebar"] [role="radiogroup"] label{padding:9px 10px!important;border-radius:5px!important}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:#4389e5!important}
[data-testid="stMetric"]{background:white!important;border:1px solid #d3e2f3!important;border-radius:7px!important;padding:14px!important;box-shadow:0 1px 5px #c5d8ef60}
[data-testid="stMetricValue"]{color:#0c2b57!important;font-size:1.9rem!important}
[data-testid="stDataFrame"]{background:#fff;border:1px solid #d3e2f3;border-radius:6px}
[data-testid="stVerticalBlockBorderWrapper"]{background:#fff;border:1px solid #d5e3f3;border-radius:8px;padding:7px}
.stButton button[kind="primary"]{background:#114a8d!important}
.hero{background:linear-gradient(110deg,#09264b,#154779);padding:18px 24px;border-radius:8px;color:white;margin-bottom:12px;display:flex;align-items:center;justify-content:space-between;gap:12px}
.hero h1{color:white!important;margin:0!important;font-size:2rem!important}
.hero .subtitle{color:#d6e8fc;font-size:.85rem}
.panel-title{font-weight:800;font-size:1rem;color:#113a71;padding:8px 11px;background:#e4efff;border-radius:6px;margin:8px 0}
.panel-title.red{background:#ffe5ea;color:#d91c39}

/* Sidebar radio circles removed, labels become full-width navigation */
[data-testid="stSidebar"] [role="radiogroup"] label [data-testid="stWidgetLabel"],
[data-testid="stSidebar"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] {color:white!important}
[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child:has(input[type="radio"]),
[data-testid="stSidebar"] [role="radiogroup"] input[type="radio"] {display:none!important}
[data-testid="stSidebar"] [role="radiogroup"] label {display:flex!important;align-items:center!important;width:100%!important;min-height:39px!important;margin:1px 0!important;padding:8px 13px!important;cursor:pointer}
[data-testid="stSidebar"] [role="radiogroup"] label p {font-size:14px!important;font-weight:600!important}
[data-testid="stSidebar"] [role="radiogroup"] {gap:2px!important}
/* Compact cards and calendar */
.ui-card {background:white;border:1px solid #d9e5f4;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px #183e6610}
.ui-card-title {background:#e7f0ff;padding:12px 15px;font-weight:800;color:#153d70;font-size:15px}
.ui-card-title.red {background:#ffebef;color:#c81e3c}
.ui-card-body {padding:11px 12px}
.mini-cal {display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:5px;text-align:center}
.mini-cal .dow {font-size:12px;color:#72829b;font-weight:700;padding:5px 0}
.mini-cal .dow.sun {color:#e45160}.mini-cal .dow.sat{color:#3175c9}
.mini-cal .day {min-height:34px;display:flex;align-items:center;justify-content:center;border-radius:8px;position:relative;font-size:13px;color:#263c5e}
.mini-cal .day.muted {color:#b7c2d1}
.mini-cal .day.today {background:#174c91;color:white;font-weight:800}
.mini-cal .day.has-due:not(.today) {background:#eef4ff;color:#164d92;font-weight:700}
.mini-cal .day.has-due::after {content:"";width:5px;height:5px;background:#f06c44;border-radius:50%;position:absolute;bottom:2px;left:calc(50% - 2.5px)}
.mini-cal .day.today::after{background:#ffce54}
.calendar-foot {padding:8px 2px 1px;font-size:11px;color:#75859b}
/* Non-editable polished compact tables */
.pretty-table-wrap {border:1px solid #dce6f3;border-radius:9px;overflow:hidden;background:white}
.pretty-table {width:100%;border-collapse:separate;border-spacing:0;table-layout:fixed}
.pretty-table th {background:#f0f5fd;color:#536b8c;font-size:12px;text-align:left;padding:11px 9px;border-bottom:1px solid #dbe5f2;font-weight:750}
.pretty-table td {padding:10px 9px;font-size:12px;color:#263c5d;border-bottom:1px solid #edf1f7;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pretty-table tr:last-child td{border-bottom:0}
.pretty-table tbody tr:nth-child(even){background:#fafcff}
.pretty-table tbody tr:hover{background:#edf5ff}
.pretty-table .taskname{font-weight:650;color:#153a69}
.pretty-table .datecell{font-variant-numeric:tabular-nums;color:#506580}
.state-pill{display:inline-block;border-radius:6px;padding:4px 8px;font-size:11px;font-weight:750;background:#e9eef7;color:#49627f}
.state-pill.done{background:#def7e8;color:#16824c}
.state-pill.active{background:#fff0d2;color:#a96300}
.state-pill.plan{background:#e1edff;color:#1d63c1}
.state-pill.late{background:#ffe4e8;color:#c7253b}
.empty-list {padding:30px 12px;text-align:center;color:#8390a2;font-size:13px}

/* Hide radio indicator across Streamlit/BaseWeb versions while keeping clickable menu labels */
section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child:has(input),
section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child:has(svg),
section[data-testid="stSidebar"] div[role="radiogroup"] label [data-baseweb="radio"] > div:first-child,
section[data-testid="stSidebar"] div[role="radiogroup"] label input[type="radio"],
section[data-testid="stSidebar"] div[role="radiogroup"] label svg,
section[data-testid="stSidebar"] div[role="radiogroup"] label [data-testid="stRadioOption"] > div:first-child:has(input) {
 display:none!important;width:0!important;min-width:0!important;margin:0!important;padding:0!important;visibility:hidden!important;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label {gap:0!important;padding-left:14px!important}
section[data-testid="stSidebar"] div[role="radiogroup"] label > div:last-child {margin-left:0!important;padding-left:0!important}

/* Unified clean table design for all Google Sheets data views */
.unified-table-scroll {overflow-x:auto;width:100%;margin:5px 0 18px;border-radius:10px}
.unified-table {background:#fff;border:1px solid #dbe6f4;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(26,65,110,.045)}
.unified-table .pretty-table {table-layout:auto;min-width:700px;border-collapse:collapse;width:100%}
.unified-table .pretty-table thead th {position:sticky;top:0;background:#eef4fd;color:#385779;font-size:12px;font-weight:750;padding:12px 13px;white-space:nowrap;border-right:0;border-bottom:1px solid #d7e3f2}
.unified-table .pretty-table tbody td {font-size:12px;padding:12px 13px;border-right:0;border-bottom:1px solid #eaf0f7;max-width:400px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;line-height:1.6}
.unified-table .pretty-table tbody tr:nth-child(even) {background:#f8fbff}
.unified-table .pretty-table tbody tr:hover {background:#edf5ff}
.unified-table .pretty-table tbody tr:last-child td {border-bottom:0}
.unified-table a {color:#2468bc;text-decoration:none;font-weight:650}
.unified-table a:hover {text-decoration:underline}
.category-pill {display:inline-block;background:#e5f0ff;color:#245f9e;border:1px solid #c9e0ff;padding:3px 9px;border-radius:6px;font-size:11px;font-weight:700}
.priority-pill {display:inline-block;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:750}
.priority-pill.high {background:#ffe3e7;color:#c82c40}
.priority-pill.normal {background:#fff0c9;color:#a96b00}
.priority-pill.low {background:#e7effa;color:#567293}
</style>""",unsafe_allow_html=True)
NAV=['📅 전체 일정','📋 업무 목록','🗓️ 월간 캘린더','⏰ 마감임박 일정','🗣️ 회의 일정','🎓 교육 / 외부 일정','✅ 완료된 업무','👤 팀원별 업무','💬 팀 확인사항','➕ 일정 등록','🕘 변경 이력']
st.sidebar.markdown('## 📅 영업부 일정')
page=st.sidebar.radio('메뉴',NAV,label_visibility='collapsed')
st.sidebar.caption('Google Sheets 연결 · '+('공개 편집' if ALLOW_EDIT else '공개 조회 전용'))

if not tasks.empty:
    tasks['발송일']=tasks['발송일'].map(fmt_date)
    tasks['마감일']=tasks['마감일'].map(fmt_date)
    tasks['마감상태']=tasks.apply(lambda r:deadline(r)[0],axis=1)
    tasks['D-Day']=tasks.apply(lambda r:deadline(r)[1],axis=1)
    tasks['진행률(%)']=pd.to_numeric(tasks['진행률(%)'],errors='coerce').fillna(0).clip(0,100)
else:
    tasks['마감상태']=pd.Series(dtype='str');tasks['D-Day']=pd.Series(dtype='float')

def display_table(df, columns=None, height=330):
    """행별 첨부파일 등록/다운로드가 가능한 관리표."""
    cols = columns or ['발송일','마감일','업무구분','업무명','진행예정자(주/부)','담당자','진행상태','우선순위','확인사항','첨부파일URL']
    cols = [c for c in cols if c in df.columns]
    if df.empty:
        st.info('표시할 데이터가 없습니다.')
        return
    counts = {}
    if '첨부파일URL' in cols:
        try:
            meta = file_records()
            if not meta.empty:
                counts = meta.groupby(meta['업무ID'].astype(str)).size().to_dict()
        except Exception as exc:
            st.warning(f'첨부파일 목록 조회 오류: {exc}')
    widths = {'발송일':1,'마감일':1,'업무구분':1.15,'업무명':4.1,'진행예정자(주/부)':1.3,'담당자':.8,'진행상태':.95,'우선순위':.85,'확인사항':1.2,'첨부파일URL':1.35,'D-Day':.7}
    ratios = [widths.get(c,1.1) for c in cols]
    headers = st.columns(ratios,gap='small')
    for cell,col in zip(headers,cols):
        cell.markdown(f'<div class="attachment-table-header">{html.escape("첨부파일" if col=="첨부파일URL" else col)}</div>',unsafe_allow_html=True)
    for i,(_,rec) in enumerate(df.iterrows()):
        row = st.columns(ratios,gap='small',vertical_alignment='center')
        for cell,col in zip(row,cols):
            val=rec.get(col,'')
            val='' if pd.isna(val) else str(val)
            safe=html.escape(val,quote=True)
            with cell:
                if col=='첨부파일URL':
                    task_id=str(rec.get('업무ID','')).strip()
                    count=counts.get(task_id,0)
                    label=f'📎 파일 {count}개' if count else '＋ 등록'
                    if task_id:
                        with st.popover(label,use_container_width=True):
                            st.caption('업무: '+str(rec.get('업무명','')))
                            attachment_manager(task_id,f'row_{i}_{task_id}')
                    else:
                        st.caption('업무ID 없음')
                else:
                    if col in ('진행상태','처리상태'):
                        cls='done' if val=='완료' else 'active' if val=='진행중' else 'late' if val=='확인필요' else 'plan'
                        safe=f'<span class="state-pill {cls}">{safe}</span>' if val else '—'
                    elif col=='우선순위':
                        cls='high' if val in ('긴급','높음') else 'normal' if val=='보통' else 'low'
                        safe=f'<span class="priority-pill {cls}">{safe}</span>' if val else '—'
                    elif col=='업무구분':
                        safe=f'<span class="category-pill">{safe}</span>' if val else '—'
                    elif col=='업무명':
                        safe=f'<span class="taskname" title="{safe}">{safe}</span>' if val else '—'
                    elif not val:
                        safe='—'
                    cell.markdown(f'<div class="attachment-table-cell" title="{html.escape(val,quote=True)}">{safe}</div>',unsafe_allow_html=True)

st.markdown(f'<div class="hero"><h1>🗓️ 영업부 업무 일정 대시보드</h1><div class="subtitle">오늘은 {date.today().strftime("%Y년 %m월 %d일")} · Google Sheets 실시간 조회</div></div>',unsafe_allow_html=True)
if ALLOW_EDIT:st.warning('공개 편집이 활성화되어 있습니다. 링크 방문자가 수정할 수 있습니다.')
if page=='📅 전체 일정':
    today=date.today();month=tasks[tasks['마감일'].str.startswith(today.strftime('%Y-%m'),na=False)]
    done=int((month['진행상태']=='완료').sum());total=len(month)
    urgent=tasks[(tasks['마감상태'].isin(['오늘 마감','마감 임박'])) & (tasks['진행상태']!='완료')]
    # 상단 KPI 5개 카드 제거: 실제 일정 중심의 간결한 화면
    left,middle,right=st.columns([1.35,1.15,.85])
    def polished_table(frame, fields, max_rows=6):
        frame=frame.head(max_rows)
        if frame.empty:
            st.markdown('<div class="pretty-table-wrap"><div class="empty-list">표시할 일정이 없습니다.</div></div>',unsafe_allow_html=True)
            return
        headers={'D-Day':'D-Day','마감일':'마감일','업무명':'업무명','담당자':'담당자','진행상태':'상태'}
        widths={'D-Day':'12%','마감일':'20%','업무명':'40%','담당자':'15%','진행상태':'13%'}
        th=''.join(f'<th style="width:{widths.get(f,"auto")}">{headers.get(f,f)}</th>' for f in fields)
        rows=[]
        for _,r in frame.iterrows():
            cells=[]
            for f in fields:
                val=str(r.get(f,'') or '')
                if f=='D-Day':
                    raw=r.get('D-Day')
                    val='D'+str(int(raw)) if pd.notna(raw) else '—'
                safe=html.escape(val)
                if f=='진행상태':
                    state_class=('done' if val=='완료' else 'active' if val=='진행중' else 'plan' if val=='예정' else 'late' if val=='확인필요' else '')
                    safe=f'<span class="state-pill {state_class}">{safe}</span>'
                elif f=='업무명':safe=f'<span class="taskname" title="{safe}">{safe}</span>'
                elif f=='마감일':safe=f'<span class="datecell">{safe}</span>'
                cells.append(f'<td>{safe}</td>')
            rows.append('<tr>'+''.join(cells)+'</tr>')
        st.markdown('<div class="pretty-table-wrap"><table class="pretty-table"><thead><tr>'+th+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>',unsafe_allow_html=True)

    with left:
        st.markdown('<div class="panel-title red">🚨 마감 임박 일정 (D-3이내)</div>',unsafe_allow_html=True)
        polished_table(urgent.sort_values('D-Day'),['D-Day','마감일','업무명','담당자','진행상태'])
    with middle:
        st.markdown('<div class="panel-title">⏰ 금주 주요 일정</div>',unsafe_allow_html=True)
        week_end=today+timedelta(days=7)
        week=tasks[tasks['마감일'].apply(lambda x:bool(dateval(x) and today<=dateval(x)<=week_end))]
        polished_table(week.sort_values('마감일'),['마감일','업무명','담당자','진행상태'])
    with right:
        year,mo=today.year,today.month
        due_dates=set(month['마감일'].dropna().astype(str))
        weekdays=['월','화','수','목','금','토','일']
        head=''.join(f'<div class="dow {"sun" if i==6 else "sat" if i==5 else ""}">{d}</div>' for i,d in enumerate(weekdays))
        day_cells=[]
        for wk in calendar.monthcalendar(year,mo):
            for n in wk:
                if n==0:day_cells.append('<div class="day muted"></div>');continue
                classes='day'+(' today' if n==today.day else '')+(' has-due' if f'{year}-{mo:02d}-{n:02d}' in due_dates else '')
                day_cells.append(f'<div class="{classes}">{n}</div>')
        st.markdown(f'<div class="ui-card"><div class="ui-card-title">🗓️ {year}년 {mo}월</div><div class="ui-card-body"><div class="mini-cal">{head}{"".join(day_cells)}</div><div class="calendar-foot">🟠 마감 일정이 등록된 날짜</div></div></div>',unsafe_allow_html=True)
    f1,f2,f3,f4,f5=st.columns([1.1,1,1,1,1.8])
    period=f1.date_input('기간',value=(date(today.year,1,1),date(today.year,12,31)))
    cat=f2.selectbox('업무 구분',['전체']+sorted(x for x in tasks['업무구분'].unique() if x))
    state=f3.selectbox('진행 상태',['전체']+sorted(x for x in tasks['진행상태'].unique() if x))
    owner=f4.selectbox('담당자',['전체']+sorted(x for x in tasks['담당자'].unique() if x))
    q=f5.text_input('업무명 또는 키워드 검색')
    view=tasks.copy()
    if isinstance(period,tuple) and len(period)==2:
        lo,hi=period;view=view[view['마감일'].apply(lambda x:bool(dateval(x) and lo<=dateval(x)<=hi)) | ((view['마감일']=='') & view['발송일'].apply(lambda x:bool(dateval(x) and lo<=dateval(x)<=hi)))]
    if cat!='전체':view=view[view['업무구분']==cat]
    if state!='전체':view=view[view['진행상태']==state]
    if owner!='전체':view=view[view['담당자']==owner]
    if q:view=view[view.astype(str).apply(lambda x:x.str.contains(q,case=False,regex=False)).any(axis=1)]
    st.markdown('<div class="panel-title">📋 전체 업무 관리표</div>',unsafe_allow_html=True)
    display_table(view,height=370)
    st.caption('화면의 수치와 업무는 Google Sheets 실제 기록을 기준으로 계산됩니다. 샘플 일정은 추가하지 않습니다.')

elif page in ['🗣️ 회의 일정','🎓 교육 / 외부 일정','✅ 완료된 업무']:
    groups={'🗣️ 회의 일정':['회의'],'👥 거래처 관련':['거래처','채권관리'],'🧾 ERP / 마감 업무':['마감업무','ERP/시스템','비용처리'],'🎓 교육 / 외부 일정':['교육'],'📁 팀 공유 자료':[],'✅ 완료된 업무':[]}
    subset=tasks.copy()
    if page=='📁 팀 공유 자료':subset=subset[subset['첨부파일URL'].str.strip()!='']
    elif page=='✅ 완료된 업무':subset=subset[subset['진행상태']=='완료']
    else:subset=subset[subset['업무구분'].isin(groups[page])]
    st.subheader(page);st.caption(f'Google Sheets 등록 업무 {len(subset)}건')
    display_table(subset,height=550)

if False:  # previous summary view replaced by redesigned dashboard
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
        display_table(alert,['업무명','담당자','마감일','마감상태','D-Day','진행상태'])
    with r:
        st.subheader('진행 상태별 현황')
        if total:
            count=tasks['진행상태'].replace('','미지정').value_counts().reset_index()
            count.columns=['상태','건수']
            st.plotly_chart(px.pie(count,names='상태',values='건수',hole=.55),use_container_width=True)
    st.subheader('이번 주 마감 일정')
    end=date.today()+timedelta(days=7)
    week=tasks[tasks['마감일'].apply(lambda x: bool(dateval(x) and date.today()<=dateval(x)<=end)) & (tasks['진행상태']!='완료')]
    display_table(week,['마감일','업무명','담당자','진행상태','우선순위'])

elif page == '👥 팀원별 업무':
    st.subheader('👥 팀원별 업무 현황')
    if tasks.empty:
        st.info('등록된 업무가 없습니다.')
    else:
        summary=tasks.groupby('담당자',dropna=False).agg(전체=('업무ID','count'),완료=('진행상태',lambda s:(s=='완료').sum()),진행중=('진행상태',lambda s:(s=='진행중').sum()),지연=('마감상태',lambda s:(s=='지연').sum())).reset_index()
        display_table(summary,summary.columns.tolist())
        member=st.selectbox('담당자 선택',['전체']+sorted(tasks['담당자'].dropna().unique().tolist()))
        view=tasks if member=='전체' else tasks[tasks['담당자']==member]
        display_table(view,['업무ID','업무명','업무구분','담당자','마감일','진행상태','우선순위','마감상태'])

elif page in ('📋 업무 목록','⏰ 마감임박 일정'):
    st.subheader('업무 검색 및 상세 관리')
    f1,f2,f3,f4=st.columns(4)
    keyword=f1.text_input('업무명 검색')
    status=f2.selectbox('진행 상태',['전체']+STATES)
    owner=f3.selectbox('담당자',['전체']+sorted([x for x in tasks['담당자'].unique() if x]))
    category=f4.selectbox('업무 구분',['전체']+CATEGORIES)
    df=tasks.copy()
    if page=='⏰ 마감임박 일정':df=df[df['마감상태'].isin(['지연','오늘 마감','마감 임박'])]
    if keyword:df=df[df['업무명'].str.contains(keyword,case=False,regex=False,na=False)]
    if status!='전체':df=df[df['진행상태']==status]
    if owner!='전체':df=df[df['담당자']==owner]
    if category!='전체':df=df[df['업무구분']==category]
    display_table(df,['업무ID','마감일','업무구분','업무명','담당자','진행상태','우선순위','진행률(%)','마감상태','D-Day'])
    if not df.empty:
        task_id=st.selectbox('상세 확인 / 수정할 업무',df['업무ID'].tolist(),format_func=lambda x:f'{x} · {tasks.loc[tasks["업무ID"]==x,"업무명"].iloc[0]}')
        item=tasks[tasks['업무ID']==task_id].iloc[0]
        st.info(str(item['상세내용']) or str(item['업무명']))
        if item['비고']:st.caption('비고: '+str(item['비고']))
        if item['첨부파일URL'] and str(item['첨부파일URL']).startswith('https://'):
            st.link_button('📎 첨부파일 열기',str(item['첨부파일URL']))
        attachment_manager(task_id, 'detail')
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
        display_table(matched,['작성일시','작성자','확인유형','확인내용','처리상태','처리담당자'])
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
        display_table(history.iloc[::-1].head(200),HISTORY)
    except Exception as exc:st.error(f'이력 조회 실패: {exc}')

st.caption('※ 업무 데이터는 Google Sheets에서 조회하고, 첨부파일은 Google Drive에 저장합니다. 공개 편집을 켠 경우 변경 내용은 Google Sheets에 저장됩니다. 동시 수정이 많은 환경에서는 별도 데이터베이스와 트랜잭션 처리를 권장합니다.')
