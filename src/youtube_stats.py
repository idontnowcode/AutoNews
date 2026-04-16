"""
YouTube Data API로 업로드된 모든 영상의 통계 수집 → Supabase video_stats upsert
- videos 테이블 (커리큘럼) + news_items 테이블 (뉴스) 의 youtube_id 수집
- videos.list(part='statistics,contentDetails') 배치 호출 (최대 50개/요청)
- video_stats 테이블에 upsert (youtube_id 기준)
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


def fetch_all_video_ids() -> list[dict]:
    """
    Supabase에서 모든 youtube_id 수집.
    반환: [{'youtube_id', 'title', 'video_type', 'category', 'published_at'}, ...]
    """
    db = get_client()
    results = []

    # 커리큘럼 영상
    res = db.table('videos') \
            .select('youtube_id, title, created_at, script_json') \
            .not_.is_('youtube_id', 'null') \
            .execute()
    for r in (res.data or []):
        category = '커리큘럼'
        sj = r.get('script_json') or {}
        if isinstance(sj, str):
            try: sj = json.loads(sj)
            except Exception: sj = {}
        if sj.get('category'):
            category = sj['category']
        results.append({
            'youtube_id':  r['youtube_id'],
            'title':       r.get('title', ''),
            'video_type':  'curriculum',
            'category':    category,
            'published_at': r.get('created_at'),
        })

    # 뉴스 영상
    res = db.table('news_items') \
            .select('youtube_id, title, created_at, category') \
            .not_.is_('youtube_id', 'null') \
            .eq('status', 'done') \
            .execute()
    for r in (res.data or []):
        results.append({
            'youtube_id':  r['youtube_id'],
            'title':       r.get('title', ''),
            'video_type':  'news',
            'category':    r.get('category', '뉴스'),
            'published_at': r.get('created_at'),
        })

    return results


def fetch_stats_from_youtube(video_ids: list[str]) -> dict:
    """
    YouTube API로 통계 조회.
    반환: {youtube_id: {'view_count', 'like_count', 'comment_count', 'duration_sec'}}
    """
    if not video_ids:
        return {}
    youtube = _get_youtube_client()
    stats = {}

    # 50개씩 배치 처리
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        response = youtube.videos().list(
            part='statistics,contentDetails',
            id=','.join(batch)
        ).execute()

        for item in response.get('items', []):
            vid_id = item['id']
            s = item.get('statistics', {})
            d = item.get('contentDetails', {})
            stats[vid_id] = {
                'view_count':    int(s.get('viewCount',    0)),
                'like_count':    int(s.get('likeCount',    0)),
                'comment_count': int(s.get('commentCount', 0)),
                'duration_sec':  _parse_duration(d.get('duration', '')),
            }

    return stats


def save_stats_to_db(video_meta: list[dict], yt_stats: dict) -> int:
    """video_stats 테이블에 upsert. 저장 건수 반환."""
    db = get_client()
    saved = 0
    now = datetime.now(timezone.utc).isoformat()

    for meta in video_meta:
        yid = meta['youtube_id']
        if yid not in yt_stats:
            continue
        s = yt_stats[yid]
        try:
            db.table('video_stats').upsert({
                'youtube_id':    yid,
                'title':         meta.get('title', ''),
                'video_type':    meta.get('video_type', 'curriculum'),
                'category':      meta.get('category', ''),
                'view_count':    s['view_count'],
                'like_count':    s['like_count'],
                'comment_count': s['comment_count'],
                'duration_sec':  s['duration_sec'],
                'published_at':  meta.get('published_at'),
                'fetched_at':    now,
            }, on_conflict='youtube_id').execute()
            saved += 1
        except Exception as e:
            print(f'   저장 실패 ({yid}): {e}')

    return saved


def collect_all_stats() -> list[dict]:
    """
    전체 파이프라인: DB에서 ID 수집 → YouTube API 조회 → DB upsert.
    반환: 저장된 통계 레코드 리스트 (분석용)
    """
    print('📊 영상 통계 수집 시작...')

    video_meta = fetch_all_video_ids()
    print(f'   대상 영상: {len(video_meta)}개 (커리큘럼 {sum(1 for v in video_meta if v["video_type"]=="curriculum")}개 / '
          f'뉴스 {sum(1 for v in video_meta if v["video_type"]=="news")}개)')

    if not video_meta:
        print('   수집할 영상 없음')
        return []

    yt_ids = [v['youtube_id'] for v in video_meta]
    yt_stats = fetch_stats_from_youtube(yt_ids)
    print(f'   YouTube API 응답: {len(yt_stats)}개')

    saved = save_stats_to_db(video_meta, yt_stats)
    print(f'   DB 저장 완료: {saved}개')

    # 분석용 merged 레코드 반환
    merged = []
    for meta in video_meta:
        yid = meta['youtube_id']
        if yid in yt_stats:
            merged.append({**meta, **yt_stats[yid]})
    return merged
