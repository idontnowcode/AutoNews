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

def get_next_optimal_time(days_str: str = 'mon,tue', hours_str: str = '20') -> str:
    """
    설정된 요일/시간 조합 중 가장 가까운 다음 업로드 시각 반환 (UTC ISO 8601).
    days_str : 'mon,tue' 또는 'everyday' (매일)
    hours_str: '20' 또는 '9,20' (KST, 쉼표로 여러 시간 지정 가능)
    """
    # 요일 파싱
    if days_str.strip().lower() == 'everyday':
        target_days = list(range(7))
    else:
        target_days = [_DAY_MAP[d.strip().lower()] for d in days_str.split(',')
                       if d.strip().lower() in _DAY_MAP]
    if not target_days:
        target_days = [0, 1]  # 기본 월·화

    # 시간 파싱 (KST → UTC)
    hours_utc = []
    for h in hours_str.split(','):
        try:
            hours_utc.append((int(h.strip()) - 9) % 24)
        except ValueError:
            pass
    if not hours_utc:
        hours_utc = [(20 - 9) % 24]  # 기본 20시 KST

    now_utc = datetime.now(timezone.utc)
    best: datetime | None = None

    # 오늘 포함 7일, 모든 (요일 × 시간) 조합에서 가장 가까운 미래 시각 탐색
    for offset in range(8):
        candidate_date = now_utc + timedelta(days=offset)
        if candidate_date.weekday() not in target_days:
            continue
        for hour_utc in hours_utc:
            publish_dt = candidate_date.replace(hour=hour_utc, minute=0, second=0, microsecond=0)
            if publish_dt <= now_utc:
                continue  # 이미 지난 시각 스킵
            if best is None or publish_dt < best:
                best = publish_dt

    if best is None:
        # fallback: 내일 첫 번째 시간
        best = (now_utc + timedelta(days=1)).replace(
            hour=hours_utc[0], minute=0, second=0, microsecond=0)

    return best.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'


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
