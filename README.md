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
