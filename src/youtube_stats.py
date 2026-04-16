"""
YouTube 채널의 업로드 플레이리스트에서 모든 영상을 직접 가져와 통계 수집.
Supabase DB는 video_type/category 보강용으로만 사용.

흐름:
  1. channels.list(mine=True) → uploads 플레이리스트 ID
  2. playlistItems.list(페이지네이션) → 전체 영상 ID 목록
  3. videos.list(part=statistics,contentDetails,snippet) → 실제 통계
  4. Supabase videos/news_items 로 video_type/category 보강
  5. video_stats 테이블 upsert
"""
import os
import json
import re
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from src.db_client import get_client


def _get_youtube_client():
    token_json = os.environ['YOUTUBE_TOKEN']
    creds = Credentials.from_authorized_user_info(json.loads(token_json))
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise RuntimeError('YouTube OAuth 토큰이 유효하지 않습니다.')
    return build('youtube', 'v3', credentials=creds)


def _parse_duration(iso: str) -> int:
    """ISO 8601 duration (PT1M30S) → 초"""
    if not iso:
        return 0
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso)
    if not m:
        return 0
    h, mi, s = (int(m.group(i) or 0) for i in (1, 2, 3))
    return h * 3600 + mi * 60 + s


def _get_uploads_playlist_id(youtube) -> str:
    """내 채널의 uploads 플레이리스트 ID 반환"""
    res = youtube.channels().list(
        part='contentDetails',
        mine=True
    ).execute()
    items = res.get('items', [])
    if not items:
        raise RuntimeError('채널 정보를 가져올 수 없습니다.')
    return items[0]['contentDetails']['relatedPlaylists']['uploads']


def _fetch_all_playlist_items(youtube, playlist_id: str) -> list[str]:
    """플레이리스트의 모든 영상 ID 페이지네이션 수집"""
    video_ids = []
    next_page = None

    while True:
        kwargs = dict(
            part='contentDetails',
            playlistId=playlist_id,
            maxResults=50,
        )
        if next_page:
            kwargs['pageToken'] = next_page

        res = youtube.playlistItems().list(**kwargs).execute()
        for item in res.get('items', []):
            vid_id = item['contentDetails'].get('videoId')
            if vid_id:
                video_ids.append(vid_id)

        next_page = res.get('nextPageToken')
        if not next_page:
            break

    return video_ids


def _fetch_video_details(youtube, video_ids: list[str]) -> dict:
    """
    videos.list로 통계 + snippet 수집.
    반환: {
      youtube_id: {
        'title', 'published_at',
        'view_count', 'like_count', 'comment_count', 'duration_sec'
      }
    }
    """
    details = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        res = youtube.videos().list(
            part='statistics,contentDetails,snippet',
            id=','.join(batch)
        ).execute()

        for item in res.get('items', []):
            vid_id  = item['id']
            snippet = item.get('snippet', {})
            s       = item.get('statistics', {})
            d       = item.get('contentDetails', {})

            details[vid_id] = {
                'title':         snippet.get('title', ''),
                'published_at':  snippet.get('publishedAt'),
                'view_count':    int(s.get('viewCount',    0)),
                'like_count':    int(s.get('likeCount',    0)),
                'comment_count': int(s.get('commentCount', 0)),
                'duration_sec':  _parse_duration(d.get('duration', '')),
            }

    return details


def _build_db_meta_map() -> dict:
    """
    Supabase에서 youtube_id → {video_type, category} 매핑 구성.
    채널에는 있지만 DB에 없는 영상은 'unknown'으로 처리.
    """
    db = get_client()
    meta = {}

    # 커리큘럼
    res = db.table('videos') \
            .select('youtube_id, script_json') \
            .not_.is_('youtube_id', 'null') \
            .execute()
    for r in (res.data or []):
        yid = r.get('youtube_id')
        if not yid:
            continue
        sj = r.get('script_json') or {}
        if isinstance(sj, str):
            try: sj = json.loads(sj)
            except Exception: sj = {}
        meta[yid] = {
            'video_type': 'curriculum',
            'category':   sj.get('category', '커리큘럼'),
        }

    # 뉴스
    res = db.table('news_items') \
            .select('youtube_id, category') \
            .not_.is_('youtube_id', 'null') \
            .eq('status', 'done') \
            .execute()
    for r in (res.data or []):
        yid = r.get('youtube_id')
        if not yid:
            continue
        meta[yid] = {
            'video_type': 'news',
            'category':   r.get('category', '뉴스'),
        }

    return meta


def save_stats_to_db(records: list[dict]) -> int:
    """video_stats 테이블에 upsert. 저장 건수 반환."""
    db = get_client()
    saved = 0
    now = datetime.now(timezone.utc).isoformat()

    for r in records:
        try:
            db.table('video_stats').upsert({
                'youtube_id':    r['youtube_id'],
                'title':         r.get('title', ''),
                'video_type':    r.get('video_type', 'unknown'),
                'category':      r.get('category', ''),
                'view_count':    r.get('view_count', 0),
                'like_count':    r.get('like_count', 0),
                'comment_count': r.get('comment_count', 0),
                'duration_sec':  r.get('duration_sec', 0),
                'published_at':  r.get('published_at'),
                'fetched_at':    now,
            }, on_conflict='youtube_id').execute()
            saved += 1
        except Exception as e:
            print(f'   저장 실패 ({r.get("youtube_id")}): {e}')

    return saved


def collect_all_stats() -> list[dict]:
    """
    전체 파이프라인:
      채널 uploads 플레이리스트 → 전체 영상 ID
      → YouTube API 통계/스니펫 수집
      → Supabase 메타 보강
      → video_stats upsert
    반환: 분석용 레코드 리스트
    """
    print('📊 영상 통계 수집 시작...')
    youtube = _get_youtube_client()

    # 1. 채널 전체 영상 ID 수집
    playlist_id = _get_uploads_playlist_id(youtube)
    print(f'   업로드 플레이리스트: {playlist_id}')

    video_ids = _fetch_all_playlist_items(youtube, playlist_id)
    print(f'   채널 전체 영상: {len(video_ids)}개')

    if not video_ids:
        print('   수집할 영상 없음')
        return []

    # 2. 영상별 통계 + 제목/게시일 수집
    details = _fetch_video_details(youtube, video_ids)
    print(f'   YouTube API 통계 응답: {len(details)}개')

    # 3. Supabase 메타 보강 (video_type, category)
    db_meta = _build_db_meta_map()
    db_matched = sum(1 for yid in details if yid in db_meta)
    print(f'   DB 매칭: {db_matched}개 / 미매칭: {len(details) - db_matched}개 (채널 직접 업로드)')

    # 4. 레코드 병합 (DB 미매칭 영상은 제목 패턴으로 자동 분류)
    records = []
    for yid, det in details.items():
        if yid in db_meta:
            meta = db_meta[yid]
        else:
            title = det.get('title', '')
            if '[일분 뉴스]' in title or '뉴스' in title:
                meta = {'video_type': 'news', 'category': '뉴스'}
            elif '[일분 경제]' in title or '경제' in title:
                meta = {'video_type': 'curriculum', 'category': '커리큘럼'}
            else:
                meta = {'video_type': 'unknown', 'category': '기타'}
        records.append({
            'youtube_id': yid,
            **det,
            **meta,
        })

    # 5. DB upsert
    saved = save_stats_to_db(records)
    print(f'   DB 저장 완료: {saved}개')

    return records
