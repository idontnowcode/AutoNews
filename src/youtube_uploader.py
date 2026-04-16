import os
import json
from datetime import datetime, timezone, timedelta
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


_DAY_MAP = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}

def get_next_optimal_time(days_str: str = 'mon,tue', hour_kst: int = 20) -> str:
    """
    설정된 요일 중 가장 가까운 다음 업로드 시각 반환 (UTC ISO 8601).
    days_str: 'mon,tue' 형식 (쉼표 구분)
    hour_kst: KST 시간 (기본 20시) → UTC = KST - 9
    """
    target_days = [_DAY_MAP[d.strip().lower()] for d in days_str.split(',') if d.strip().lower() in _DAY_MAP]
    if not target_days:
        target_days = [0, 1]  # 기본 월·화

    hour_utc = (hour_kst - 9) % 24
    now_utc = datetime.now(timezone.utc)

    # 오늘부터 7일 내 가장 가까운 목표 요일 탐색
    for offset in range(1, 8):
        candidate = now_utc + timedelta(days=offset)
        if candidate.weekday() in target_days:
            publish_dt = candidate.replace(hour=hour_utc, minute=0, second=0, microsecond=0)
            return publish_dt.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'

    # fallback: 내일 같은 시각
    tomorrow = (now_utc + timedelta(days=1)).replace(hour=hour_utc, minute=0, second=0, microsecond=0)
    return tomorrow.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'


def upload_shorts(video_path: str, script_data: dict,
                  youtube_title_prefix: str = '',
                  publish_at: str = None) -> str:
    """YouTube Shorts 업로드 → 영상 ID 반환
    youtube_title_prefix: 영상 속 제목과 별개로 유튜브 업로드 제목 앞에 붙는 태그
                          예) '[일분 경제] ', '[일분 뉴스] '
    """
    youtube = _get_youtube_client()

    raw_title   = script_data['title']
    yt_title    = f"{youtube_title_prefix}{raw_title}"[:100]
    hashtags    = ' '.join([f'#{t}' for t in script_data.get('hashtags', [])])
    description = f"{script_data.get('description', '')}\n\n{hashtags} #Shorts"

    request = youtube.videos().insert(
        part='snippet,status',
        body={
            'snippet': {
                'title':           yt_title,
                'description':     description,
                'tags':            script_data.get('hashtags', []) + ['Shorts'],
                'categoryId':      '25',
                'defaultLanguage': 'ko',
            },
            'status': {
                'privacyStatus':           'private' if publish_at else 'public',
                'selfDeclaredMadeForKids': False,
                **({'publishAt': publish_at} if publish_at else {}),
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
    video_id = response['id']
    if publish_at:
        print(f'   📅 예약 발행: {publish_at} (UTC) → https://youtu.be/{video_id}')
    return video_id
