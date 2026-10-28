"""Run on the administrator's own PC; never run with real tokens in shared logs."""
import argparse
import json
import os
from pathlib import Path

SCOPE = 'https://www.googleapis.com/auth/drive'


def write_secrets(path, credentials):
    if not credentials.refresh_token:
        raise ValueError('Refresh token이 없습니다. Google 계정에서 기존 앱 연결을 해제한 후 다시 승인하세요.')
    values = {'client_id': credentials.client_id, 'client_secret': credentials.client_secret,
              'refresh_token': credentials.refresh_token}
    # Exclusive creation prevents overwriting any existing credential file.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as output:
        output.write('[drive_oauth]\n')
        for key, value in values.items():
            output.write(f'{key} = {json.dumps(value, ensure_ascii=False)}\n')


def main():
    parser = argparse.ArgumentParser(description='관리자 PC에서 Drive OAuth를 승인하고 Secrets 조각을 로컬 파일로 저장합니다.')
    parser.add_argument('--client', required=True, type=Path, help='Google에서 다운로드한 데스크톱 OAuth 클라이언트 JSON')
    parser.add_argument('--output', required=True, type=Path, help='새로 생성할 비공개 TOML 파일 (저장소 밖의 경로)')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    if args.output.resolve().is_relative_to(repo):
        parser.error('인증 파일은 Git 저장소 밖에 저장해 주세요.')
    if args.output.exists():
        parser.error('출력 파일이 이미 있습니다. 다른 경로를 선택해 주세요.')
    from google_auth_oauthlib.flow import InstalledAppFlow
    # PKCE and state are provided/verified by the OAuth library. Loopback callback
    # is for a Desktop client running on this same PC, not the deployed web app.
    config = json.loads(args.client.read_text(encoding='utf-8'))
    if 'installed' not in config:
        parser.error('데스크톱 앱 유형의 OAuth 클라이언트 JSON이 필요합니다.')
    flow = InstalledAppFlow.from_client_config(config, [SCOPE], autogenerate_code_verifier=True)
    credentials = flow.run_local_server(host='localhost', port=0, open_browser=True,
        access_type='offline', prompt='consent', timeout_seconds=300,
        authorization_prompt_message='열리는 브라우저에서 저장 폴더를 소유한 Google 계정으로 승인하세요.',
        success_message='승인되었습니다. 이 창을 닫고 터미널로 돌아가세요.')
    write_secrets(args.output, credentials)
    print('인증 완료. 지정한 로컬 TOML 파일의 [drive_oauth]를 Streamlit Cloud Secrets 끝에 추가하세요. 파일 내용은 채팅이나 GitHub에 올리지 마세요.')


if __name__ == '__main__':
    main()
