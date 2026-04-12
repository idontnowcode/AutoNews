import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def _get_youtube_client():
    """환경 변수에서 토큰 읽기"""
    token_json = os.environ['YOUTUBE_TOKEN']
    creds = Credentials.from_authorized_user_info(json.loads(token_json))
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
