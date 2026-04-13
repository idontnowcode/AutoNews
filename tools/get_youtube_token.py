"""
YouTube OAuth2 토큰 발급 스크립트
===================================
사용법:
  1. Google Cloud Console에서 OAuth 클라이언트 ID 다운로드 → client_secrets.json 저장
  2. pip install google-auth-oauthlib
  3. python tools/get_youtube_token.py
  4. 브라우저에서 업로드할 채널 계정으로 로그인
  5. 출력된 JSON을 GitHub Secret YOUTUBE_TOKEN에 붙여넣기
"""

import json
import os
import sys

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    sys.exit('google-auth-oauthlib 미설치:\n  pip install google-auth-oauthlib')

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
SECRETS_FILE = os.path.join(os.path.dirname(__file__), '..', 'client_secrets.json')
OUTPUT_FILE  = os.path.join(os.path.dirname(__file__), '..', 'token.json')


def main():
    if not os.path.exists(SECRETS_FILE):
        print('❌ client_secrets.json 파일이 없습니다.')
        print()
        print('📋 준비 방법:')
        print('  1. https://console.cloud.google.com 접속')
        print('  2. 프로젝트 선택 (또는 새로 생성)')
        print('  3. APIs & Services → Credentials')
        print('  4. Create Credentials → OAuth client ID → Desktop app')
        print('  5. 다운로드한 JSON 파일을 client_secrets.json 으로 프로젝트 루트에 저장')
        print('  6. YouTube Data API v3 가 사용 설정되어 있는지 확인')
        sys.exit(1)

    print('🔑 브라우저가 열립니다. 업로드할 YouTube 채널 계정으로 로그인하세요.')
    print()

    flow = InstalledAppFlow.from_client_secrets_file(SECRETS_FILE, SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)

    # token.json 저장
    token_data = {
        'token':         creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri':     creds.token_uri,
        'client_id':     creds.client_id,
        'client_secret': creds.client_secret,
        'scopes':        list(creds.scopes),
    }

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(token_data, f, indent=2)

    print(f'✅ 토큰 저장 완료: {OUTPUT_FILE}')
    print()
    print('=' * 60)
    print('📋 아래 내용을 GitHub Secret YOUTUBE_TOKEN 에 붙여넣으세요:')
    print('=' * 60)
    print(json.dumps(token_data))
    print('=' * 60)


if __name__ == '__main__':
    main()
