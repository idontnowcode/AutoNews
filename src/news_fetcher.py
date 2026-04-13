"""
RSS 피드에서 경제 뉴스 수집 → Supabase news_items 저장
"""
import os
from datetime import datetime, timezone
import feedparser
from src.db_client import get_client

# ── RSS 피드 목록 (무료, 별도 API 키 불필요) ──────────────
RSS_FEEDS = [
    ('연합뉴스 경제',  'https://www.yna.co.kr/rss/economy.xml'),
    ('매일경제',       'https://www.mk.co.kr/rss/40300001/'),
    ('한국경제',       'https://www.hankyung.com/feed/all-news'),
    ('구글뉴스 경제',  'https://news.google.com/rss/search?q=한국+경제+금융&hl=ko&gl=KR&ceid=KR:ko'),
]

MAX_PER_FEED = 5   # 피드당 최대 수집 개수


def fetch_rss_items() -> list[dict]:
    """모든 RSS 피드에서 뉴스 수집"""
    items = []
    for source, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:MAX_PER_FEED]:
                title   = entry.get('title', '').strip()
                link    = entry.get('link', '').strip()
                summary = entry.get('summary', entry.get('description', '')).strip()
                # HTML 태그 간단 제거
                import re
                summary = re.sub(r'<[^>]+>', '', summary)[:500]

                pub = entry.get('published_parsed') or entry.get('updated_parsed')
                published_at = None
                if pub:
                    published_at = datetime(*pub[:6], tzinfo=timezone.utc).isoformat()

                if title and link:
                    items.append({
                        'title':        title,
                        'url':          link,
                        'source':       source,
                        'summary':      summary,
                        'published_at': published_at,
                    })
            print(f'   [{source}] {len(feed.entries[:MAX_PER_FEED])}건 수집')
        except Exception as e:
            print(f'   [{source}] 수집 실패: {e}')
    return items


def save_new_items(items: list[dict]) -> int:
    """중복 제외하고 신규 뉴스만 DB에 저장"""
    db = get_client()
    saved = 0
    for item in items:
        try:
            # URL 기준 중복 체크
            existing = db.table('news_items').select('id').eq('url', item['url']).execute()
            if existing.data:
                continue
            db.table('news_items').insert({
                'title':        item['title'],
                'url':          item['url'],
                'source':       item['source'],
                'summary':      item['summary'],
                'status':       'pending',
                'published_at': item.get('published_at'),
            }).execute()
            saved += 1
        except Exception as e:
            print(f'   저장 실패 ({item["title"][:30]}): {e}')
    return saved


def get_next_news() -> dict | None:
    """다음 처리할 뉴스 아이템 반환 (최신 pending 1건)"""
    db = get_client()
    res = db.table('news_items') \
            .select('*') \
            .eq('status', 'pending') \
            .order('published_at', desc=True) \
            .limit(1) \
            .execute()
    return res.data[0] if res.data else None


def mark_news_in_progress(news_id: str):
    get_client().table('news_items').update({'status': 'in_progress'}).eq('id', news_id).execute()


def mark_news_done(news_id: str, youtube_id: str):
    get_client().table('news_items').update({
        'status': 'done', 'youtube_id': youtube_id
    }).eq('id', news_id).execute()


def mark_news_pending(news_id: str):
    get_client().table('news_items').update({'status': 'pending'}).eq('id', news_id).execute()
