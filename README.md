# 영업부 업무 일정 대시보드

기존 ERP 앱과 독립적으로 운영하는 Streamlit 업무관리 앱입니다. Google Sheets의 `업무일정`, `업무확인내역`, `팀원정보`, `변경이력` 탭을 사용합니다. `일정현황`은 기존 엑셀 요약용으로 유지됩니다.

## 파일
- `app.py`: 일정 조회, 마감 알림, 달력, 업무 등록/수정, 확인 의견, 변경 이력
- `requirements.txt`: Python 패키지
- `Dockerfile`: 사내 서버/별도 비공개 서버용 실행 이미지
- `.streamlit/config.toml`: UI 설정
- `.streamlit/secrets.toml.example`: 비밀 설정 예시 (**실제 키를 넣어 커밋 금지**)

## 1. GitHub 업로드
압축을 풀고 폴더 안의 파일을 `juwonkim6068/sales-team-calendar` 저장소 최상단에 업로드합니다. `app.py`는 반드시 루트에 있어야 합니다. 숨김 폴더 `.streamlit`도 포함해야 합니다. `secrets.toml`은 절대 업로드하지 마세요.

## 2. Google Sheets
기존 엑셀을 Google Sheets로 가져온 뒤 5개 탭 이름과 열 이름이 원본과 같은지 확인합니다. 서비스 계정 이메일을 해당 시트의 **편집자**로 공유합니다. `팀원정보` 시트에 사용자를 등록합니다: 이메일, 이름, `사용여부=사용`. 관리자 이메일은 Secrets의 `admin_emails`에도 입력합니다. 승인되지 않은 사용자는 차단됩니다.

## 3. 인증/Secrets
`secrets.toml.example`을 참고하여 **서버 내부에서만** `.streamlit/secrets.toml`을 생성합니다. `spreadsheet_id`는 Google Sheets URL의 `/d/`와 `/edit` 사이 문자열입니다. `gcp_service_account`는 서비스 계정 JSON의 값을 옮깁니다. OIDC 인증 제공자(예: 회사 Google Workspace 또는 Microsoft Entra ID)에서 웹 앱을 등록하고, 배포 도메인에 맞는 `redirect_uri`(`https://도메인/oauth2callback`)를 등록해야 합니다. Google 예시 metadata URL이 포함되어 있으며, Microsoft 로그인은 해당 조직의 OIDC 메타데이터 URL로 교체해야 합니다.

Streamlit `st.login()`을 사용하므로 외부 접속을 허용하려면 **반드시 HTTPS + OIDC**를 설정해야 합니다. 미설정 시 앱은 데이터를 표시하지 않습니다. 단순 공개 URL 또는 IP 접근만으로 운영하지 마세요. 회사 보안 승인 및 서버 방화벽/VPN 설정을 먼저 확인하세요.

## 4. 실행
로컬 테스트: `pip install -r requirements.txt` 후 `streamlit run app.py`.

사내/별도 서버: `docker build -t sales-team-calendar .` 후 HTTPS 역방향 프록시, 비밀파일 마운트, 사내 방화벽을 설정한 다음 실행합니다. 예: `docker run -d --name sales-calendar -p 127.0.0.1:8501:8501 -v /SECURE/PATH/secrets.toml:/app/.streamlit/secrets.toml:ro sales-team-calendar`. `/SECURE/PATH`는 실제 서버 내부의 보호된 경로로 변경하세요. 외부에서 8501 포트를 직접 공개하지 않습니다.

## 5. 현재 범위와 주의점
- 구글시트의 수정 내역은 `변경이력` 시트에 남기지만, **직접 시트를 편집한 변경은 앱에서 자동 추적하지 않습니다**.
- 마감일 없는 업무는 마감 임박 목록에서 제외합니다.
- 기존 시트의 D-Day와 마감구분 수식은 화면에서 재계산하므로 날짜 형식에 따른 차이를 줄였습니다.
- 동시에 같은 업무를 수정할 경우 마지막 저장이 우선할 수 있습니다. 높은 동시접속·엄격한 감사 추적이 필요하면 DB 전환을 권장합니다.
- 서버의 로컬 시간대를 `Asia/Seoul`로 설정하세요. 그렇지 않으면 D-Day 계산이 서버 시간대 기준이 됩니다.
- 팀원별 수정 권한은 현재 승인 사용자 공통입니다. 관리자 전용 삭제 기능은 제공하지 않습니다.

## 공유파일 (Google Drive)

사이드바의 `📁 공유파일`은 파일 탐색기 형태입니다. 상단 `파일 업로드`와 `새 폴더`에서 자료를 추가하고, 현재 위치 경로 또는 `상위` 버튼으로 이동합니다. 목록에서 폴더 이름을 누르면 폴더가 열리고, 파일 이름을 누르면 오른쪽에 다운로드·Google Drive 열기·폴더 이동 메뉴가 표시됩니다. 현재 폴더 내 이름 검색, 파일/폴더 필터, 이름·최신·크기순 정렬을 지원합니다. 파일은 앱 서버가 아닌 Google Drive에 저장됩니다. 파일당 업로드·앱 내 다운로드 한도는 100MB이며, 더 큰 기존 파일이나 Google 문서는 `Google Drive에서 열기`를 사용합니다. 다운로드 준비 시 파일 한 개를 현재 사용자 세션 메모리에 보관합니다. 같은 이름의 파일을 올리면 덮어쓰지 않고 별도 파일을 생성합니다. 다른 하위 폴더로 이동할 때는 상위 폴더로 이동한 뒤 대상 폴더로 옮길 수 있습니다.

설정은 기존 Streamlit Community Cloud의 Secrets에서 진행합니다. 기존 `[gcp_service_account]` 인증 내용과 Google Sheets 설정은 변경하지 않습니다. 공유파일은 모든 앱 사용자가 연결된 한 Google 계정의 폴더를 함께 사용합니다. 현재 앱에는 사용자별 로그인/권한 제한이 없으므로 앱 접근 권한을 가진 팀원이 이 폴더의 파일을 읽고 추가·이동할 수 있습니다.

### 개인 내 드라이브 연결 (Google 사용자 OAuth)

이 방식은 서비스 계정 저장공간이 아닌, 승인한 Google 사용자의 저장공간을 사용합니다. 현재 `shared_drive_folder_id`에 설정한 내 드라이브 폴더 ID를 그대로 사용할 수 있습니다. 해당 값이 없을 때만 `drive_folder_id`를 사용합니다. 두 값이 있으면 `shared_drive_folder_id`가 우선합니다.

1. Google Cloud Console에서 프로젝트를 선택하고 **Google Drive API**를 활성화합니다.
2. **Google Auth Platform**에서 앱 이름, 지원 이메일, 대상 사용자와 데이터 액세스를 설정합니다. Drive 권한은 `https://www.googleapis.com/auth/drive`입니다. 기존 폴더의 파일 조회·다운로드·이동을 지원하기 때문에 이 권한을 요청합니다. Google 승인 자체는 Drive 전체 권한이므로 앱을 신뢰하는 관리 계정으로만 승인하세요. 앱 화면의 탐색 범위는 설정한 저장 폴더 아래로 제한됩니다.
3. 외부 앱의 테스트 모드라면 승인할 Google 계정을 **테스트 사용자**에 추가합니다. 외부 앱이 테스트 상태이면 Drive refresh token은 일반적으로 **7일 후 만료**됩니다. 계속 운영하려면 조직 내부 앱 또는 적절한 프로덕션 게시·검증 설정을 완료하세요. Drive 권한의 Google 검증 요건은 계정·배포 범위에 따라 다릅니다. 조직 관리자가 OAuth 연결을 차단할 수도 있습니다.
4. OAuth 클라이언트 ID를 **데스크톱 앱** 유형으로 만들고 클라이언트 JSON을 관리자 PC에 다운로드합니다. Streamlit URL을 리디렉션 URI로 설정하는 방식이 아닙니다. 승인 스크립트가 같은 PC의 브라우저와 로컬 콜백을 사용합니다.
5. 관리자 PC에서 저장소를 내려받고 다음을 실행합니다. 클라이언트 JSON과 출력 TOML은 저장소 밖의 비공개 폴더에 저장하세요. 아래 경로는 본인 PC 경로로 바꿉니다.

```bash
python -m pip install "google-auth-oauthlib>=1.2,<2"
python tools/setup_drive_oauth.py --client "/private/path/client_secret.json" --output "/private/path/drive-oauth-secrets.toml"
```

Windows에서는 `python` 대신 `py`를 사용할 수 있습니다. 출력 파일 이름이 이미 존재하면 스크립트는 덮어쓰지 않습니다. 브라우저에서 **저장 폴더를 소유하거나 수정 가능한 Google 계정**으로 승인합니다. 스크립트는 토큰을 화면에 출력하지 않고 지정한 로컬 파일에 저장합니다. Windows에서는 해당 폴더의 계정 접근 권한도 제한하세요.

6. 출력 TOML의 `[drive_oauth]` 섹션을 **Streamlit Cloud Secrets 맨 아래**에 추가합니다. 기존 `[gcp_service_account]` 및 다른 설정은 유지합니다. 다음은 구조 예시이며 실제 값은 승인 스크립트가 생성합니다. 비밀값을 채팅·GitHub에 올리지 마세요.

```toml
# 최상위 항목: 모든 [섹션]보다 위에 유지
shared_drive_folder_id = "기존_내_드라이브_폴더_ID"

# 기존 [gcp_service_account]와 다른 섹션은 그대로 유지

# 맨 아래에 새 섹션으로 추가
[drive_oauth]
client_id = "승인_스크립트가_생성한_값"
client_secret = "승인_스크립트가_생성한_값"
refresh_token = "승인_스크립트가_생성한_값"
```

7. Secrets를 저장하고 앱을 새로고침합니다. 공유파일 메뉴에 **저장 계정: Google 사용자 OAuth**가 표시되는지 확인합니다. 작은 파일 업로드 → 실제 Drive 저장 확인 → 다운로드 → 하위 폴더 생성/이동 순으로 검증합니다. 사용자별 별도 Google 로그인은 필요하지 않습니다. 토큰은 서버에서만 사용하며 만료된 액세스 토큰은 자동 갱신됩니다. 승인을 취소하거나 refresh token이 만료되면 다시 승인한 뒤 `[drive_oauth]`만 갱신합니다. 잘못된 OAuth 설정을 서비스 계정으로 자동 대체하지 않습니다.

### 조직 공유 드라이브 연결 (서비스 계정)

`[drive_oauth]` 섹션이 없으면 기존 서비스 계정 정보를 재사용해 별도의 Drive 클라이언트를 만듭니다. Google Drive API를 활성화하고, 공유 드라이브 내 폴더를 생성한 뒤 기존 서비스 계정을 파일 추가·이동 가능한 멤버로 추가합니다. `shared_drive_folder_id`에는 해당 폴더 ID를 설정합니다. 개인 내 드라이브를 서비스 계정에 공유하는 것만으로는 서비스 계정의 저장공간 제한을 해결하지 못합니다.

어느 방식을 선택하든 기존 Sheets 클라이언트의 권한과 인증 코드는 변경하지 않습니다. 실제 OAuth 승인과 Drive 실연동은 관리자 PC 및 Streamlit Cloud에서 수행해야 합니다.
