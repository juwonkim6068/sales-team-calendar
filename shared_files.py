"""Google Drive shared-file UI. Existing Sheets credentials and scopes are unchanged."""
import io
import json

import streamlit as st
from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as UserCredentials
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from googleapiclient.errors import HttpError

FOLDER = 'application/vnd.google-apps.folder'
MAX_BYTES = 100 * 1024 * 1024
FIELDS = 'id,name,mimeType,size,modifiedTime,parents,driveId,capabilities(canAddChildren),webViewLink'

EXPLORER_CSS = """<style>
.files-heading{margin:4px 0 24px;padding:24px 28px;background:linear-gradient(110deg,#edf4ff,#f5f9ff);border:1px solid #dbe7f7;border-radius:16px}
.files-heading>span{font-size:10px;font-weight:800;letter-spacing:.18em;color:#547db4}
.files-heading h2{font-size:24px!important;margin:8px 0 4px!important;padding:0!important}
.files-heading p{font-size:13px;color:#657a95;margin:0;line-height:1.7}
[class*="st-key-shared_open_"] button,[class*="st-key-shared_select_"] button{text-align:left;justify-content:flex-start;min-height:44px;padding:9px 12px;border-radius:8px;border-color:transparent;box-shadow:none}
[class*="st-key-shared_open_"] button:hover,[class*="st-key-shared_select_"] button:hover{background:#edf4ff;border-color:#d2e3fa;color:#195bbe}
[class*="st-key-shared_open_"] button p,[class*="st-key-shared_select_"] button p{overflow-wrap:anywhere;text-align:left}
@media(max-width:767px){.files-heading{padding:18px}.files-heading h2{font-size:20px!important}}
</style>"""


def format_size(value):
    if value is None:
        return '—'
    size = int(value)
    if size < 1024:
        return f'{size} B'
    if size < 1024 * 1024:
        return f'{size / 1024:.1f} KB'
    return f'{size / 1024 / 1024:.1f} MB'


def file_icon(item):
    kind = item['mimeType']
    if 'spreadsheet' in kind or 'excel' in kind:
        return '📊'
    if kind.startswith('image/'):
        return '🖼️'
    if kind == 'application/pdf':
        return '📕'
    if 'presentation' in kind:
        return '📽️'
    return '📄'


def filter_items(items, query='', category='전체', order='이름순'):
    result = [x for x in items if query.strip().casefold() in x['name'].casefold()
              and (category == '전체' or (x['mimeType'] == FOLDER) == (category == '폴더'))]
    if order == '최신순':
        result.sort(key=lambda x: x.get('modifiedTime', ''), reverse=True)
    elif order == '크기순':
        result.sort(key=lambda x: int(x.get('size', 0)), reverse=True)
    else:
        result.sort(key=lambda x: x['name'].casefold())
    # Keep folders grouped before files for every ordering.
    result.sort(key=lambda x: x['mimeType'] != FOLDER)
    return result


def drive_error_message(exc):
    """Explain safe status/reason codes without exposing response bodies or credentials."""
    status = getattr(exc.resp, 'status', None)
    try:
        error = json.loads(exc.content).get('error', {})
        reasons = {x.get('reason') for x in error.get('errors', [])}
        reasons.update(x.get('reason') for x in error.get('details', []))
    except (ValueError, TypeError, AttributeError):
        reasons = set()
    if reasons & {'accessNotConfigured', 'SERVICE_DISABLED'}:
        return 'Google Drive API가 비활성화되어 있습니다. Drive 인증에 사용하는 OAuth 클라이언트 또는 서비스 계정의 Google Cloud 프로젝트에서 Google Drive API를 활성화해 주세요.'
    if 'storageQuotaExceeded' in reasons:
        return 'Google Drive 저장공간 제한입니다. 서비스 계정은 개인 내 드라이브에 파일을 업로드할 수 없습니다. 공유 드라이브 폴더 또는 별도의 사용자 OAuth 인증이 필요합니다.'
    if status == 404:
        return '저장 폴더를 찾을 수 없거나 연결 계정에 접근 권한이 없습니다(404). 폴더 ID와 OAuth 승인에 사용한 Google 계정의 폴더 접근 권한을 확인해 주세요. 서비스 계정 방식이라면 client_email 계정의 접근 권한을 확인하세요.'
    if status == 403:
        return 'Google Drive 접근이 거부되었습니다(403). Drive API 활성화 여부, 연결한 계정의 폴더 수정 권한과 조직의 공유 정책을 확인해 주세요.'
    if status == 401:
        return 'Google Drive 인증이 거부되었습니다(401). Drive OAuth 승인 또는 서비스 계정 키의 유효 여부를 확인해 주세요. 인증 정보는 채팅에 보내지 마세요.'
    return f'Google Drive 요청이 실패했습니다(HTTP {status or "알 수 없음"}). 잠시 후 다시 시도하고 계속되면 이 오류 코드를 알려주세요.'


def drive_client(info, oauth=None):
    if oauth is not None:
        required = ('client_id', 'client_secret', 'refresh_token')
        if not all(str(oauth.get(k, '')).strip() for k in required):
            raise ValueError('Streamlit Secrets의 [drive_oauth]에 client_id, client_secret, refresh_token을 모두 설정해 주세요. 기존 Sheets 인증은 변경하지 않습니다.')
        credentials = UserCredentials(
            token=None, refresh_token=oauth['refresh_token'],
            token_uri='https://oauth2.googleapis.com/token',
            client_id=oauth['client_id'], client_secret=oauth['client_secret'],
            scopes=['https://www.googleapis.com/auth/drive'])
    else:
        credentials = Credentials.from_service_account_info(
            info, scopes=['https://www.googleapis.com/auth/drive'])
    return build('drive', 'v3', credentials=credentials, cache_discovery=False)


def metadata(client, item_id):
    return client.files().get(fileId=item_id, fields=FIELDS, supportsAllDrives=True).execute()


def children(client, folder_id):
    items, token = [], None
    while True:
        result = client.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields=f'nextPageToken,files({FIELDS})', pageSize=100,
            pageToken=token, orderBy='folder,name', supportsAllDrives=True,
            includeItemsFromAllDrives=True).execute()
        items.extend(result.get('files', []))
        token = result.get('nextPageToken')
        if not token:
            return items


def clean_name(value):
    value = value.strip()
    if not value or value in ('.', '..') or any(c in value for c in ('/', '\\', '\x00')):
        raise ValueError('이름을 입력하고 / 또는 \\ 문자는 제외해 주세요.')
    return value


def upload(client, folder_id, uploaded):
    if uploaded.size > MAX_BYTES:
        raise ValueError('파일은 100MB 이하로 업로드해 주세요.')
    uploaded.seek(0)
    return client.files().create(
        body={'name': clean_name(uploaded.name), 'parents': [folder_id]},
        media_body=MediaIoBaseUpload(uploaded, mimetype=uploaded.type or 'application/octet-stream', resumable=True),
        fields='id,name', supportsAllDrives=True).execute()


def download(client, item):
    if int(item.get('size', 0)) > MAX_BYTES:
        raise ValueError('100MB 초과 파일은 Google Drive에서 다운로드해 주세요.')
    data = io.BytesIO()
    request = client.files().get_media(fileId=item['id'], supportsAllDrives=True)
    reader = MediaIoBaseDownload(data, request)
    done = False
    while not done:
        _, done = reader.next_chunk()
        if data.tell() > MAX_BYTES:
            raise ValueError('다운로드 가능한 크기(100MB)를 초과했습니다.')
    return data.getvalue()


def render_shared_files(credential_info):
    st.title('📁 공유파일')
    st.caption('파일은 Google Drive에 저장됩니다. 폴더를 만들어 업무별로 정리하세요. 파일당 최대 100MB입니다.')
    try:
        oauth = st.secrets.get('drive_oauth')
        root_id = str(st.secrets.get('shared_drive_folder_id') or st.secrets.get('drive_folder_id', '')).strip()
    except FileNotFoundError:
        root_id, oauth = '', None
    if not root_id:
        st.info('Streamlit Cloud Secrets 최상위에 shared_drive_folder_id = "저장 폴더 ID"를 추가해 주세요. 기존 [gcp_service_account] 설정은 그대로 유지하세요.')
        st.caption('내 드라이브는 별도의 [drive_oauth] 사용자 인증을 설정하세요. 서비스 계정만 사용하는 경우에는 공유 드라이브가 필요합니다.')
        return
    if not all(c.isalnum() or c in '_-' for c in root_id):
        st.error('shared_drive_folder_id에는 폴더 URL 대신 폴더 ID만 입력해 주세요.')
        return
    try:
        client = drive_client(credential_info, oauth=oauth)
        root = metadata(client, root_id)
        if root['mimeType'] != FOLDER:
            raise ValueError('저장 위치가 폴더가 아닙니다.')
        if not root.get('driveId') and oauth is None:
            raise ValueError('개인 내 드라이브에 업로드하려면 Streamlit Cloud Secrets에 [drive_oauth] 사용자 인증을 추가해 주세요. 기존 [gcp_service_account]는 그대로 유지하세요.')
        if not root.get('capabilities', {}).get('canAddChildren'):
            raise ValueError('연결한 Google 계정에 이 폴더의 파일 추가 권한이 없습니다.')
        path = st.session_state.get('shared_file_path', [root])
        if not path or path[0]['id'] != root_id:
            path = [root]
        # Revalidate the breadcrumb so operations stay inside the configured root.
        for index in range(1, len(path)):
            item = metadata(client, path[index]['id'])
            if path[index - 1]['id'] not in item.get('parents', []) or item['mimeType'] != FOLDER:
                path = [root]
                break
            path[index] = item
        st.session_state['shared_file_path'] = path
        current = path[-1]
        items = children(client, current['id'])
        folders = [x for x in items if x['mimeType'] == FOLDER]
        files = [x for x in items if x['mimeType'] != FOLDER]
        st.markdown(EXPLORER_CSS, unsafe_allow_html=True)
        st.markdown('<div class="files-heading"><span>TEAM SPACE</span><h2>팀의 자료를 한곳에</h2><p>폴더를 열고 파일을 넣어 보세요. 변경사항은 Google Drive에 바로 저장됩니다.</p></div>', unsafe_allow_html=True)
        toolbar = st.columns([1.2, 1.2, 1, 2.6], vertical_alignment='center')
        with toolbar[0].popover('↑ 파일 업로드', use_container_width=True):
            st.markdown('#### 현재 폴더에 파일 추가')
            st.caption(f'저장 위치: {current["name"]} · 파일당 최대 100MB')
            with st.form('shared_upload_' + current['id'], clear_on_submit=True):
                selected = st.file_uploader('파일을 끌어 놓거나 찾아서 선택하세요', accept_multiple_files=True)
                submitted = st.form_submit_button('업로드', type='primary', use_container_width=True)
            if submitted:
                if not selected:
                    st.warning('업로드할 파일을 선택해 주세요.')
                else:
                    completed = []
                    progress = st.progress(0, text='파일을 저장하고 있습니다…')
                    for index, uploaded in enumerate(selected):
                        try:
                            upload(client, current['id'], uploaded)
                            completed.append(uploaded.name)
                        except HttpError as exc:
                            st.error(f'{uploaded.name}: {drive_error_message(exc)} 재시도 전 파일 목록을 확인해 주세요.')
                        except Exception:
                            st.error(f'{uploaded.name}: 저장하지 못했습니다. 권한·용량·파일 크기를 확인한 뒤 다시 시도해 주세요.')
                        progress.progress((index + 1) / len(selected))
                    if completed:
                        st.success(f'{len(completed)}개 파일을 저장했습니다.')
                    items = children(client, current['id'])
                    folders = [x for x in items if x['mimeType'] == FOLDER]
                    files = [x for x in items if x['mimeType'] != FOLDER]
        with toolbar[1].popover('＋ 새 폴더', use_container_width=True):
            st.markdown('#### 새 폴더 만들기')
            with st.form('shared_folder_create', clear_on_submit=True):
                name = st.text_input('폴더 이름', placeholder='예: 견적서, 계약서, 회의자료')
                if st.form_submit_button('폴더 생성', type='primary', use_container_width=True):
                    client.files().create(body={'name': clean_name(name), 'mimeType': FOLDER, 'parents': [current['id']]}, fields='id', supportsAllDrives=True).execute()
                    st.session_state['shared_file_notice'] = '폴더를 만들었습니다.'
                    st.rerun()
        if toolbar[2].button('↻ 새로고침', use_container_width=True):
            st.session_state.pop('shared_file_download', None)
            st.rerun()
        toolbar[3].caption(f'📂 폴더 {len(folders)}개　 ·　 📄 파일 {len(files)}개')
        with st.container(border=True):
            navigation = st.columns([1, 6], vertical_alignment='center')
            if navigation[0].button('↑ 상위', disabled=len(path) == 1, use_container_width=True):
                st.session_state['shared_file_path'] = path[:-1]
                st.session_state.pop('shared_file_selected', None)
                st.rerun()
            navigation[1].caption('현재 위치')
            crumbs = st.columns([1] * len(path))
            for index, part in enumerate(path):
                if crumbs[index].button(('🏠 공유파일' if index == 0 else '📁 ' + part['name']), key='shared_crumb_' + part['id'], use_container_width=True, disabled=index == len(path) - 1):
                    st.session_state['shared_file_path'] = path[:index + 1]
                    st.session_state.pop('shared_file_selected', None)
                    st.rerun()
        notice = st.session_state.pop('shared_file_notice', None)
        if notice:
            st.success(notice)
        controls = st.columns([3, 1.4, 1.4])
        query = controls[0].text_input('현재 폴더에서 검색', placeholder='🔎 파일 또는 폴더 이름 검색', label_visibility='collapsed', key='shared_file_search_' + current['id'])
        category = controls[1].selectbox('종류', ['전체', '폴더', '파일'], label_visibility='collapsed')
        order = controls[2].selectbox('정렬', ['이름순', '최신순', '크기순'], label_visibility='collapsed')
        visible = filter_items(items, query, category, order)
        listing, detail = st.columns([3.7, 1.5], gap='large')
        with listing:
            with st.container(border=True):
                st.markdown('#### 파일 및 폴더')
                st.caption('폴더 이름을 누르면 열립니다. 파일 이름을 누르면 다운로드·이동 메뉴가 표시됩니다.')
                header = st.columns([4.5, 1.4, 1.3])
                header[0].caption('이름')
                header[1].caption('수정일')
                header[2].caption('크기')
                st.divider()
                if not visible:
                    if items:
                        st.info('검색 결과가 없습니다. 검색어나 종류를 변경해 보세요.')
                    else:
                        st.markdown('### 📂 아직 비어 있는 폴더예요')
                        st.caption('위의 ‘파일 업로드’로 자료를 넣거나 ‘새 폴더’로 정리를 시작하세요.')
                for item in visible:
                    row = st.columns([4.5, 1.4, 1.3], vertical_alignment='center')
                    is_folder = item['mimeType'] == FOLDER
                    chosen = st.session_state.get('shared_file_selected') == item['id']
                    label = ('📁 ' if is_folder else file_icon(item) + ' ') + item['name']
                    if row[0].button(label, key=('shared_open_' if is_folder else 'shared_select_') + item['id'], use_container_width=True, type='primary' if chosen and not is_folder else 'secondary'):
                        st.session_state.pop('shared_file_download', None)
                        if is_folder:
                            st.session_state['shared_file_path'] = path + [item]
                            st.session_state.pop('shared_file_selected', None)
                        else:
                            st.session_state['shared_file_selected'] = item['id']
                        st.rerun()
                    row[1].caption(item.get('modifiedTime', '')[:10] or '—')
                    row[2].caption('폴더' if is_folder else format_size(item.get('size')))
        chosen = next((x for x in visible if x['mimeType'] != FOLDER and x['id'] == st.session_state.get('shared_file_selected')), None)
        with detail:
            with st.container(border=True):
                if chosen is None:
                    st.markdown('### 📄 파일 선택')
                    st.write('목록에서 파일을 선택해 주세요.')
                    st.caption('여기에서 다운로드하거나 다른 폴더로 옮길 수 있습니다.')
                else:
                    st.markdown('### ' + file_icon(chosen))
                    st.write(chosen['name'])
                    st.caption(format_size(chosen.get('size')) + ' · ' + (chosen.get('modifiedTime', '')[:10] or '수정일 정보 없음'))
                    st.divider()
                    if not chosen['mimeType'].startswith('application/vnd.google-apps.'):
                        cached = st.session_state.get('shared_file_download')
                        if not cached or cached[0] != chosen['id']:
                            if st.button('↓ 다운로드 준비', key='shared_prepare_' + chosen['id'], type='primary', use_container_width=True):
                                with st.spinner('파일을 준비하고 있습니다…'):
                                    st.session_state['shared_file_download'] = (chosen['id'], download(client, chosen))
                                st.rerun()
                        else:
                            st.download_button('↓ 내 PC에 저장', cached[1], file_name=chosen['name'], mime=chosen['mimeType'], key='shared_download_' + chosen['id'], on_click='ignore', type='primary', use_container_width=True)
                    else:
                        st.caption('Google 문서는 아래 버튼으로 열어 다운로드할 수 있습니다.')
                    if chosen.get('webViewLink'):
                        st.link_button('↗ Google Drive에서 열기', chosen['webViewLink'], use_container_width=True)
                    destinations = ([path[-2]] if len(path) > 1 else []) + folders
                    if destinations:
                        st.divider()
                        st.markdown('**폴더로 이동**')
                        target = st.selectbox('대상 폴더', range(len(destinations)), format_func=lambda i: ('↑ 상위 · ' if i == 0 and len(path) > 1 else '📁 ') + destinations[i]['name'], key='shared_target_' + chosen['id'])
                        if st.button('이동', key='shared_move_' + chosen['id'], use_container_width=True):
                            client.files().update(fileId=chosen['id'], addParents=destinations[target]['id'], removeParents=current['id'], fields='id', supportsAllDrives=True).execute()
                            st.session_state.pop('shared_file_download', None)
                            st.session_state.pop('shared_file_selected', None)
                            st.session_state['shared_file_notice'] = '파일을 이동했습니다.'
                            st.rerun()
                    else:
                        st.caption('새 폴더를 만들면 파일을 폴더별로 정리할 수 있습니다.')
        with st.expander('연결 정보'):
            st.caption('저장 계정: Google 사용자 OAuth' if oauth is not None else '저장 계정: 서비스 계정 · 공유 드라이브')
            st.caption('파일은 현재 Google Drive 폴더에 저장됩니다. 같은 이름으로 올린 파일은 별도 파일로 보관됩니다.')
    except RefreshError:
        st.error('Google Drive 사용자 인증을 갱신하지 못했습니다. OAuth 승인이 만료되거나 취소되었을 수 있습니다. 설정 안내에 따라 다시 승인하고 [drive_oauth]만 갱신해 주세요. 기존 Sheets 인증은 변경하지 마세요.')
    except HttpError as exc:
        st.error(drive_error_message(exc))
    except ValueError as exc:
        st.error(str(exc))
    except Exception:
        st.error('Google Drive 작업을 완료하지 못했습니다. 폴더 ID, Drive API 활성화, 서비스 계정의 공유 드라이브 권한을 확인한 후 다시 시도해 주세요.')
