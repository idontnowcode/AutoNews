import os
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def _get_youtube_client():
    """환경 변수에서 토큰 읽기 + 만료 시 자동 갱신"""
    token_json = os.environ['YOUTUBE_TOKEN']
    creds = Credentials.from_authorized_user_info(json.loads(token_json))

    # 액세스 토큰 만료 시 refresh_token으로 자동 갱신
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            print('🔑 YouTube OAuth 토큰 갱신 중...')
            creds.refresh(Request())
            print('   갱신 완료')
        else:
            raise RuntimeError(
                'YouTube OAuth 토큰이 유효하지 않습니다. '
                'tools/refresh_youtube_token.py를 로컬에서 실행하여 '
                'YOUTUBE_TOKEN secret을 재발급하세요.'
            )

    return build('youtube', 'v3', credentials=creds)


def upload_shorts(video_path: str, script_data: dict) -> str:
    """YouTube Shorts 업로드 → 영상 ID 반환"""
    youtube = _get_youtube_client()

    title       = script_data['title'][:100]
    hashtags    = ' '.join([f'#{t}' for t in script_data.get('hashtags', [])])
    description = f"{script_data.get('description', '')}\n\n{hashtags} #Shorts"

    request = youtube.videos().insert(
        part='snippet,status',
        body={
            'snippet': {
                'title':           title,
                'description':     description,
                'tags':            script_data.get('hashtags', []) + ['Shorts', '뉴스'],
                'categoryId':      '25',     # News & Politics
                'defaultLanguage': 'ko',
            },
            'status': {
                'privacyStatus':           'public',
                'selfDeclaredMadeForKids': False,
            }
        },
        media_body=MediaFileUpload(
            video_path,
            mimetype='video/mp4',
            chunksize=-1,
            resumable=True
        )
    )
    response = request.execute()
    return response['id']
