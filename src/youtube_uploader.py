import os
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def _get_youtube_client(language: str = 'ko'):
    """환경 변수에서 토큰 읽기 + 만료 시 자동 갱신.
    language='en' → YOUTUBE_TOKEN_EN 사용 (없으면 YOUTUBE_TOKEN fallback)
    """
    token_env = 'YOUTUBE_TOKEN'
    if language == 'en' and os.environ.get('YOUTUBE_TOKEN_EN'):
        token_env = 'YOUTUBE_TOKEN_EN'
        print('   🇺🇸 영어 채널 토큰(YOUTUBE_TOKEN_EN) 사용')
    elif language == 'en':
        print('   ⚠️  YOUTUBE_TOKEN_EN 미설정 — 기본 토큰(YOUTUBE_TOKEN) 사용')

    token_json = os.environ[token_env]
    creds = Credentials.from_authorized_user_info(json.loads(token_json))

    # 액세스 토큰 만료 시 refresh_token으로 자동 갱신
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            print('🔑 YouTube OAuth 토큰 갱신 중...')
            creds.refresh(Request())
            print('   갱신 완료')
        else:
            raise RuntimeError(
                f'YouTube OAuth 토큰({token_env})이 유효하지 않습니다. '
                'tools/refresh_youtube_token.py를 로컬에서 실행하여 secret을 재발급하세요.'
            )

    return build('youtube', 'v3', credentials=creds)


_DAY_MAP = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}


def get_next_optimal_time(days_str: str = 'everyday',
                          slots_json: str = '[]',
                          category: str = 'news') -> str:
    """
    설정된 요일·슬롯 조합 중 해당 카테고리의 가장 가까운 다음 발행 시각 반환 (UTC ISO 8601).

    days_str  : 'everyday' 또는 'mon,tue,...'
    slots_json: '[{"hour":9,"category":"news"},{"hour":20,"category":"curriculum"}]'
    category  : 'news' 또는 'curriculum'
    """
    # 요일 파싱
    if days_str.strip().lower() == 'everyday':
        target_days = list(range(7))
    else:
        target_days = [_DAY_MAP[d.strip().lower()] for d in days_str.split(',')
                       if d.strip().lower() in _DAY_MAP]
    if not target_days:
        target_days = list(range(7))

    # 슬롯에서 해당 카테고리 시간 추출 (KST → UTC)
    try:
        slots = json.loads(slots_json) if slots_json else []
    except Exception:
        slots = []
    hours_kst = [s['hour'] for s in slots if s.get('category') == category]
    if not hours_kst:
        hours_kst = [20]  # fallback: 오후 8시 KST
    hours_utc = [(h - 9) % 24 for h in hours_kst]

    now_utc = datetime.now(timezone.utc)
    best: Optional[datetime] = None

    # 오늘 포함 7일, 모든 (요일 × 시간) 조합에서 가장 가까운 미래 시각 탐색
    for offset in range(8):
        candidate_date = now_utc + timedelta(days=offset)
        if candidate_date.weekday() not in target_days:
            continue
        for h_utc in hours_utc:
            publish_dt = candidate_date.replace(hour=h_utc, minute=0, second=0, microsecond=0)
            if publish_dt <= now_utc:
                continue
            if best is None or publish_dt < best:
                best = publish_dt

    if best is None:
        best = (now_utc + timedelta(days=1)).replace(
            hour=hours_utc[0], minute=0, second=0, microsecond=0)

    return best.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'


def upload_shorts(video_path: str, script_data: dict,
                  youtube_title_prefix: str = '',
                  publish_at: str = None,
                  language: str = 'ko') -> str:
    """YouTube Shorts 업로드 → 영상 ID 반환
    youtube_title_prefix: 유튜브 제목 앞 태그 (예: '[일분 경제] ', '[One Minute Economy] ')
    language: 'ko' → YOUTUBE_TOKEN / 'en' → YOUTUBE_TOKEN_EN
    """
    youtube = _get_youtube_client(language=language)

    raw_title   = script_data['title']
    yt_title    = f"{youtube_title_prefix}{raw_title}"[:100]
    hashtags    = ' '.join([f'#{t}' for t in script_data.get('hashtags', [])])
    description = f"{script_data.get('description', '')}\n\n{hashtags} #Shorts"
    yt_language = 'en' if language == 'en' else 'ko'

    request = youtube.videos().insert(
        part='snippet,status',
        body={
            'snippet': {
                'title':           yt_title,
                'description':     description,
                'tags':            script_data.get('hashtags', []) + ['Shorts'],
                'categoryId':      '17',
                'defaultLanguage': yt_language,
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
