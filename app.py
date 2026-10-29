import calendar
import hashlib
import json
import uuid
from datetime import date, datetime
from html import escape
from urllib.parse import quote

import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# 업무 카드 배지: 담당자 이름과 업무구분 값마다 고정된 색상을 부여합니다.
# 빨간색 계열은 마감 지연/위험 표시와 혼동되지 않도록 제외합니다.
_OWNER_PALETTE = [
    ('#fff9d6', '#856000', '#eab308'),  # 김주원: 노랑
    ('#eaf8ef', '#16703d', '#22a05a'),  # 이상인: 초록
    ('#edf4ff', '#1d55b3', '#3b82f6'),  # 조인환: 파랑
    ('#eee9ff', '#5a42a4', '#d6cafa'),  # 보라
    ('#e6f6f6', '#176e77', '#bce6e8'),  # 청록
    ('#eff0ff', '#4859a5', '#d3d9fa'),  # 남색
]
_CATEGORY_PALETTE = [
    ('#e4f5f2', '#126b62', '#b9e2da'),
    ('#eaf0ff', '#2a57a5', '#ccdafa'),
    ('#f1edff', '#63479d', '#ddd1f8'),
    ('#fdf3df', '#906313', '#efdfb7'),
    ('#e9f5e6', '#477c2d', '#cce6c3'),
]

def _task_badge_colors(value, kind='owner'):
    name = str(value or '').strip()
    if kind == 'owner':
        # 주요 담당자는 서로 확실히 구분되는 고정 색상
        fixed = {'김주원': 0, '이상인': 1, '조인환': 2}
        if name.split(' ')[0] in fixed:name=name.split(' ')[0]
        if name in ('','미지정','담당자 미지정','전체'):
            return ('#f1f5f9','#526174','#94a3b8')
        palette = _OWNER_PALETTE
    else:
        fixed = {}
        palette = _CATEGORY_PALETTE
    if name in fixed:
        index = fixed[name]
    else:
        index = int(hashlib.sha256(name.encode('utf-8')).hexdigest()[:8], 16) % len(palette)
    return palette[index]

def _task_badge_style(value, kind='owner'):
    bg, fg, border = _task_badge_colors(value, kind)
    return f'--badge-bg:{bg};--badge-fg:{fg};--badge-border:{border}'

st.set_page_config(page_title='영업팀 대시보드', page_icon='📊', layout='wide', initial_sidebar_state='expanded')
st.markdown("""<style>
/* Aligned, compact task actions */
[class*="st-key-completed_row_"]{display:grid!important;grid-template-columns:minmax(0,1fr) auto!important;align-items:center!important;gap:12px!important;background:#f0faf4;border:1px solid #c7e7d3;border-radius:10px;padding:12px 14px;margin-bottom:12px}
[class*="st-key-completed_row_"] > [data-testid="stElementContainer"]{margin:0!important;align-self:center!important}
[class*="st-key-completed_row_"] > [data-testid="stElementContainer"]:last-child{justify-self:end;width:auto!important}
[class*="st-key-completed_row_"] [data-testid="stMarkdownContainer"]{margin:0!important}
[class*="st-key-completed_row_"] [data-testid="stMarkdownContainer"] p{margin:0!important}
[class*="st-key-completed_row_"] .task-completed-banner{background:transparent!important;border:0!important;padding:0!important;margin:0!important;gap:10px}
[class*="st-key-open_delete_"] button{display:inline-flex!important;align-items:center!important;justify-content:center!important;gap:5px!important;min-height:32px!important;padding:5px 10px!important;background:#fff7f7!important;color:#b83b45!important;border:1px solid #efc9cd!important;border-radius:7px!important;box-shadow:none!important;white-space:nowrap}
[class*="st-key-open_delete_"] button p{font-size:12px!important;font-weight:650!important;line-height:1.2!important;white-space:nowrap}
[class*="st-key-open_delete_"] button:hover{background:#fff0f0!important;border-color:#db9099!important}
[class*="st-key-open_task_edit_"] button{min-height:31px!important;padding:5px 10px!important;background:#f7faff!important;color:#42648e!important;border:1px solid #d9e4f2!important;border-radius:7px!important;box-shadow:none!important;gap:5px!important}
[class*="st-key-open_task_edit_"] button p{font-size:11px!important;font-weight:600!important;line-height:1.3!important}
[class*="st-key-open_task_edit_"] button:hover{background:#edf4ff!important;color:#245fc2!important;border-color:#b9ceec!important}
[class*="st-key-open_delete_"] [data-testid="stIconMaterial"],[class*="st-key-open_task_edit_"] [data-testid="stIconMaterial"]{font-size:16px!important;width:16px!important;height:16px!important;line-height:1!important}
@media(max-width:767px){[class*="st-key-completed_row_"]{padding:10px;gap:8px!important}}

@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap');
:root{--ink:#172641;--muted:#7283a0;--line:#e3eaf3;--blue:#2169ef}
html,body,.stApp,[class*="css"]{font-family:'Noto Sans KR',sans-serif}
.stApp{background:#f8fafd;color:var(--ink)}
/* 상단 Streamlit 도구모음과 페이지 제목이 겹치지 않도록 안전한 공간 확보 */
.block-container{max-width:1900px;padding:3.85rem 2rem 3rem!important}
[data-testid="stAppViewBlockContainer"]{padding-top:3.85rem!important}
[data-testid="stHeader"]{background:transparent!important}
@media(max-width:1050px){[data-testid="stAppViewBlockContainer"]{padding-top:3.65rem!important}}
h1,h2,h3{color:#172641!important;letter-spacing:-.04em;font-weight:800!important}
h1{font-size:1.8rem!important;margin-bottom:.2rem!important}
[data-testid="stSidebar"]{background:linear-gradient(155deg,#253b58,#1b2d47);border-right:0}
[data-testid="stSidebar"] [data-testid="stSidebarContent"]{padding-top:1.5rem}
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3,[data-testid="stSidebar"] p,[data-testid="stSidebar"] label{color:#eaf1ff!important}
[data-testid="stSidebar"] [role="radiogroup"] label{padding:10px 12px;margin:3px 0;border-radius:9px;cursor:pointer}
/* 메뉴 앞의 Streamlit 라디오 선택 원형 표시만 숨김 (기능은 유지) */
[data-testid="stSidebar"] [role="radiogroup"] label [data-testid="stRadioButtonIcon"],
[data-testid="stSidebar"] [role="radiogroup"] label [data-baseweb="radio"],
[data-testid="stSidebar"] [role="radiogroup"] label input[type="radio"],
[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child:has(input[type="radio"]){display:none!important}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:#31568c!important;border-radius:9px}
[data-testid="stSidebar"] [role="radiogroup"] label p{margin:0!important}
[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:#355577}
[data-testid="stSidebar"] [data-testid="stAlert"]{background:#304762;color:white;border:1px solid #536987}
[data-testid="stSidebar"] button{background:#344d6b;color:#fff;border:1px solid #58708e}
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
.cal-day{position:relative}
.cal-day a.day-num{text-decoration:none!important}
.cal-day a.day-num::after{content:'';position:absolute;inset:0;cursor:pointer}
.cal-day:has(a.day-num:hover){background:#f0f6ff}
.cal-day .cal-event{position:relative;z-index:1}
.cal-day.outside{background:#fafbfd}
.cal-day .day-num{font-size:13px;color:#243754;font-weight:750;margin-bottom:8px}
.cal-day.outside .day-num{color:#a8b6cb}
.cal-day .day-num.today{display:inline-block;background:#2169ef;color:#fff;padding:3px 8px;border-radius:20px}
.cal-weekdays > div:first-child,.cal-day:nth-child(7n+1) .day-num{color:#dc2626}
.cal-weekdays > div:last-child,.cal-day:nth-child(7n) .day-num{color:#2563eb}
.cal-day.outside:nth-child(7n+1) .day-num{color:#e9a0a0}
.cal-day.outside:nth-child(7n) .day-num{color:#9eb9ec}
.cal-day:nth-child(7n+1) .day-num.today{background:#dc2626;color:#fff}
.cal-day:nth-child(7n) .day-num.today{background:#2563eb;color:#fff}
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
@media(max-width:1050px){.block-container{padding:3.65rem .7rem 2rem!important}.cal-day{min-height:108px;padding:5px 3px}.cal-event{font-size:9px;padding:4px}.cal-event .event-sub{font-size:9px}}

.task-card-top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin:2px 0 10px}
.task-card-title{font-size:17px;font-weight:800;color:#192c49}
.task-tags{display:flex;gap:7px}.task-tags span{font-size:12px;font-weight:700;border-radius:30px;padding:5px 11px}
.task-card-meta{font-size:12px;color:#71819b;margin-bottom:13px;line-height:1.8}
[data-testid="stVerticalBlockBorderWrapper"]:has(.task-card-top){border-radius:16px!important;box-shadow:0 4px 18px rgba(31,67,122,.045)!important}

.new-task-banner{background:linear-gradient(120deg,#1557d6,#428bff);border-radius:16px;padding:21px 19px;color:white;margin:0 0 12px;box-shadow:0 10px 22px rgba(27,95,218,.17)}
.new-task-kicker{font-size:10px;letter-spacing:.15em;font-weight:800;opacity:.82;margin-bottom:8px}
.new-task-title{font-size:22px;font-weight:800;letter-spacing:-.035em}
.new-task-desc{font-size:12px;margin-top:7px;color:#e9f2ff}
.form-section-label{font-size:12px;font-weight:800;color:#2465d6;margin:18px 0 9px;padding:8px 10px;background:#f0f6ff;border-left:3px solid #2874ee;border-radius:5px}
@media(min-width:1100px){[data-testid="stColumn"]:has(.new-task-banner) [data-testid="stVerticalBlockBorderWrapper"]{border-radius:16px!important}}

/* Compact task cards and clear field-value pairs */
.task-card-top{margin:0 0 5px!important;gap:8px!important}
.task-card-title{font-size:15px!important;line-height:1.4!important}
.task-tags span{font-size:11px!important;padding:3px 9px!important}
.task-card-meta{display:flex;flex-wrap:wrap;gap:6px;margin:5px 0 7px!important;line-height:1.3!important}
.task-card-meta span{display:inline-flex;align-items:center;gap:6px;background:#f4f7fc;border:1px solid #e8edf5;padding:5px 8px;border-radius:7px;color:#334966;font-size:11px}
.task-card-meta b{color:#7183a0;font-weight:700}
.task-form-section{display:flex;align-items:center;gap:10px;margin:18px 0 12px;padding-bottom:9px;border-bottom:1px solid #e4eaf2;color:#263e60;font-size:14px;font-weight:750}
.task-form-section b{display:inline-flex;align-items:center;justify-content:center;width:25px;height:25px;border-radius:7px;background:#edf3fc;color:#3067b0;font-size:11px}
.task-form-footer{margin:12px 0 8px;font-size:12px;color:#7b889b}
[data-testid="stForm"]:has(.task-form-marker){background:#fff!important;border:1px solid #dfe6ef!important;border-radius:14px!important;padding:22px!important;box-shadow:0 6px 24px rgba(31,55,85,.04)}
[data-testid="stForm"]:has(.task-form-marker) [data-testid="stWidgetLabel"] p{font-size:12px!important;font-weight:650!important;color:#42536c}
[data-testid="stForm"]:has(.task-form-marker) input,[data-testid="stForm"]:has(.task-form-marker) textarea{border-radius:8px!important;background:#f8fafc!important}
[data-testid="stForm"]:has(.task-form-marker) [data-testid="stFormSubmitButton"] button{min-height:44px!important;border-radius:9px!important;font-size:14px!important}
@media(max-width:767px){[data-testid="stForm"]:has(.task-form-marker){padding:14px!important}}
[data-testid="stVerticalBlockBorderWrapper"]:has(.task-card-top){padding:12px 14px!important}
[data-testid="stVerticalBlockBorderWrapper"]:has(.task-card-top) [data-testid="stExpander"]{margin-top:4px!important}
[data-testid="stVerticalBlockBorderWrapper"]:has(.task-card-top) [data-testid="stProgress"]{margin-bottom:0!important}
/* Clear, denser new-task form */
[data-testid="stColumn"]:has(.new-task-banner) [data-testid="stForm"] label p{font-size:12px;font-weight:700;color:#334767}
[data-testid="stColumn"]:has(.new-task-banner) [data-testid="stForm"] [data-testid="stVerticalBlock"]{gap:.45rem}
[data-testid="stColumn"]:has(.new-task-banner) [data-testid="stForm"] textarea{min-height:64px!important}
[data-testid="stColumn"]:has(.new-task-banner) [data-testid="stForm"] [data-testid="stFormSubmitButton"] button{min-height:43px;border-radius:10px;font-weight:800}
.new-task-banner{padding:15px 16px!important;margin-bottom:7px!important}
.new-task-title{font-size:19px!important}.new-task-desc{font-size:11px!important}
.form-section-label{margin:10px 0 5px!important;padding:6px 9px!important;font-size:11px!important}

/* High-visibility, compact task management */
.task-list-head{background:linear-gradient(100deg,#eaf2ff,#f6f9ff);border:1px solid #c8dbff;border-left:5px solid #2469ed;border-radius:12px;padding:12px 16px;margin:4px 0 12px}
.task-list-head strong{display:block;color:#143d83;font-size:17px;font-weight:850}
.task-list-head small{color:#48658d;font-size:12px}
[data-testid="stVerticalBlockBorderWrapper"]:has(.task-card-top){border:1px solid #cddbf0!important;border-left:5px solid #2469ed!important;background:#fff!important;box-shadow:0 5px 15px rgba(32,85,170,.07)!important;margin-bottom:9px!important;padding:13px 16px!important}
[data-testid="stVerticalBlockBorderWrapper"]:has(.task-card-top):hover{border-color:#83aaf0!important;box-shadow:0 7px 20px rgba(32,85,170,.13)!important}
.task-card-title{font-size:17px!important;color:#102d57!important;font-weight:850!important}
.task-card-meta{gap:7px!important;margin:8px 0!important}
.task-card-meta span{background:#edf4ff!important;border:1px solid #d4e4fa!important;color:#203e6b!important;font-size:12px!important;padding:6px 9px!important}
.task-card-meta b{color:#225cb1!important;font-weight:800!important}
.task-tags span{font-size:12px!important;font-weight:800!important;padding:5px 11px!important}
[data-testid="stVerticalBlockBorderWrapper"]:has(.task-card-top) [data-testid="stExpander"]{background:#f0f6ff!important;border:1px solid #c5dafb!important}
[data-testid="stVerticalBlockBorderWrapper"]:has(.task-card-top) [data-testid="stExpander"] summary p{font-weight:800!important;color:#1556b5!important}
.new-task-banner{background:linear-gradient(120deg,#104dbd,#2679ff)!important;border:2px solid #91baff!important;box-shadow:0 10px 24px rgba(28,89,210,.2)!important;padding:19px!important}
.new-task-title{font-size:23px!important}
[data-testid="stColumn"]:has(.new-task-banner) [data-testid="stForm"]{border:2px solid #b7d2ff!important;border-radius:14px!important;padding:14px!important;background:#fff!important}
[data-testid="stColumn"]:has(.new-task-banner) [data-testid="stForm"] label p{font-size:13px!important;font-weight:800!important;color:#1d3d70!important}
[data-testid="stColumn"]:has(.new-task-banner) [data-testid="stForm"] input:focus,[data-testid="stColumn"]:has(.new-task-banner) [data-testid="stForm"] textarea:focus{border-color:#2169ef!important;box-shadow:0 0 0 2px #d9e8ff!important}
[data-testid="stColumn"]:has(.new-task-banner) [data-testid="stFormSubmitButton"] button{background:#155ee9!important;min-height:49px!important;font-size:15px!important;box-shadow:0 5px 12px rgba(27,91,209,.2)!important}
.form-section-label{font-size:12px!important;background:#e6f0ff!important;color:#154eaa!important;border-left:4px solid #2169ef!important;padding:9px 11px!important}
@media(max-width:850px){.task-card-title{font-size:15px!important}.task-card-meta span{font-size:11px!important}}

.edit-intro{background:#e5efff;border-left:5px solid #2169ef;padding:13px 15px;border-radius:10px;margin:6px 0 12px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;justify-content:space-between}
.edit-intro strong{font-size:16px;color:#164a9c}.edit-intro span{font-size:12px;color:#496b99}
.edit-section{background:#eef5ff;border-left:4px solid #2169ef;border-radius:8px;padding:10px 12px;margin:13px 0 8px;color:#164a9c;font-size:14px;font-weight:800}
.edit-section small{color:#5e789b;font-size:11px;font-weight:500;margin-left:10px}
.edit-save-hint{background:#edf9f2;border:1px solid #bde5ce;color:#167448;border-radius:9px;padding:11px;font-size:12px;font-weight:700;margin:14px 0 7px}
[data-testid="stVerticalBlockBorderWrapper"]:has(.task-card-top) [data-testid="stExpander"] details[open]{background:#fff!important}
[data-testid="stVerticalBlockBorderWrapper"]:has(.task-card-top) [data-testid="stForm"]{background:white!important;border:1px solid #d6e3f4!important;border-radius:12px!important;padding:14px!important}
[data-testid="stVerticalBlockBorderWrapper"]:has(.task-card-top) [data-testid="stForm"] label p{font-size:13px!important;font-weight:800!important;color:#1b467d!important}
[data-testid="stVerticalBlockBorderWrapper"]:has(.task-card-top) [data-testid="stFormSubmitButton"] button{background:#165fe7!important;color:white!important;min-height:48px!important;font-size:15px!important;font-weight:800!important;border-radius:9px!important}

/* New-task form: aligned headings, distinct groups, and consistent field spacing */
[data-testid="stColumn"]:has(.new-task-banner) .form-section-label{
  margin:24px 0 0!important;padding:11px 13px!important;
  font-size:13px!important;line-height:1.45!important;
  background:#e7f0ff!important;border-left:4px solid #2267ed!important;
  border-radius:8px!important;box-sizing:border-box!important;
}
[data-testid="stColumn"]:has(.new-task-banner) .section-caption{
  margin:10px 0 16px!important;padding:0 2px!important;
  color:#62758e!important;font-size:11px!important;line-height:1.6!important;
}
[data-testid="stColumn"]:has(.new-task-banner) [data-testid="stForm"] [data-testid="stVerticalBlock"]{
  gap:.85rem!important;
}
[data-testid="stColumn"]:has(.new-task-banner) [data-testid="stForm"] [data-testid="stHorizontalBlock"]{
  gap:14px!important;align-items:start!important;
}
[data-testid="stColumn"]:has(.new-task-banner) [data-testid="stForm"] [data-testid="stWidgetLabel"]{
  margin-bottom:7px!important;
}
[data-testid="stColumn"]:has(.new-task-banner) [data-testid="stForm"] [data-testid="stWidgetLabel"] p{
  font-size:12px!important;line-height:1.5!important;
}
[data-testid="stColumn"]:has(.new-task-banner) [data-testid="stForm"] input,
[data-testid="stColumn"]:has(.new-task-banner) [data-testid="stForm"] textarea{
  border-radius:9px!important;
}
[data-testid="stColumn"]:has(.new-task-banner) [data-testid="stFormSubmitButton"]{
  margin-top:10px!important;
}


/* Meeting-specific visual hierarchy */
.meeting-hero{background:linear-gradient(110deg,#eaf2ff,#f8fbff);border:1px solid #cbdfff;border-left:5px solid #2468ed;border-radius:14px;padding:15px 19px;margin:6px 0 18px}
.meeting-hero strong{display:block;color:#153c81;font-size:19px;font-weight:850;margin-bottom:4px}
.meeting-hero span{color:#587193;font-size:12px}
.meeting-list-card{padding:3px 0 2px}
.meeting-list-title{font-size:18px;font-weight:850;color:#18355e;overflow-wrap:anywhere;line-height:1.5;margin-bottom:9px}
.meeting-pills{display:flex;flex-wrap:wrap;gap:7px;margin:9px 0}
.meeting-pills span{background:#edf4ff;color:#285da5;border:1px solid #d8e7ff;border-radius:7px;padding:5px 9px;font-size:11px;font-weight:750}
.meeting-excerpt{background:#f5f8fc;border-radius:9px;padding:10px 12px;color:#50647f;font-size:12px;line-height:1.65;overflow-wrap:anywhere;margin:9px 0}
.meeting-detail-header{background:linear-gradient(105deg,#e8f2ff,#f8fbff);border-left:5px solid #2169ef;border-radius:10px;padding:15px;margin:0 0 14px}
.meeting-detail-header strong{font-size:20px;color:#143867;overflow-wrap:anywhere}
.meeting-detail-header small{display:block;margin-top:8px;color:#627895}
.meeting-section{font-size:14px;font-weight:850;color:#1d529d;background:#edf5ff;border-left:4px solid #2b75ed;border-radius:7px;padding:10px 12px;margin:18px 0 9px}
.meeting-body{background:#fff;border:1px solid #e0e9f5;border-radius:10px;padding:14px 15px;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.75;font-size:13px;color:#344763;min-height:48px}
.meeting-date-box{background:#eaf2ff;border-radius:11px;text-align:center;padding:12px 4px;color:#2c5b9b;font-size:13px;font-weight:800}
.meeting-date-box strong{font-size:25px;color:#143e81}
[data-testid="stVerticalBlockBorderWrapper"]:has(.meeting-list-card){border:1px solid #d7e4f7!important;border-left:4px solid #3477ed!important;border-radius:14px!important;box-shadow:0 4px 15px rgba(25,72,142,.06)!important;padding:15px!important;margin-bottom:10px}
[data-testid="stVerticalBlockBorderWrapper"]:has(.meeting-detail-header){border:1px solid #d1e0f5!important;border-radius:15px!important;padding:17px!important;background:#fbfdff!important}


.meeting-topbar{display:flex;justify-content:space-between;align-items:center;gap:18px;flex-wrap:wrap;margin:5px 0 20px}
.meeting-top-title{font-size:30px;font-weight:900;color:#142e53;line-height:1.3}
.meeting-top-title small{display:block;font-size:12px;font-weight:450;color:#71819b;margin-top:9px}
.meeting-mini-stats{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}
.meeting-mini-stat{background:#fff;border:1px solid #dce7f7;border-radius:10px;padding:9px 12px;min-width:94px;display:flex;align-items:center;gap:10px;box-shadow:0 2px 9px rgba(30,75,140,.04)}
.meeting-mini-stat span{font-size:11px;color:#607796;white-space:nowrap}
.meeting-mini-stat b{font-size:16px;color:#143a75;white-space:nowrap}
.meeting-filter-title{background:#eaf2ff;border-left:4px solid #2468ef;border-radius:9px;padding:12px 15px;color:#17498e;font-size:15px;font-weight:850;margin:12px 0 10px}
.meeting-filter-title small{display:block;font-size:11px;color:#6981a4;font-weight:450;margin-top:4px}

/* 달력 상세정보 팝업 전용 스타일: 달력과 다른 페이지에는 영향 없음 */
[data-testid="stDialog"]:has(.cal-detail-marker) [data-testid="stDialogContent"]{background:#f8fbff}
.cal-detail-marker{display:none}
.cal-detail-hero{background:linear-gradient(110deg,#eaf2ff,#f8fbff);border:1px solid #cddfff;border-left:5px solid #2469ed;border-radius:14px;padding:19px 21px;margin:3px 0 14px}
.cal-detail-kicker{color:#2765c5;font-size:12px;font-weight:800;margin-bottom:8px}
.cal-detail-title{font-size:22px;font-weight:850;color:#142d52;line-height:1.4;margin-bottom:12px;overflow-wrap:anywhere}
.cal-detail-pills{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:12px}
.cal-detail-pills span{font-size:12px;font-weight:700;color:#285b9f;background:white;border:1px solid #d8e5fa;border-radius:7px;padding:6px 10px}
.cal-detail-dates{font-size:12px;color:#516a8e;margin-bottom:14px}
.cal-detail-progress-label{display:flex;justify-content:space-between;color:#28578f;font-size:12px;margin-bottom:7px}
.cal-detail-progress-label strong{font-size:14px;color:#175ed7}
.cal-detail-track{height:9px;background:#dbe7fa;border-radius:20px;overflow:hidden}
.cal-detail-track div{height:100%;background:linear-gradient(90deg,#2865ec,#58a1ff);border-radius:20px}
.cal-detail-content{background:#fff;border:1px solid #e1e9f5;border-radius:12px;padding:16px 19px;margin:0 0 14px}
.cal-detail-content b{display:block;color:#173e79;font-size:14px;margin-bottom:10px}
.cal-detail-content div{font-size:13px;color:#3c506d;line-height:1.8;overflow-wrap:anywhere}
[data-testid="stDialog"]:has(.cal-detail-marker) [data-testid="stExpander"]{border:1px solid #b9d2fb!important;border-radius:12px!important;overflow:hidden;background:#fff}
[data-testid="stDialog"]:has(.cal-detail-marker) [data-testid="stExpander"] summary{background:#eaf2ff!important;padding:12px!important}
[data-testid="stDialog"]:has(.cal-detail-marker) [data-testid="stExpander"] summary p{color:#164eac!important;font-weight:800!important}
[data-testid="stDialog"]:has(.cal-detail-marker) [data-testid="stForm"]{border:0!important;background:#fff!important}
[data-testid="stDialog"]:has(.cal-detail-marker) [data-testid="stForm"] label p{font-weight:750!important;color:#263f66!important;font-size:12px!important}
.cal-edit-section{background:#eaf2ff;border-left:4px solid #2169ef;color:#1e64cc;padding:11px 13px;border-radius:7px;margin:17px 0 12px;font-weight:850;font-size:13px}
.cal-edit-section span{color:#173d78;margin-left:8px}
[data-testid="stDialog"]:has(.cal-detail-marker) [data-testid="stFormSubmitButton"] button{min-height:47px!important;font-weight:800!important;background:#2169ef!important;color:white!important;border-radius:9px!important}

/* 모바일 화면 전용 CSS — Python 위젯 구조와 PC 레이아웃은 그대로 유지 */
@media screen and (max-width: 700px) {
  .block-container, [data-testid="stAppViewBlockContainer"] {padding:3.6rem .65rem 2rem!important;max-width:100%!important;}
  .dashboard-head h1 {font-size:1.55rem!important;}
  .dashboard-head p {font-size:12px;line-height:1.55;}
  .cal-weekdays div {font-size:10px;padding:9px 0;}
  .cal-day {min-height:80px;padding:5px 2px;overflow:hidden;}
  .cal-day .day-num {font-size:11px;margin-bottom:4px;}
  .cal-event {font-size:9px;padding:3px 2px;margin:3px 0;}
  .cal-event .event-title {font-size:9px;}
  .cal-event .event-sub {display:none;}
  .cal-more {font-size:9px;margin:2px 0;}
  .cal-legend {justify-content:flex-start;gap:8px;font-size:10px;}
  .meeting-topbar {gap:10px;}
  .meeting-top-title {font-size:23px;}
  .meeting-mini-stats {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));width:100%;gap:7px;}
  .meeting-mini-stat {min-width:0;padding:8px;}
  .meeting-mini-stat span {font-size:10px;white-space:normal;}
  .meeting-mini-stat b {font-size:13px;}
  .task-card-title {font-size:15px!important;overflow-wrap:anywhere;}
  .task-tags {flex-wrap:wrap;}
  .task-card-meta span {overflow-wrap:anywhere;}
  .new-task-banner {padding:13px!important;}
  .new-task-title {font-size:19px!important;}
  .meeting-list-title {font-size:15px;}
  .cal-detail-hero {padding:13px;}
  .cal-detail-title {font-size:18px;}
  [data-testid="stDataFrame"] {max-width:100%;}
}

/* 2026-10-23: 모바일 전용 정렬 개선. PC 및 Python 로직 변경 없음. */
@media screen and (max-width: 767px) {
  html, body, .stApp {overflow-x:hidden!important;}
  [data-testid="stAppViewBlockContainer"] {padding:3.35rem 12px 2rem!important;max-width:100%!important;}
  [data-testid="stMainBlockContainer"] {max-width:100%!important;}
  .dashboard-head {margin:0 0 12px!important;}
  .dashboard-head h1 {font-size:1.55rem!important;line-height:1.3!important;}
  .dashboard-head p {font-size:12px!important;line-height:1.6!important;}
  /* 달력 상단 6개 컬럼을 모바일에서 2행으로 재배치 */
  [data-testid="stHorizontalBlock"]:has(.st-key-month_prev):has(.st-key-month_next) {
    display:grid!important;grid-template-columns:44px minmax(0,1fr) 44px!important;
    gap:8px!important;align-items:center!important;
  }
  [data-testid="stHorizontalBlock"]:has(.st-key-month_prev):has(.st-key-month_next) > [data-testid="stColumn"] {
    width:auto!important;min-width:0!important;flex:none!important;
  }
  [data-testid="stHorizontalBlock"]:has(.st-key-month_prev):has(.st-key-month_next) > [data-testid="stColumn"]:nth-child(1){grid-column:1;grid-row:1;}
  [data-testid="stHorizontalBlock"]:has(.st-key-month_prev):has(.st-key-month_next) > [data-testid="stColumn"]:nth-child(2){grid-column:2;grid-row:1;text-align:center;}
  [data-testid="stHorizontalBlock"]:has(.st-key-month_prev):has(.st-key-month_next) > [data-testid="stColumn"]:nth-child(2) h3{font-size:1.2rem!important;margin:0!important;white-space:nowrap;}
  [data-testid="stHorizontalBlock"]:has(.st-key-month_prev):has(.st-key-month_next) > [data-testid="stColumn"]:nth-child(3){grid-column:3;grid-row:1;}
  [data-testid="stHorizontalBlock"]:has(.st-key-month_prev):has(.st-key-month_next) > [data-testid="stColumn"]:nth-child(4){grid-column:1 / 2;grid-row:2;}
  [data-testid="stHorizontalBlock"]:has(.st-key-month_prev):has(.st-key-month_next) > [data-testid="stColumn"]:nth-child(5){display:none!important;}
  [data-testid="stHorizontalBlock"]:has(.st-key-month_prev):has(.st-key-month_next) > [data-testid="stColumn"]:nth-child(6){grid-column:2 / 4;grid-row:2;}
  [data-testid="stHorizontalBlock"]:has(.st-key-month_prev):has(.st-key-month_next) button{min-height:40px!important;padding:5px 6px!important;font-size:13px!important;}
  /* 달력은 좁은 화면에서도 7일을 보이되 일정 내용은 줄임 */
  .cal-shell{width:100%!important;max-width:100%!important;overflow:hidden!important;margin-top:10px!important;}
  .cal-weekdays{grid-template-columns:repeat(7,minmax(0,1fr))!important;}
  .cal-weekdays > *{min-width:0!important;font-size:10px!important;padding:9px 0!important;}
  .cal-day{min-width:0!important;min-height:73px!important;padding:5px 2px!important;overflow:hidden!important;}
  .cal-day .day-num{font-size:11px!important;margin-bottom:4px!important;}
  .cal-event{min-width:0!important;padding:3px 2px!important;margin:2px 0!important;border-radius:4px!important;}
  .cal-event .event-title{font-size:9px!important;line-height:1.35!important;overflow:hidden!important;text-overflow:ellipsis!important;}
  .cal-event .event-sub{display:none!important;}
  .cal-legend{justify-content:flex-start!important;gap:7px!important;font-size:10px!important;}
  /* 카드, 회의록, 업무 입력란 가독성 */
  .task-card-top{align-items:flex-start!important;}
  .task-card-title{font-size:15px!important;line-height:1.45!important;overflow-wrap:anywhere!important;}
  .task-tags,.task-card-meta,.meeting-pills{flex-wrap:wrap!important;gap:5px!important;}
  .task-card-meta span,.meeting-pills span{max-width:100%!important;overflow-wrap:anywhere!important;}
  .new-task-banner{padding:14px!important;border-radius:12px!important;}
  .new-task-title{font-size:19px!important;}
  .meeting-hero{padding:13px!important;}
  .meeting-list-title{font-size:15px!important;overflow-wrap:anywhere!important;}
  .meeting-mini-stats{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:7px!important;}
  [data-testid="stDataFrame"], [data-testid="stDataEditor"]{max-width:100%!important;}
  [data-testid="stForm"] input,[data-testid="stForm"] textarea{font-size:16px!important;}
  [data-testid="stDialog"] [role="dialog"]{max-width:calc(100vw - 16px)!important;}
}

/* 완료 상태는 진행률과 별개로 진행상태=완료일 때만 강조합니다. */
.task-completed-banner{display:flex;align-items:center;gap:10px;background:#eaf8ef;border:1px solid #a8dfb9;border-radius:10px;padding:10px 13px;margin:0 0 12px;color:#126b39}
.task-completed-icon{display:flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;background:#18864b;color:white;font-size:17px;font-weight:800;flex-shrink:0}
.task-completed-banner strong{display:block;font-size:13px;font-weight:750}
.task-completed-banner small{display:block;font-size:11px;color:#327c52;margin-top:2px}
.task-completed-title-tag{display:inline-block;vertical-align:middle;background:#168449;color:#fff;border-radius:7px;padding:3px 8px;margin-left:6px;font-size:12px;font-weight:800;white-space:nowrap}
@media(max-width:767px){.task-completed-banner{padding:9px 11px;gap:8px}.task-completed-title-tag{margin:5px 0 0 0}}

/* 업무 마감 D-day 상태: 완료 업무에는 지연 경고를 표시하지 않음 */
.task-deadline-banner{display:flex;align-items:center;gap:10px;border-radius:10px;padding:10px 13px;margin:0 0 11px;font-weight:800}
.task-deadline-banner strong{display:block;font-size:14px}
.task-deadline-banner small{display:block;font-size:12px;font-weight:500;margin-top:3px}
.task-deadline-overdue{background:#fff0f0;border:1px solid #f1aaaa;color:#b4232b}
.task-deadline-tomorrow{background:#fff6e7;border:1px solid #f2cb81;color:#935800}
.task-deadline-today{background:#fff6e7;border:1px solid #f2cb81;color:#935800}
.task-dday-tag{display:inline-flex;align-items:center;border-radius:7px;padding:4px 8px;font-size:12px;font-weight:800;white-space:nowrap}
.task-dday-normal{background:#e9f2ff;color:#2258a7}
.task-dday-tomorrow,.task-dday-today{background:#fff0cc;color:#895500}
.task-dday-overdue{background:#ffe2e2;color:#b4232b}
.task-dday-completed{background:#e2f5e9;color:#168449}
.task-dday-none{background:#eef1f5;color:#637084}
@media(max-width:767px){.task-deadline-banner{padding:9px 10px}.task-dday-tag{white-space:normal}}


/* Compact sidebar navigation */
[data-testid="stSidebar"]{background:#fff!important;border-right:1px solid #e4eaf2!important;box-shadow:none!important}
[data-testid="stSidebar"] [data-testid="stSidebarContent"]{background:#fff!important;padding:1.5rem 1rem!important}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{gap:.5rem!important}
[data-testid="stSidebar"] h3{color:#213753!important;font-size:17px!important;font-weight:750!important;letter-spacing:-.04em;margin:0 0 18px!important}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] label{color:#57667a!important}
[data-testid="stSidebar"] [role="radiogroup"]{gap:4px!important}
[data-testid="stSidebar"] [role="radiogroup"] label{min-height:44px!important;padding:11px 14px!important;margin:0!important;border:0!important;border-radius:9px!important;background:transparent!important;box-shadow:none!important;transition:background .15s ease}
[data-testid="stSidebar"] [role="radiogroup"] label p{font-size:13px!important;font-weight:550!important;margin:0!important;color:#57667a!important}
[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:#f4f7fb!important}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:#edf3ff!important;box-shadow:inset 3px 0 0 #2563eb!important}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p{color:#245fc2!important;font-weight:750!important}
[data-testid="stSidebar"] [role="radiogroup"] label [data-testid="stRadioButtonIcon"],
[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child:not([data-testid="stMarkdownContainer"]){display:none!important}
[data-testid="stSidebar"] [data-testid="stSelectbox"]{margin-top:12px}
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div{background:#f8fafc!important;border:1px solid #e3e9f1!important;border-radius:9px!important;color:#344054!important}
[data-testid="stSidebar"] button{background:#fff!important;color:#65758b!important;border:1px solid #e3e9f1!important;border-radius:9px!important;box-shadow:none!important;min-height:38px}
[data-testid="stSidebar"] button:hover{background:#f4f7fb!important;color:#245fc2!important;border-color:#c8d8ef!important}
[data-testid="stSidebar"] hr{border-color:#e9edf3!important;margin:14px 0!important}
@media(max-width:767px){[data-testid="stSidebar"] [data-testid="stSidebarContent"]{padding:1rem .85rem!important}}
/* Calendar page: unified typography, spacing and responsive reading */
.cal-page-header{display:flex;align-items:center;justify-content:space-between;gap:24px;margin:0 0 26px}
.cal-page-header h1{font-size:28px!important;font-weight:750!important;letter-spacing:-.045em;margin:0!important;padding:0!important}
.cal-page-header p{font-size:13px;color:#7a889c;margin:7px 0 0}
.cal-overview{display:flex;gap:0;border:1px solid #e2e8f0;background:#fff;border-radius:12px;padding:12px 4px}
.cal-overview>div{padding:0 24px;border-right:1px solid #edf0f5;min-width:100px}
.cal-overview>div:last-child{border:0}
.cal-overview span{display:block;font-size:11px;color:#7a889c;margin-bottom:5px}
.cal-overview b{font-size:22px;font-weight:700;color:#263d5d;line-height:1}
.cal-overview .complete b{color:#25805b}
.cal-month-title{font-size:22px;font-weight:700;letter-spacing:-.04em;color:#243853;text-align:center;padding:4px 0;white-space:nowrap}
.st-key-month_prev button,.st-key-month_next button,.st-key-calendar_today button{background:#fff!important;border:1px solid #dde5ef!important;color:#52677f!important;min-height:40px!important;box-shadow:none!important}
.st-key-month_prev button:hover,.st-key-month_next button:hover,.st-key-calendar_today button:hover{background:#eff4fc!important;border-color:#bdcfea!important}
.cal-context{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:15px 0 2px;color:#8290a3;font-size:11px}
.cal-context strong{font-weight:600;color:#52677f}
.cal-shell{margin-top:10px!important;border:1px solid #dfe6ef;border-radius:14px;background:#fff;box-shadow:0 5px 20px rgba(36,55,83,.035)}
.cal-weekdays{background:#f8fafc;border-bottom:1px solid #e2e8f0}
.cal-weekdays div{font-size:12px;padding:14px 0;letter-spacing:.03em;color:#7b889a;border-right:1px solid #edf0f5;font-weight:600}
.cal-weekdays div:last-child{border-right:0}
.cal-day{min-height:154px;padding:10px 9px;border-color:#edf0f5;transition:background .15s ease}
.cal-day:nth-child(7n){border-right:0}
.cal-day.is-today{background:#f7faff;box-shadow:inset 0 0 0 1px #cbdcfa}
.cal-day.outside{background:#fbfcfe}
.cal-day:has(a.day-num:hover){background:#f4f7fc}
.cal-date-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;min-height:27px}
.cal-day .day-num{display:inline-flex;align-items:center;justify-content:center;width:27px;height:27px;font-size:12px;font-weight:650;margin:0;padding:0!important;border-radius:8px}
.cal-day .day-num.today{display:inline-flex;background:#2864da;color:#fff;border-radius:8px;box-shadow:0 2px 5px #2864da20}
.cal-day.outside .day-num{color:#b4becc}
.cal-day-count{font-size:10px;color:#9aa7b7;padding-right:2px}
.cal-event{padding:5px 7px;margin:3px 0;border-radius:6px;font-size:11px;line-height:1.35;transition:box-shadow .15s ease,transform .15s ease;border-left-width:3px!important}
.cal-event:hover{box-shadow:0 3px 9px #24375312;transform:translateY(-1px)}
.cal-event:focus-visible,.cal-day a.day-num:focus-visible{outline:2px solid #2563eb;outline-offset:2px}
.cal-event .event-title{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:11px;font-weight:650;line-height:1.4}
.cal-event .event-sub{display:flex;align-items:center;justify-content:space-between;margin-top:3px;gap:4px;font-size:10px;line-height:1.3}
.cal-event .event-owner{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0;flex:1}
.cal-event .event-sub b{font-size:9px;opacity:.8;font-weight:600;flex-shrink:0}
.cal-event .track{height:3px;flex:0 1 36px;min-width:18px;max-width:36px;margin:0;border-radius:3px;background:#ffffff90;overflow:hidden}
.cal-event .fill{height:100%;border-radius:3px}
.cal-more{font-size:10px;font-weight:600;color:#70829a;margin:7px 3px}
.cal-legend{display:flex;align-items:center;justify-content:flex-start;flex-wrap:wrap;gap:8px 18px;padding:16px 2px;font-size:11px;color:#65758c}
.cal-legend>span{display:inline-flex;align-items:center;gap:6px}
.cal-legend i{width:7px;height:7px;border-radius:50%;margin:0}
.cal-scroll-hint{display:none}
@media(max-width:1050px){.cal-day{padding:8px 6px;min-height:140px}.cal-event{padding:5px 6px}.cal-overview>div{padding:0 16px;min-width:80px}}
@media(max-width:767px){
 .cal-page-header{align-items:flex-start;flex-direction:column;gap:16px;margin-bottom:20px}
 .cal-page-header h1{font-size:24px!important}.cal-page-header p{font-size:12px}
 .cal-overview{width:100%;padding:10px 0}.cal-overview>div{flex:1;padding:0 18px;min-width:0}.cal-overview b{font-size:20px}
 .cal-month-title{font-size:19px}
 .cal-context{align-items:flex-start;flex-direction:column;gap:5px;font-size:10px}
 .cal-shell{overflow-x:auto!important;overscroll-behavior-x:contain;-webkit-overflow-scrolling:touch;border-radius:10px}
 .cal-weekdays,.cal-grid{min-width:735px!important;grid-template-columns:repeat(7,minmax(0,1fr))!important}
 .cal-weekdays>div{font-size:11px!important;padding:12px 0!important}
 .cal-day{min-height:140px!important;padding:8px 6px!important}
 .cal-day .day-num{font-size:12px!important;margin:0!important}
 .cal-event{font-size:11px!important;padding:5px 6px!important;margin:3px 0!important}
 .cal-event .event-title{font-size:11px!important}
 .cal-event .event-sub{display:flex!important;font-size:10px!important}
 .cal-scroll-hint{display:block;color:#94a0b1;font-size:10px;margin-top:8px}
 .cal-legend{font-size:11px!important;gap:10px 14px!important}
}

/* 업무 카드 배지: 담당자별 지정색 / 업무구분별 지정색 */
.task-card-meta span.meta-owner{background:var(--badge-bg,#f1f5f9)!important;border-color:var(--badge-border,#cbd5e1)!important;color:var(--badge-fg,#526174)!important}
.task-card-meta span.meta-owner b{color:inherit!important}
.task-card-meta span.meta-category{background:var(--badge-bg,#e5f7f3)!important;border-color:var(--badge-border,#b9e5d9)!important;color:var(--badge-fg,#137b69)!important}
.task-card-meta span.meta-category b{color:inherit!important}
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

def build_person_labels(team):
    labels={}
    for row in team.to_dict('records'):
        name=safe(row.get('이름'))
        value=row.get('직급')
        rank=safe(value) if pd.notna(value) else ''
        if name and name not in ('전체','미지정'):
            labels[name]=f'{name} {rank}' if rank and not name.endswith(' '+rank) else name
    return labels

def person_label(name):
    name=safe(name)
    return globals().get('PERSON_LABELS',{}).get(name,name)

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

def delete_completed_record(svc, record_id):
    """Delete exactly one completed task from the integrated sheet by stable ID."""
    rows = read_tab(svc, TAB)
    matches = rows.index[rows['통합ID'] == record_id].tolist() if not rows.empty else []
    if len(matches) != 1:
        raise RuntimeError('삭제 대상이 없거나 ID가 중복되어 삭제하지 않았습니다. 새로고침 후 확인하세요.')
    row_idx = matches[0]
    if safe(rows.iloc[row_idx].get('진행상태')) != '완료':
        raise RuntimeError('완료 상태인 업무만 삭제할 수 있습니다.')
    sheets = svc.spreadsheets().get(spreadsheetId=SID, fields='sheets(properties(sheetId,title))').execute().get('sheets', [])
    ids = [sh['properties']['sheetId'] for sh in sheets if sh['properties'].get('title') == TAB]
    if len(ids) != 1:
        raise RuntimeError('통합업무 시트를 확인할 수 없어 삭제하지 않았습니다.')
    # pandas index 0 is sheet row 2 (zero-based startIndex=1).
    svc.spreadsheets().batchUpdate(spreadsheetId=SID, body={'requests': [
        {'deleteDimension': {'range': {'sheetId': ids[0], 'dimension': 'ROWS',
                                       'startIndex': row_idx + 1, 'endIndex': row_idx + 2}}}
    ]}).execute()

@st.dialog('완료 업무 삭제 확인')
def confirm_completed_task_delete(svc, task_id):
    st.warning('복구할 수 없습니다. 정말 삭제하시겠습니까?')
    yes_col, no_col = st.columns(2)
    with yes_col:
        if st.button('예, 삭제합니다', key='confirm_yes_' + task_id,
                     type='primary', use_container_width=True):
            try:
                delete_completed_record(svc, task_id)
                st.session_state['task_deleted_notice'] = True
                st.rerun()
            except Exception as exc:
                st.error(f'삭제 실패: {exc}')
    with no_col:
        if st.button('아니요', key='confirm_no_' + task_id,
                     use_container_width=True):
            st.rerun()

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

def task_title_parts(value):
    title=safe(value)
    kind='공통'
    first=True
    while title.startswith(('｢개인｣','｢공통｣')):
        if first:kind='개인' if title.startswith('｢개인｣') else '공통'
        title=title[4:].strip()
        first=False
    return kind,title

def task_title_with_kind(value,kind):
    _,title=task_title_parts(value)
    return f'｢{kind}｣ {title}' if title else ''

def calendar_view_month(params,current=None,today=None):
    for value in (params.get('calendar_month'),current,params.get('calendar_date'),today or date.today()):
        try:
            parsed=value if isinstance(value,date) else date.fromisoformat(value)
            return parsed.replace(day=1)
        except (ValueError,TypeError):
            continue

def form(svc,people,existing=None,key='new',compact=False):
    old=existing or {}
    old_kind,old_title=task_title_parts(old.get('업무명'))
    with st.form('edit_'+key):
        st.markdown('<div class="task-form-marker"></div>',unsafe_allow_html=True)
        st.markdown('<div class="task-form-section"><b>01</b><span>업무 기본 정보</span></div>',unsafe_allow_html=True)
        name_col,scope_col=st.columns([2.5,1.2])
        title=name_col.text_input('업무명 *',value=old_title,placeholder='업무명을 입력하세요')
        task_kind=scope_col.radio('업무 범위',['개인','공통'],index=0 if old_kind=='개인' else 1,horizontal=True)
        st.caption('개인·공통 구분은 업무명에 표시됩니다. 열람 권한은 동일합니다.')
        detail=st.text_area('상세 내용',value=safe(old.get('상세내용')),placeholder='업무의 목적과 진행할 내용을 입력하세요.',height=88)
        st.markdown('<div class="task-form-section"><b>02</b><span>담당 및 분류</span></div>',unsafe_allow_html=True)
        if compact:
            company=st.text_input('관련 거래처 (선택)',value=safe(old.get('거래처')),placeholder='거래처명 입력')
            c2,c3=st.columns(2)
        else:
            c1,c2,c3=st.columns(3)
            company=c1.text_input('거래처',value=safe(old.get('거래처')),placeholder='거래처명 입력')
        options=list(dict.fromkeys(people+([safe(old.get('담당자'))] if safe(old.get('담당자')) else [])))
        options=['미지정','전체']+ [p for p in options if p and p not in ('미지정','전체')]
        owner=c2.selectbox('담당자',options,index=options.index(safe(old.get('담당자'))) if safe(old.get('담당자')) in options else 0,format_func=person_label)
        cat_options=list(dict.fromkeys(CATS+([safe(old.get('업무구분'))] if safe(old.get('업무구분')) else [])))
        category=c3.selectbox('업무구분',cat_options,index=cat_options.index(safe(old.get('업무구분'))) if safe(old.get('업무구분')) in cat_options else 0)
        st.markdown('<div class="task-form-section"><b>03</b><span>일정 및 진행 현황</span></div>',unsafe_allow_html=True)
        c1,c2,c3=st.columns(3)
        start=c1.date_input('시작일',value=dt(old.get('시작일')) or date.today())
        due=c2.date_input('마감일',value=dt(old.get('마감일')) or date.today())
        tm=c3.text_input('시작시간 (선택)',value=safe(old.get('시작시간')),placeholder='09:00')
        c1,c2=st.columns(2)
        state_opts=list(dict.fromkeys(STATES+([safe(old.get('진행상태'))] if safe(old.get('진행상태')) else [])))
        status=c1.selectbox('진행상태',state_opts,index=state_opts.index(safe(old.get('진행상태'))) if safe(old.get('진행상태')) in state_opts else 0)
        priority=c2.selectbox('우선순위',['낮음','보통','높음','긴급'],index=['낮음','보통','높음','긴급'].index(safe(old.get('우선순위'))) if safe(old.get('우선순위')) in ['낮음','보통','높음','긴급'] else 1)
        try:p=int(float(old.get('진행률') or 0))
        except (ValueError,TypeError):p=0
        progress=st.slider('진행률 (%)',0,100,max(0,min(100,p)))
        with st.expander('메모 및 첨부파일 · 선택 입력',expanded=bool(old.get('메모') or old.get('첨부파일URL'))):
            memo=st.text_area('메모 (선택)',value=safe(old.get('메모')),height=80,placeholder='참고사항이나 인수인계 내용을 입력하세요.')
            link=st.text_input('첨부파일 링크 (선택)',value=safe(old.get('첨부파일URL')),placeholder='https://…')
        st.markdown('<div class="task-form-footer">필수 항목을 확인한 후 저장해 주세요.</div>',unsafe_allow_html=True)
        if st.form_submit_button('저장',type='primary',use_container_width=True):
            saved_title=task_title_with_kind(title,task_kind)
            if not saved_title:st.error('업무명을 입력하세요.');return
            if due<start:st.error('마감일은 시작일 이후여야 합니다.');return
            if tm:
                try:datetime.strptime(tm,'%H:%M')
                except ValueError:st.error('시작시간은 14:00 형식으로 입력하세요.');return
            now=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            rec={k:safe(old.get(k)) for k in HEAD}
            rec.update({'통합ID':safe(old.get('통합ID')) or uuid.uuid4().hex,'원본시트':safe(old.get('원본시트')) or '통합업무',
             '원본ID':safe(old.get('원본ID')) or uuid.uuid4().hex,'업무명':saved_title,'상세내용':detail,
             '거래처':company,'담당자':'' if owner=='미지정' else owner,'업무구분':category,
             '시작일':start.isoformat(),'마감일':due.isoformat(),'시작시간':tm,'진행상태':('완료' if progress == 100 or status == '완료' else status),
             '우선순위':priority,'진행률':str(100 if status == '완료' else progress),'메모':memo,'첨부파일URL':link,
             '작성일':safe(old.get('작성일')) or now,'수정일':now})
            try:
                save_record(svc,rec,safe(old.get('통합ID')) or None)
                if key.startswith('calendar_'):
                    view_month=calendar_view_month(st.query_params,st.session_state.get('month'))
                    st.session_state.month=view_month
                    st.query_params['calendar_month']=view_month.isoformat()
                    st.query_params.pop('calendar_task',None)
                    st.query_params.pop('calendar_date',None)
                    st.session_state.pop('calendar_new_open',None)
                    st.session_state['calendar_saved_notice']='일정이 수정되었습니다.' if safe(old.get('통합ID')) else '일정이 등록되었습니다.'
                if key.startswith('calendar_date_'):
                    st.query_params.pop('calendar_date',None)
                    st.session_state['calendar_created_notice'] = True
                # 신규 업무 등록 후 입력 폼의 위젯 키를 갱신해 모든 입력값을 초기화합니다.
                # 수정 폼은 기존 동작을 그대로 유지합니다.
                if compact and not safe(old.get('통합ID')):
                    st.session_state['task_new_form_version'] = st.session_state.get('task_new_form_version', 0) + 1
                    st.session_state['task_created_notice'] = True
                    st.session_state['task_new_panel_closed'] = True
                st.rerun()
            except Exception as exc:st.error(f'저장 실패: {exc}')

def display_table(data):
    cols=['업무명','담당자','업무구분','시작일','마감일','진행상태','진행률','거래처']
    if data.empty:st.info('표시할 업무가 없습니다.')
    else:
        view=data[[x for x in cols if x in data.columns]].copy()
        if '담당자' in view:view['담당자']=view['담당자'].map(person_label)
        st.dataframe(view,hide_index=True,use_container_width=True)


MEETING_TAB='회의록DB'
MEETING_FIELDS=['ID','제목','구분','부서','날짜','시작','종료','장소','참석자','작성자','회의내용','결정사항','후속조치','작성일']
def meeting_data():
    if MEETING_TAB not in tab_names(svc):
        svc.spreadsheets().batchUpdate(spreadsheetId=SID,body={'requests':[{'addSheet':{'properties':{'title':MEETING_TAB}}}]}).execute()
    vals=svc.spreadsheets().values().get(spreadsheetId=SID,range="'회의록DB'!A:N").execute().get('values',[])
    if not vals:
        svc.spreadsheets().values().update(spreadsheetId=SID,range="'회의록DB'!A1:N1",valueInputOption='RAW',body={'values':[MEETING_FIELDS]}).execute()
        return []
    if vals[0]!=MEETING_FIELDS:raise ValueError('회의록DB 열 구성이 다릅니다. 기존 데이터를 보호하기 위해 중단합니다.')
    return [dict(zip(MEETING_FIELDS,row+['']*(len(MEETING_FIELDS)-len(row)))) for row in vals[1:] if row and row[0]]
def meeting_save(r):
    data=meeting_data()
    ids=[x['ID'] for x in data]
    values=[str(r.get(k,'')) for k in MEETING_FIELDS]
    if r['ID'] in ids:
        n=ids.index(r['ID'])+2
        svc.spreadsheets().values().update(spreadsheetId=SID,range=f"'회의록DB'!A{n}:N{n}",valueInputOption='RAW',body={'values':[values]}).execute()
    else:
        svc.spreadsheets().values().append(spreadsheetId=SID,range="'회의록DB'!A:N",valueInputOption='RAW',insertDataOption='INSERT_ROWS',body={'values':[values]}).execute()
def meeting_form(r=None):
    r=r or {}
    with st.form('meeting_form_'+r.get('ID','new')):
        title=st.text_input('회의 제목 *',r.get('제목',''),placeholder='예: 영업부 주간 회의')
        a,b=st.columns(2)
        kind=a.selectbox('회의구분',['정기회의','업무회의','거래처 미팅','기타'],index=['정기회의','업무회의','거래처 미팅','기타'].index(r.get('구분','정기회의')) if r.get('구분','정기회의') in ['정기회의','업무회의','거래처 미팅','기타'] else 0)
        dept=b.text_input('부서',r.get('부서','영업부'))
        a,b,c=st.columns(3)
        day=a.date_input('회의일',date.fromisoformat(r['날짜']) if r.get('날짜') and len(r['날짜'])==10 else date.today())
        start=b.text_input('시작시간',r.get('시작','10:00'))
        end=c.text_input('종료시간',r.get('종료','11:00'))
        place=st.text_input('장소',r.get('장소',''))
        attendees=st.text_input('참석자 (쉼표 구분)',r.get('참석자',''))
        author=st.text_input('작성자',r.get('작성자',''))
        content=st.text_area('회의 내용',r.get('회의내용',''),height=160)
        decisions=st.text_area('주요 결정사항',r.get('결정사항',''),height=100)
        actions=st.text_area('후속조치 / To-Do',r.get('후속조치',''),height=100,placeholder='담당자 | 할 일 | 기한 | 진행상태')
        if st.form_submit_button('💾 회의록 저장',type='primary',use_container_width=True):
            if not title.strip():st.error('회의 제목을 입력하세요.')
            else:
                record=dict(zip(MEETING_FIELDS,[r.get('ID') or str(uuid.uuid4()),title,kind,dept,day.isoformat(),start,end,place,attendees,author,content,decisions,actions,r.get('작성일') or datetime.now().isoformat(timespec='minutes')]))
                try:
                    meeting_save(record)
                    st.session_state.pop('meeting_view_id',None)
                    st.session_state['meeting_saved_notice']=True
                    st.rerun()
                except Exception as e:st.error(f'저장 실패: {e}')

# 개인 메모장: 기존 시트는 변경하지 않고 별도 시트에 저장합니다.
MEMO_TAB = '개인메모DB'
MEMO_FIELDS = ['ID', '작성자', '날짜', '제목', '내용', '수정일']

def memo_records():
    if MEMO_TAB not in tab_names(svc):
        svc.spreadsheets().batchUpdate(spreadsheetId=SID, body={'requests':[{'addSheet':{'properties':{'title':MEMO_TAB}}}]}).execute()
    values = svc.spreadsheets().values().get(spreadsheetId=SID, range="'개인메모DB'!A:F").execute().get('values', [])
    if not values:
        svc.spreadsheets().values().update(spreadsheetId=SID, range="'개인메모DB'!A1:F1", valueInputOption='RAW', body={'values':[MEMO_FIELDS]}).execute()
        return []
    if values[0] != MEMO_FIELDS:
        raise ValueError('개인메모DB의 열 구성이 다릅니다. 기존 데이터 보호를 위해 저장을 중단했습니다.')
    return [dict(zip(MEMO_FIELDS, row+['']*(len(MEMO_FIELDS)-len(row)))) for row in values[1:] if row and row[0]]

def memo_save(record):
    records = memo_records()
    values = [str(record.get(k,'')) for k in MEMO_FIELDS]
    ids = [r['ID'] for r in records]
    if record['ID'] in ids:
        row = ids.index(record['ID']) + 2
        svc.spreadsheets().values().update(spreadsheetId=SID, range=f"'개인메모DB'!A{row}:F{row}", valueInputOption='RAW', body={'values':[values]}).execute()
    else:
        svc.spreadsheets().values().append(spreadsheetId=SID, range="'개인메모DB'!A:F", valueInputOption='RAW', insertDataOption='INSERT_ROWS', body={'values':[values]}).execute()

def memo_delete(record_id):
    records = memo_records()
    ids = [r['ID'] for r in records]
    if record_id not in ids:
        raise ValueError('삭제할 메모를 찾지 못했습니다.')
    meta = svc.spreadsheets().get(spreadsheetId=SID, fields='sheets(properties(sheetId,title))').execute()
    sheet_id = next(x['properties']['sheetId'] for x in meta['sheets'] if x['properties']['title']==MEMO_TAB)
    index = ids.index(record_id) + 1  # zero-based row index; header is index 0
    svc.spreadsheets().batchUpdate(spreadsheetId=SID,body={'requests':[{'deleteDimension':{'range':{'sheetId':sheet_id,'dimension':'ROWS','startIndex':index,'endIndex':index+1}}}]}).execute()

st.sidebar.markdown('### 영업팀 대시보드')
page=st.sidebar.radio('메뉴',['🗓️ 달력','📋 업무현황','📝 회의록','🗒️ 개인 메모장','📁 공유파일','🏢 거래처 특이사항','⚙️ 데이터 통합/설정'],format_func=lambda value: {'🗓️ 달력':'달력','📋 업무현황':'업무 현황','📝 회의록':'회의록','🗒️ 개인 메모장':'개인 메모장','📁 공유파일':'공유파일','🏢 거래처 특이사항':'거래처 관리','⚙️ 데이터 통합/설정':'데이터 설정'}[value],label_visibility='collapsed')
sidebar_filter=st.sidebar.container()
st.sidebar.divider()
if st.sidebar.button('↻ 새로고침',use_container_width=True):st.rerun()
if page=='📁 공유파일':
    from shared_files import render_shared_files
    render_shared_files(secrets_credential())
    st.stop()
try:svc=api();tabs=tab_names(svc)
except Exception as exc:st.error(f'Google Sheets 연결 실패: {exc}');st.stop()
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

PERSON_LABELS={}
try:
    team=read_tab(svc,'팀원정보','A:Z')
    PERSON_LABELS=build_person_labels(team)
    people=[safe(x) for x in team.get('이름',pd.Series(dtype=str)).tolist() if safe(x)]
except Exception:people=[]
people=list(dict.fromkeys(people+[safe(x) for x in df.get('담당자',pd.Series(dtype=str)).tolist() if safe(x)]))
people=[p for p in people if p not in ('전체','미지정')]

if page=='⚙️ 데이터 통합/설정':
    st.title('데이터 통합 및 설정')
    st.caption('공유 편집 방식으로 운영됩니다. 사용자별 열람·수정 권한은 적용되지 않습니다.')
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
    person=sidebar_filter.selectbox('담당자',choices,key='person_filter',format_func=person_label)
    shown=df if person=='전체' else df[df['담당자'].isin([person,'전체'])]
    if page=='🗓️ 달력':
        st.session_state.month=calendar_view_month(st.query_params,st.session_state.get('month'))
        m=st.session_state.month
        month_tasks=shown[shown['마감일'].astype(str).str.startswith(m.strftime('%Y-%m'))]
        month_done=int(month_tasks['진행상태'].eq('완료').sum())
        st.markdown(f'<div class="cal-page-header"><div><h1>캘린더</h1><p>팀 일정과 업무 진행 현황을 한눈에 확인하세요.</p></div><div class="cal-overview"><div><span>이달의 업무</span><b>{len(month_tasks)}</b></div><div><span>미완료</span><b>{len(month_tasks)-month_done}</b></div><div class="complete"><span>완료</span><b>{month_done}</b></div></div></div>',unsafe_allow_html=True)
        left,title,right,todaycol,spacer,add=st.columns([.65,2.2,.65,.85,3.2,1.4],vertical_alignment='center')
        if left.button('❮',key='month_prev',use_container_width=True):
            st.session_state.month=(pd.Timestamp(m)-pd.DateOffset(months=1)).date()
            st.query_params['calendar_month']=st.session_state.month.isoformat();st.rerun()
        title.markdown(f'<div class="cal-month-title">{m.year}년 {m.month}월</div>',unsafe_allow_html=True)
        if right.button('❯',key='month_next',use_container_width=True):
            st.session_state.month=(pd.Timestamp(m)+pd.DateOffset(months=1)).date()
            st.query_params['calendar_month']=st.session_state.month.isoformat();st.rerun()
        if todaycol.button('오늘',key='calendar_today',use_container_width=True):
            st.session_state.month=date.today().replace(day=1)
            st.query_params['calendar_month']=st.session_state.month.isoformat();st.rerun()
        if add.button('＋ 일정 추가',key='calendar_add_button',type='primary',use_container_width=True):
            st.session_state['calendar_new_open']=True
            st.query_params.pop('calendar_task',None)
            st.query_params.pop('calendar_date',None)
        def close_calendar_new():
            st.session_state.pop('calendar_new_open',None)
        @st.dialog('일정 추가',width='large',on_dismiss=close_calendar_new)
        def calendar_new_add():
            form(svc,people,key='calendar_new')
        if st.session_state.get('calendar_new_open'):
            calendar_new_add()
        if st.session_state.get('calendar_saved_notice'):
            st.success(st.session_state.pop('calendar_saved_notice'))
            st.session_state.pop('calendar_created_notice',None)
        if st.session_state.pop('calendar_created_notice',False):
            st.success('일정이 등록되었습니다.')
        def close_calendar_date_add():
            st.query_params.pop('calendar_date',None)
        @st.dialog('📅 선택한 날짜에 일정 추가', width='large', on_dismiss=close_calendar_date_add)
        def calendar_date_add(selected_day):
            st.caption(f'{selected_day:%Y년 %m월 %d일} · 시작일과 마감일을 변경할 수 있습니다.')
            form(svc,people,existing={'시작일':selected_day.isoformat(),'마감일':selected_day.isoformat()},key='calendar_date_'+selected_day.isoformat())
        selected_date=st.query_params.get('calendar_date')
        if selected_date and not st.query_params.get('calendar_task'):
            try:
                selected_day=date.fromisoformat(selected_date)
            except (ValueError,TypeError):
                st.query_params.pop('calendar_date',None)
                st.warning('올바르지 않은 날짜입니다. 달력에서 날짜를 다시 선택하세요.')
            else:
                calendar_date_add(selected_day)
        st.markdown('<style>.cal-event:is(a){display:block;text-decoration:none!important;cursor:pointer}.cal-event:is(a):hover{text-decoration:none!important;filter:brightness(.98)}</style>',unsafe_allow_html=True)
        # 기존 달력 HTML/CSS를 유지하면서 업무 카드만 클릭 가능한 링크로 연결합니다.
        @st.dialog('📋 업무 상세정보 · 수정', width='large')
        def calendar_task_detail(task_row):
            st.markdown('<div class="cal-detail-marker"></div>',unsafe_allow_html=True)
            task_title=escape(safe(task_row.get('업무명')) or '업무 상세정보')
            owner=escape(person_label(task_row.get('담당자')) or '미지정')
            status=escape(safe(task_row.get('진행상태')) or '미진행')
            category=escape(safe(task_row.get('업무구분')) or '미지정')
            start_day=escape(safe(task_row.get('시작일')) or '미지정')
            due_day=escape(safe(task_row.get('마감일')) or '미지정')
            try:progress=max(0,min(100,int(float(task_row.get('진행률') or 0))))
            except (ValueError,TypeError):progress=0
            detail=escape(safe(task_row.get('상세내용')) or '등록된 상세내용이 없습니다.').replace('\n','<br>')
            st.markdown(f'''<div class="cal-detail-hero"><div class="cal-detail-kicker">📌 선택한 업무</div>
                <div class="cal-detail-title">{task_title}</div>
                <div class="cal-detail-pills"><span>👤 {owner}</span><span>● {status}</span><span>📁 {category}</span></div>
                <div class="cal-detail-dates">📅 {start_day} ~ {due_day}</div>
                <div class="cal-detail-progress-label"><b>업무 진행률</b><strong>{progress}%</strong></div>
                <div class="cal-detail-track"><div style="width:{progress}%"></div></div></div>
                <div class="cal-detail-content"><b>📋 상세 업무 내용</b><div>{detail}</div></div>''',unsafe_allow_html=True)
            with st.expander('✏️ 업무 정보 수정 · 클릭하여 펼치기', expanded=False):
                st.caption('수정할 내용을 입력한 뒤 하단의 파란 저장 버튼을 누르세요.')
                form(svc,people,existing=task_row,key='calendar_detail_'+safe(task_row.get('통합ID')))
            if st.button('닫기',key='calendar_detail_close'):
                st.query_params.pop('calendar_task',None)
                st.rerun()
        selected_calendar_task=st.query_params.get('calendar_task','')
        if selected_calendar_task:
            matches=df[df['통합ID'].astype(str)==str(selected_calendar_task)]
            if len(matches)==1:
                calendar_task_detail(matches.iloc[0].to_dict())
            else:
                st.query_params.pop('calendar_task',None)
        def owner_color(owner):
            return _task_badge_colors(owner,'owner')[2]
        def pct(row):
            try:return max(0,min(100,int(float(row.get('진행률') or 0))))
            except (ValueError,TypeError):return 0
        def cal_entries(day):
            daystr=day.isoformat()
            d=shown[shown['마감일']==daystr]  # 달력에는 시작일과 관계없이 마감일 당일에만 표시
            return d.sort_values(['시작시간','업무명'],kind='stable')
        st.markdown(f'<div class="cal-context"><strong>{escape(person_label(person))} · 마감일 기준</strong><span>날짜 클릭으로 등록 · 일정 클릭으로 상세보기</span></div>',unsafe_allow_html=True)
        html=['<div class="cal-shell"><div class="cal-weekdays">']
        html += [f'<div>{d}</div>' for d in ['일요일','월요일','화요일','수요일','목요일','금요일','토요일']]
        html.append('</div><div class="cal-grid">')
        weeks=calendar.Calendar(firstweekday=6).monthdatescalendar(m.year,m.month)
        for week in weeks:
            for day in week:
                outside=' outside' if day.month!=m.month else ''
                todaycls=' today' if day==date.today() else ''
                daily=cal_entries(day)
                dayclass=' is-today' if day==date.today() else ''
                daycount=f'<span class="cal-day-count">{len(daily)}건</span>' if len(daily) else ''
                html.append(f'<div class="cal-day{outside}{dayclass}"><div class="cal-date-row"><a class="day-num{todaycls}" href="?calendar_date={day.isoformat()}&amp;calendar_month={m.isoformat()}" target="_self" aria-label="{day.isoformat()} 일정 추가" title="{day.isoformat()} 일정 추가">{day.day}</a>{daycount}</div>')
                for _,r in daily.head(3).iterrows():
                    owner=safe(r.get('담당자')) or '미지정'
                    bg,fg,color=_task_badge_colors(owner,'owner')
                    progress=pct(r)
                    # 담당자별 색상을 상태와 무관하게 유지합니다.
                    status=safe(r.get('진행상태'))
                    task=escape(safe(r.get('업무명')));owner_html=escape(person_label(owner))
                    tm=escape(safe(r.get('시작시간')))
                    html.append(f'<a class="cal-event" href="?calendar_task={quote(safe(r.get("통합ID")),safe="")}&amp;calendar_month={m.isoformat()}" target="_self" title="{task} · {owner_html} · {escape(status)} · {progress}%" style="background:{bg};color:{fg};border-left:3px solid {color}"><div class="event-title">{"✓ " if status=="완료" else ""}{tm+" " if tm else ""}{task}</div><div class="event-sub"><span class="event-owner">{owner_html}</span><div class="track"><div class="fill" style="width:{progress}%;background:{color}"></div></div><b>{progress}%</b></div></a>')
                if len(daily)>3:html.append(f'<div class="cal-more">+ {len(daily)-3}건 더보기</div>')
                html.append('</div>')
        html.append('</div></div>')
        st.markdown(''.join(html),unsafe_allow_html=True)
        st.markdown('<div class="cal-scroll-hint">↔ 달력을 좌우로 밀어 나머지 날짜를 확인하세요.</div>',unsafe_allow_html=True)
        if people:
            legend=''.join(f'<span><i style="background:{owner_color(p)}"></i>{escape(person_label(p))}</span>' for p in people)
            st.markdown(f'<div class="cal-legend">{legend}</div>',unsafe_allow_html=True)
    elif page=='📋 업무현황':
        today=date.today().isoformat()
        done=shown['진행상태'].eq('완료')
        late=(shown['마감일']<today)&(~done)&shown['마감일'].ne('')
        ongoing=shown['진행상태'].isin(['진행중','거의완료'])&(~late)
        # 회의록과 동일한 상단 제목 + 우측 소형 통계 카드 디자인
        stats=[('📄 전체 업무',len(shown)),('🔵 진행 중',int(ongoing.sum())),
               ('🟢 완료',int(done.sum())),('🔴 지연',int(late.sum()))]
        stats_html=''.join(
            f'<div class="meeting-mini-stat"><span>{label}</span><b>{value}건</b></div>'
            for label,value in stats)
        st.markdown(
            '<div class="meeting-topbar"><div class="meeting-top-title">📋 업무 현황'
            '<small>개인의 업무를 등록하고 마감일까지 관리할 수 있습니다.</small></div>'
            '<div class="meeting-mini-stats">'+stats_html+'</div></div>',
            unsafe_allow_html=True)
        left,right=st.columns([3.1,1.45],gap='medium')
        with left:
            st.markdown('<div class="task-list-head"><strong>📌 업무 목록 · 한눈에 확인</strong><small>업무별 상태와 마감일을 확인하고 아래 파란 수정란을 눌러 바로 변경하세요.</small></div>',unsafe_allow_html=True)
            st.caption('업무 카드를 선택하면 진행상태, 우선순위, 담당자 등을 바로 변경할 수 있습니다.')
            view=st.radio('상태별 조회',['전체','진행 중','완료','지연'],horizontal=True,label_visibility='collapsed')
            q=st.text_input('🔎 업무명, 거래처, 담당자 검색',key='task_search')
            f1,f2,f3=st.columns(3)
            owner_filter=f1.selectbox('담당자',['전체']+people,key='task_owner',format_func=person_label)
            cat_filter=f2.selectbox('업무구분',['전체']+sorted(set(shown['업무구분'].dropna())-{''}),key='task_category')
            priority_filter=f3.selectbox('우선순위',['전체','긴급','높음','보통','낮음'],key='task_priority')
            filtered=shown.copy()
            if view=='진행 중':filtered=filtered[ongoing]
            elif view=='완료':filtered=filtered[done]
            elif view=='지연':filtered=filtered[late]
            if q:
                searchable=filtered[['업무명','거래처','담당자','상세내용']].fillna('').astype(str).copy()
                searchable['담당자']=searchable['담당자'].map(person_label)
                mask=searchable.apply(lambda col:col.str.contains(q,case=False,regex=False)).any(axis=1)
                filtered=filtered[mask]
            if owner_filter!='전체':filtered=filtered[filtered['담당자'].isin([owner_filter,'전체'])]
            if cat_filter!='전체':filtered=filtered[filtered['업무구분']==cat_filter]
            if priority_filter!='전체':filtered=filtered[filtered['우선순위']==priority_filter]
            st.caption(f'🔵 현재 {len(filtered)}건 표시 중  ·  카드의 수정 메뉴에서 상태·우선순위·진행률 변경 가능')
            if st.session_state.pop('task_deleted_notice', False):
                st.success('완료된 업무를 삭제했습니다. Google Sheets에도 반영되었습니다.')
            if filtered.empty:
                st.info('조건에 맞는 업무가 없습니다.')
            else:
                status_colors={'완료':('#e4f8ec','#12844a'),'진행중':('#e6f0ff','#1768df'),
                               '거의완료':('#e8f0ff','#3554bd'),'미진행':('#f0f3f8','#66758b'),
                               '보류':('#fff3db','#a46b05')}
                priority_colors={'긴급':('#ffe5e5','#c52d35'),'높음':('#ffeded','#d4484b'),
                                 '보통':('#fff2dc','#b77712'),'낮음':('#edf2f7','#65758b')}
                for _, task in filtered.iterrows():
                    task_id=safe(task['통합ID'])
                    title=safe(task['업무명'])
                    status=safe(task['진행상태']) or '미진행'
                    priority=safe(task['우선순위']) or '보통'
                    try: percent=max(0,min(100,int(float(task.get('진행률') or 0))))
                    except (ValueError,TypeError):percent=0
                    sbg,sfg=status_colors.get(status,('#f0f3f8','#66758b'))
                    pbg,pfg=priority_colors.get(priority,('#f0f3f8','#66758b'))
                    due_text=safe(task.get('마감일')) or '미지정'
                    owner_text=safe(task.get('담당자')) or '담당자 미지정'
                    category_text=safe(task.get('업무구분')) or '기타'
                    owner_badge_style = _task_badge_style(owner_text, 'owner')
                    category_badge_style = _task_badge_style(category_text, 'category')
                    company_text=safe(task.get('거래처'))
                    is_completed = status == '완료'
                    due_date = dt(task.get('마감일'))
                    days_left = (due_date - date.today()).days if due_date else None
                    if days_left is None:
                        dday_label, dday_class = '마감일 미지정', 'none'
                    elif days_left > 0:
                        dday_label, dday_class = f'D-{days_left}', 'tomorrow' if days_left == 1 and not is_completed else 'normal'
                    elif days_left == 0:
                        dday_label, dday_class = 'D-0 · 오늘 마감', 'today' if not is_completed else 'completed'
                    else:
                        dday_label, dday_class = f'D+{-days_left} · 마감 경과', 'overdue' if not is_completed else 'completed'
                    if is_completed:
                        dday_class = 'completed'
                    dday_tag = f'<span class="task-dday-tag task-dday-{dday_class}">{escape(dday_label)}</span>'
                    with st.container(border=True):
                        if not is_completed and days_left is not None and days_left < 0:
                            st.markdown(
                                f'<div class="task-deadline-banner task-deadline-overdue">'
                                f'<span>🚨</span><span><strong>마감일 경과 · {escape(dday_label)}</strong>'
                                '<small>마감일이 지났지만 완료되지 않은 업무입니다.</small></span></div>',
                                unsafe_allow_html=True)
                        elif not is_completed and days_left == 1:
                            st.markdown(
                                '<div class="task-deadline-banner task-deadline-tomorrow">'
                                '<span>⏰</span><span><strong>마감 하루 전 · D-1</strong>'
                                '<small>내일이 마감일입니다. 진행 상태를 확인하세요.</small></span></div>',
                                unsafe_allow_html=True)
                        elif not is_completed and days_left == 0:
                            st.markdown(
                                '<div class="task-deadline-banner task-deadline-today">'
                                '<span>📅</span><span><strong>오늘 마감 · D-0</strong>'
                                '<small>오늘까지 완료해야 하는 업무입니다.</small></span></div>',
                                unsafe_allow_html=True)
                        if is_completed:
                            # 완료 배너 오른쪽에 실제 Streamlit 삭제 버튼을 배치합니다.
                            # 삭제는 확인 대화상자에서 '예'를 누른 경우에만 실행됩니다.
                            with st.container(key='completed_row_'+task_id):
                                st.markdown(
                                    '<div class="task-completed-banner">'
                                    '<span class="task-completed-icon">✓</span>'
                                    '<span><strong>완료된 업무</strong><small>이 업무는 완료 처리되었습니다.</small></span>'
                                    '</div>', unsafe_allow_html=True)
                                if st.button('삭제',icon=':material/delete_outline:', key='open_delete_' + task_id,
                                             type='secondary'):
                                    confirm_completed_task_delete(svc, task_id)
                        st.markdown(
                            f'<div class="task-card-top"><div class="task-card-title">{escape(title)}'
                            + (' <span class="task-completed-title-tag">✓ 완료</span>' if is_completed else '')
                            + '</div>'
                            f'<div class="task-tags"><span style="background:{sbg};color:{sfg}">{escape(status)}</span>'
                            f'<span style="background:{pbg};color:{pfg}">{escape(priority)}</span></div></div>'
                            f'<div class="task-card-meta">'
                            f'<span class="meta-owner" style="{owner_badge_style}"><b>담당자</b>{escape(person_label(owner_text))}</span>'
                            f'<span class="meta-category" style="{category_badge_style}"><b>업무구분</b>{escape(category_text)}</span>'
                            f'<span><b>마감일</b>{escape(due_text)}</span>'
                            + dday_tag
                            + (f'<span><b>거래처</b>{escape(company_text)}</span>' if company_text else '')
                            + '</div>',unsafe_allow_html=True)
                        st.progress(percent/100,text=f'📊 업무 진행률  {percent}%')
                        if st.button('업무 수정하기',icon=':material/edit:',key='open_task_edit_'+task_id):
                            st.session_state['task_edit_open']=task_id
                        if st.session_state.get('task_edit_open')==task_id:
                            st.markdown("<div class='edit-intro'><strong>✏️ 업무 정보 수정</strong><span>변경 후 아래 저장 버튼을 누르세요.</span></div>",unsafe_allow_html=True)
                            with st.form('quick_edit_'+task_id):
                                st.markdown("<div class='edit-section'>01 · 진행 현황 <small>상태 / 우선순위 / 진행률</small></div>",unsafe_allow_html=True)
                                a,b,c=st.columns([1.1,1,1.3])
                                states=list(dict.fromkeys(STATES+[status]))
                                new_status=a.selectbox('진행상태',states,index=states.index(status),key='qs_'+task_id)
                                priorities=list(dict.fromkeys(['낮음','보통','높음','긴급']+[priority]))
                                new_priority=b.selectbox('우선순위',priorities,index=priorities.index(priority),key='qp_'+task_id)
                                new_progress=c.slider('진행률 (%)',0,100,percent,key='qg_'+task_id)
                                a,b=st.columns(2)
                                st.markdown("<div class='edit-section'>02 · 기본 정보 <small>업무명 / 담당자 / 마감일</small></div>",unsafe_allow_html=True)
                                new_title=a.text_input('업무명',value=title,key='qt_'+task_id)
                                new_owner=b.selectbox('담당자',list(dict.fromkeys(
                                    ['미지정']+people+([owner_text] if owner_text!='담당자 미지정' else []))),
                                    index=(list(dict.fromkeys(['미지정']+people+([owner_text] if owner_text!='담당자 미지정' else []))).index(owner_text)
                                           if owner_text!='담당자 미지정' else 0),key='qo_'+task_id,format_func=person_label)
                                a,b=st.columns(2)
                                new_due=a.date_input('마감일',value=dt(task.get('마감일')) or date.today(),key='qd_'+task_id)
                                new_cat=b.selectbox('업무구분',list(dict.fromkeys(CATS+[category_text])),
                                    index=list(dict.fromkeys(CATS+[category_text])).index(category_text),key='qc_'+task_id)
                                st.markdown("<div class='edit-section'>03 · 업무 내용 <small>상세내용 / 거래처</small></div>",unsafe_allow_html=True)
                                new_detail=st.text_area('상세내용' ,value=safe(task.get('상세내용')),key='qdetail_'+task_id)
                                new_company=st.text_input('거래처',value=company_text,key='qcompany_'+task_id)
                                st.markdown("<div class='edit-save-hint'>✓ 변경 내용을 확인하고 저장하세요. Google Sheets에 반영됩니다.</div>",unsafe_allow_html=True)
                                if st.form_submit_button('✓ 변경사항 저장하기',type='primary',use_container_width=True):
                                    if not new_title.strip():
                                        st.error('업무명을 입력하세요.')
                                    elif dt(task.get('시작일')) and new_due<dt(task.get('시작일')):
                                        st.error('마감일은 시작일 이후여야 합니다.')
                                    else:
                                        record={k:safe(task.get(k)) for k in HEAD}
                                        record.update({'업무명':new_title.strip(),'담당자':'' if new_owner=='미지정' else new_owner,
                                            '업무구분':new_cat,'진행상태':('완료' if new_progress == 100 or new_status == '완료' else new_status),'우선순위':new_priority,
                                            '진행률':str(100 if new_status == '완료' else new_progress),'마감일':new_due.isoformat(),
                                            '상세내용':new_detail,'거래처':new_company,
                                            '수정일':datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
                                        try:
                                            save_record(svc,record,task_id)
                                            st.session_state.pop('task_edit_open',None)
                                            st.session_state['task_updated_notice']=True
                                            st.rerun()
                                        except Exception as exc:
                                            st.error(f'저장 실패: {exc}')
        with right:
            st.markdown('''<div class="new-task-banner"><div class="new-task-kicker">✦ NEW TASK</div><div class="new-task-title">＋ 새 업무 등록</div><div class="new-task-desc">새로운 업무를 작성하고 팀원과 공유하세요.</div></div>''',unsafe_allow_html=True)
            if st.session_state.pop('task_updated_notice',False):
                st.success('업무가 수정되었습니다.')
            if st.session_state.pop('task_created_notice', False):
                st.success('새 업무가 등록되었습니다.')
            if st.session_state.get('task_new_panel_closed'):
                if st.button('＋ 새 업무 작성',use_container_width=True):
                    st.session_state.pop('task_new_panel_closed',None)
                    st.rerun()
            else:
                with st.container(border=True):
                    form(svc,people,key=f"task_new_panel_{st.session_state.get('task_new_form_version', 0)}",compact=True)

    elif page=='🗒️ 개인 메모장':
        try:
            memos=memo_records()
        except Exception as exc:
            st.error(f'메모장 연결 오류: {exc}');st.stop()
        from memo_ui import render_memos
        render_memos(memos,people,person_label,memo_save,memo_delete)

    elif page=='📝 회의록':
        try:meetings=meeting_data()
        except Exception as e:st.error(f'회의록 연결 오류: {e}');st.stop()
        todos=[line for r in meetings for line in r['후속조치'].splitlines() if line.strip()]
        completed=sum('완료' in x for x in todos)
        delayed=sum('지연' in x for x in todos)
        monthly=sum(x['날짜'].startswith(date.today().strftime('%Y-%m')) for x in meetings)
        st.markdown(
            '<div class="meeting-topbar"><div class="meeting-top-title">👥 회의록'
            '<small>영업팀 회의 내용을 기록하고 공유하는 공간입니다.</small></div>'
            '<div class="meeting-mini-stats">'
            + ''.join(f'<div class="meeting-mini-stat"><span>{label}</span><b>{num}건</b></div>'
              for label,num in [('📅 이번 달 회의',monthly),('🟢 완료',completed),
                                ('🟠 진행 중',max(0,len(todos)-completed-delayed)),('🔴 지연',delayed)])
            + '</div></div>',unsafe_allow_html=True)
        st.markdown('<div class="meeting-filter-title">🔎 회의록 검색 및 필터 <small>원하는 회의 내용을 빠르게 찾아보세요.</small></div>',unsafe_allow_html=True)
        with st.container(border=True):
            q=st.text_input('회의록 통합 검색',placeholder='회의 제목, 내용, 참석자, 작성자 검색',key='meeting_search')
            f1,f2,f3=st.columns(3)
            kind=f1.selectbox('회의구분',['전체']+sorted(set(x['구분'] for x in meetings)))
            attendee=f2.selectbox('참석자',['전체']+sorted(set(p.strip() for x in meetings for p in x['참석자'].split(',') if p.strip())))
            author=f3.selectbox('작성자',['전체']+sorted(set(x['작성자'] for x in meetings if x['작성자'])))
        filtered=[r for r in meetings if (kind=='전체' or r['구분']==kind) and (attendee=='전체' or attendee in r['참석자']) and (author=='전체' or r['작성자']==author) and (not q or q.lower() in ' '.join(r.values()).lower())]
        filtered.sort(key=lambda r:r['날짜']+' '+r['시작'],reverse=True)
        left,right=st.columns([3.1,1.45],gap='medium')
        with left:
            st.markdown('<div class="meeting-hero"><strong>📌 회의록 목록 · 한눈에 확인</strong><span>자세히 보기를 누르면 회의 내용과 결정사항이 상세 창에 표시됩니다.</span></div>',unsafe_allow_html=True)
            st.markdown(f'#### 등록된 회의 ({len(filtered)}건)')
            for r in filtered:
                with st.container(border=True):
                    a,b=st.columns([1,5],gap='medium')
                    date_text=escape(r['날짜'][5:] or '미정')
                    a.markdown(f'<div class="meeting-date-box">📅<div><strong>{date_text}</strong></div></div>',unsafe_allow_html=True)
                    title=escape(r['제목'] or '제목 없음')
                    summary=escape((r['회의내용'] or '회의 내용이 아직 작성되지 않았습니다.')[:150])
                    pills=[('회의구분',r['구분']),('부서',r['부서']),('시간',r['시작']+' ~ '+r['종료']),
                           ('참석',str(len([x for x in r['참석자'].split(',') if x.strip()]))+'명')]
                    tags=''.join('<span>'+escape(k)+' · '+escape(v)+'</span>' for k,v in pills if v)
                    b.markdown('<div class="meeting-list-card"><div class="meeting-list-title">'+title+
                               '</div><div class="meeting-pills">'+tags+
                               '</div><div class="meeting-excerpt">'+summary+'</div></div>',unsafe_allow_html=True)
                    if b.button('📖 회의 내용 자세히 보기 →',key='meeting_'+r['ID'],use_container_width=True):
                        st.session_state['meeting_view_id']=r['ID'];st.rerun()
            if not filtered:st.info('조건에 맞는 회의록이 없습니다.')
        with right:
            st.markdown('<div class="meeting-hero"><strong>✍️ 새 회의록 작성</strong><span>회의 정보, 안건, 결정사항과 후속조치를 작성해 저장하세요.</span></div>',unsafe_allow_html=True)
            with st.container(border=True):meeting_form()
        if st.session_state.pop('meeting_saved_notice',False):
            st.success('회의록을 저장했습니다.')
        def close_meeting_detail():
            st.session_state.pop('meeting_view_id',None)
        @st.dialog('회의록 상세',width='large',on_dismiss=close_meeting_detail)
        def meeting_detail_dialog(record):
            title=escape(record['제목'] or '제목 없음')
            subtitle=escape(record['날짜']+' · '+record['시작']+'~'+record['종료']+' · '+record['장소'])
            st.markdown('<div class="meeting-detail-header"><strong>'+title+'</strong><small>'+subtitle+'</small></div>',unsafe_allow_html=True)
            st.markdown('<div class="meeting-pills"><span>'+escape(record['구분'])+'</span><span>'+escape(record['부서'])+'</span><span>작성자 · '+escape(person_label(record['작성자']) or '미입력')+'</span></div>',unsafe_allow_html=True)
            for label,field in [('참석자','참석자'),('회의 내용','회의내용'),('주요 결정사항','결정사항'),('후속조치 / To-Do','후속조치')]:
                st.markdown('<div class="meeting-section">'+label+'</div><div class="meeting-body">'+escape(record[field] or '아직 입력된 내용이 없습니다.')+'</div>',unsafe_allow_html=True)
            with st.expander('이 회의록 수정하기'):
                meeting_form(record)
            if st.button('닫기',key='meeting_detail_close',use_container_width=True):
                close_meeting_detail()
                st.rerun()
        selected=st.session_state.get('meeting_view_id')
        if selected is not None:
            record=next((x for x in meetings if x['ID']==selected),None)
            if record is not None:
                meeting_detail_dialog(record)
            else:
                close_meeting_detail()
                st.warning('선택한 회의록을 찾을 수 없습니다. 목록을 새로고침해 주세요.')
    else:
        import importlib
        import customer_data
        # Streamlit can retain imported modules when app.py is redeployed.
        customer_version='20261029-customer-3'
        if getattr(customer_data,'SCHEMA_VERSION',None)!=customer_version:
            importlib.reload(customer_data)
        import customer_workspace
        if getattr(customer_workspace,'UI_VERSION',None)!=customer_version:
            importlib.reload(customer_workspace)
        CustomerStore=customer_data.CustomerStore
        render_customers=customer_workspace.render_customers
        st.session_state['customer_linked_tasks']=df.to_dict('records')
        render_customers(CustomerStore(svc,SID),people,person_label)
