"""Memo browsing and editing UI; storage callbacks remain in app.py."""
import uuid
from datetime import date, datetime
from html import escape

import streamlit as st
from memo_attachments import split_content, join_content, clipboard, save_images, show_images

UI_VERSION="20261030-memo-all-dates-1"

MEMO_CSS = '''<style>
.memo-heading{display:flex;align-items:center;justify-content:space-between;margin:0 0 22px}
.memo-heading h1{font-size:27px!important;letter-spacing:-.045em;margin:0!important;padding:0!important}
.memo-heading p{font-size:13px;color:#8290a3;margin:7px 0 0}
.memo-document-title{font-size:23px;font-weight:750;color:#243b59;line-height:1.5;overflow-wrap:anywhere;margin:4px 0 10px}
.memo-document-meta{font-size:11px;color:#8290a3;margin-bottom:24px}
.memo-document{font-size:14px;color:#35465c;line-height:1.9;white-space:pre-wrap;overflow-wrap:anywhere;min-height:290px}
.memo-editor-header{font-size:17px;font-weight:700;color:#2b4261;margin:3px 0 12px}
[class*="st-key-memo_pick_"] button{justify-content:flex-start;text-align:left;width:100%;padding:9px 11px;min-height:42px;border-radius:8px}
[class*="st-key-memo_pick_"] button p{text-align:left;font-size:13px!important;line-height:1.5;overflow-wrap:anywhere}
[class*="st-key-memo_editor_"] [data-testid="stTextArea"] textarea{font-size:14px!important;line-height:1.8!important;background:#fbfcfe!important;border-radius:9px}
[class*="st-key-memo_editor_"] [data-testid="stTextInput"] input{font-size:16px!important;font-weight:650;background:#fbfcfe!important}
[class*="st-key-memo_editor_"] [data-testid="stForm"]{padding:18px!important;border-color:#e1e8f0!important;border-radius:12px!important;background:#fff!important}
[class*="st-key-memo_list"] [data-testid="stCaptionContainer"] p{font-size:11px!important;color:#8290a3!important}
@media(max-width:767px){.memo-document-title{font-size:20px}.memo-document{font-size:14px;line-height:1.8;min-height:200px}}
</style>'''


def filter_memos(records, owner, selected_day, all_dates=False, query=''):
    query = query.strip().casefold()
    return sorted((r for r in records if r['작성자'] == owner
                   and (all_dates or r['날짜'] == selected_day.isoformat())
                   and (not query or query in (r['제목'] + '\n' + split_content(r['내용'])[0]).casefold())),
                  key=lambda r: (r['날짜'], r['수정일']), reverse=True)


def render_memos(records, people, person_label, save, delete):
    if st.session_state.pop('memo_ui_reset_search',False):
        st.session_state['memo_ui_search']=''
    st.markdown(MEMO_CSS, unsafe_allow_html=True)
    st.markdown('<div class="memo-heading"><div><h1>개인 메모장</h1><p>필요한 기록을 찾고, 생각과 업무 내용을 편하게 남기세요.</p></div></div>', unsafe_allow_html=True)
    owner_options = list(dict.fromkeys(people + [r['작성자'] for r in records if r['작성자']])) or ['미지정']
    previous = st.session_state.get('memo_owner', '')
    controls = st.columns([1.3, 1.1, 1, 1.8], vertical_alignment='bottom')
    owner = controls[0].selectbox('작성자', owner_options, index=owner_options.index(previous) if previous in owner_options else 0,
                                  key='memo_owner', format_func=person_label)
    period = controls[1].selectbox('조회 범위', ['전체 날짜', '선택 날짜'], key='memo_ui_period_all_dates')
    filter_day = controls[2].date_input('검색 날짜', value=date.today(), key='memo_selected_day', disabled=period == '전체 날짜')
    selected_day = filter_day if period == '선택 날짜' else date.today()
    query = controls[3].text_input('메모 검색', placeholder='제목 또는 내용 검색', key='memo_ui_search')
    context = (owner, selected_day.isoformat(), period, query)
    if st.session_state.get('memo_ui_context') != context:
        st.session_state['memo_ui_context'] = context
        st.session_state.pop('memo_ui_selected', None)
        st.session_state['memo_ui_mode'] = 'read'
    matches = filter_memos(records, owner, selected_day, period == '전체 날짜', query)
    selected = next((r for r in matches if r['ID'] == st.session_state.get('memo_ui_selected')), None)
    if selected is None and matches and st.session_state.get('memo_ui_mode') != 'new':
        selected = matches[0]
        st.session_state['memo_ui_selected'] = selected['ID']
    if st.session_state.get('memo_ui_notice'):
        st.success(st.session_state.pop('memo_ui_notice'))
    st.markdown('')
    listing, workspace = st.columns([1.2, 2.8], gap='large')
    with listing:
        title_col, add_col = st.columns([1.2, 1])
        title_col.markdown(f'#### 메모 {len(matches)}')
        if add_col.button('새 메모', icon=':material/add:', key='memo_ui_new', use_container_width=True):
            st.session_state['memo_ui_mode'] = 'new'
            st.session_state.pop('memo_ui_selected', None)
            st.rerun()
        with st.container(border=True, height=540, key='memo_list'):
            if not matches:
                st.caption('검색 결과가 없습니다.' if query else '저장된 메모가 없습니다. 오른쪽에서 첫 메모를 작성해 보세요.')
            for record in matches:
                active = selected is not None and selected['ID'] == record['ID']
                if st.button(record['제목'] or '제목 없음', key='memo_pick_' + record['ID'],
                             type='primary' if active else 'secondary', use_container_width=True):
                    st.session_state['memo_ui_selected'] = record['ID']
                    st.session_state['memo_ui_mode'] = 'read'
                    st.rerun()
                preview = ' '.join(split_content(record['내용'])[0].split())
                st.caption('작성일 ' + record['날짜'])
                if preview:st.caption(preview[:65] + ('…' if len(preview) > 65 else ''))
    mode = st.session_state.get('memo_ui_mode', 'read')
    with workspace:
        if selected is not None and mode == 'read':
            with st.container(border=True):
                st.markdown(f'<div class="memo-document-title">{escape(selected["제목"])}</div>'
                            f'<div class="memo-document-meta">{escape(person_label(selected["작성자"]))} · 작성일 {escape(selected["날짜"])} · 수정 {escape(selected["수정일"] or "—")}</div>'
                            f'<div class="memo-document">{escape(split_content(selected["내용"])[0])}</div>', unsafe_allow_html=True)
                show_images(split_content(selected["내용"])[1])
                st.divider()
                if st.button('수정', icon=':material/edit:', key='memo_ui_edit'):
                    st.session_state['memo_ui_mode'] = 'edit'
                    st.rerun()
                with st.expander('메모 삭제'):
                    confirmed = st.checkbox('이 메모를 삭제합니다. 삭제 후 복구할 수 없습니다.', key='memo_confirm_' + selected['ID'])
                    if st.button('삭제', icon=':material/delete_outline:', key='memo_delete_' + selected['ID'], disabled=not confirmed):
                        try:
                            delete(selected['ID'])
                        except Exception:
                            st.error('삭제하지 못했습니다. 연결 상태를 확인하고 다시 시도해 주세요.')
                        else:
                            st.session_state.pop('memo_ui_selected', None)
                            st.session_state['memo_ui_mode'] = 'read'
                            st.session_state['memo_ui_notice'] = '메모를 삭제했습니다.'
                            st.rerun()
        else:
            editing = selected is not None and mode == 'edit'
            record = selected if editing else None
            token = record['ID'] if editing else f'{owner}_{selected_day}_{st.session_state.get("memo_ui_version", 0)}'
            with st.container(key='memo_editor_' + token):
                st.markdown('<div class="memo-editor-header">' + ('메모 수정' if editing else '새 메모 작성') + '</div>', unsafe_allow_html=True)
                st.caption(f'{person_label(owner)} · {record["날짜"] if editing else selected_day.isoformat()}')
                original_body, existing_images = split_content(record['내용']) if editing else ('',[])
                with st.form('memo_form_' + token):
                    title = st.text_input('제목', value=record['제목'] if editing else '', placeholder='메모 제목을 입력하세요')
                    body = st.text_area('내용', value=original_body, height=340,
                                        placeholder='통화 내용, 해야 할 일, 떠오른 생각을 자유롭게 기록하세요.')
                    st.caption('이미지 첨부 · 아래 영역을 클릭한 뒤 Ctrl+V (Mac: ⌘V)')
                    pasted = clipboard(key='memo_paste_'+token,default=[])
                    submitted = st.form_submit_button('저장', type='primary', use_container_width=True)
                show_images(existing_images)
                if submitted:
                    if not title.strip() or not (body.strip() or pasted or existing_images):
                        st.warning('제목과 내용 또는 첨부 이미지를 입력해 주세요.')
                    else:
                        result = {**record} if editing else {'ID': str(uuid.uuid4()), '작성자': owner, '날짜': selected_day.isoformat()}
                        result.update({'제목': title.strip(), '내용': body, '수정일': datetime.now().isoformat(timespec='seconds')})
                        try:
                            if len(body)>48000:raise ValueError('메모 내용이 너무 깁니다. 내용을 나누어 저장해 주세요.')
                            images=save_images(pasted or [],existing_images,token)
                            result['내용']=join_content(body,images)
                            if len(result['내용'])>49000:raise ValueError('메모 내용이 너무 깁니다. 내용을 나누어 저장해 주세요.')
                            save(result)
                        except ValueError as exc:
                            st.error(str(exc))
                        except Exception:
                            st.error('저장하지 못했습니다. 입력 내용은 유지됩니다. 연결 상태를 확인하고 다시 시도해 주세요.')
                        else:
                            st.session_state['memo_ui_selected'] = result['ID']
                            st.session_state['memo_ui_mode'] = 'read'
                            st.session_state['memo_ui_version'] = st.session_state.get('memo_ui_version', 0) + 1
                            # Saved records should remain visible even if a search is active.
                            st.session_state['memo_ui_reset_search'] = True
                            st.session_state['memo_ui_context'] = (owner, selected_day.isoformat(), period, '')
                            st.session_state['memo_ui_notice'] = '메모를 저장했습니다.'
                            st.rerun()
                if editing and st.button('수정 취소', key='memo_ui_cancel'):
                    st.session_state['memo_ui_mode'] = 'read'
                    st.rerun()
    with st.expander('메모 이용 안내'):
        st.caption('선택한 작성자의 모든 메모를 날짜와 관계없이 최신 날짜순으로 표시합니다. 작성일은 각 메모에 별도로 표시되며, 필요한 경우 조회 범위를 선택 날짜로 변경해 검색할 수 있습니다. 이 앱은 공유 편집 방식이므로 다른 사용자도 작성자를 선택하면 메모를 볼 수 있습니다.')
