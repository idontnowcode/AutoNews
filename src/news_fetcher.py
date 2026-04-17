"""
RSS 피드에서 경제 뉴스 수집 → Supabase news_items 저장
"""
import os
from datetime import datetime, timezone, timedelta
import feedparser
from src.db_client import get_client

# ── RSS 피드 목록 (분야별) ────────────────────────────────
RSS_FEEDS_BY_CATEGORY = {
    '경제': [
        ('연합뉴스 경제',  'https://www.yna.co.kr/rss/economy.xml'),
        ('매일경제',       'https://www.mk.co.kr/rss/40300001/'),
        ('한국경제',       'https://www.hankyung.com/feed/all-news'),
        ('구글뉴스 경제',  'https://news.google.com/rss/search?q=한국+경제+금융&hl=ko&gl=KR&ceid=KR:ko'),
    ],
    '스포츠': [
        ('연합뉴스 스포츠', 'https://www.yna.co.kr/rss/sports.xml'),
        ('스포츠조선',      'https://news.google.com/rss/search?q=스포츠+한국&hl=ko&gl=KR&ceid=KR:ko'),
        ('구글뉴스 스포츠', 'https://news.google.com/rss/search?q=야구+축구+농구+한국&hl=ko&gl=KR&ceid=KR:ko'),
    ],
    'IT/테크': [
        ('연합뉴스 IT',    'https://www.yna.co.kr/rss/it.xml'),
        ('구글뉴스 IT',    'https://news.google.com/rss/search?q=인공지능+테크+IT+한국&hl=ko&gl=KR&ceid=KR:ko'),
        ('ZDNet Korea',    'https://www.zdnet.co.kr/rss/rss.xml'),
    ],
    '정치': [
        ('연합뉴스 정치',  'https://www.yna.co.kr/rss/politics.xml'),
        ('구글뉴스 정치',  'https://news.google.com/rss/search?q=한국+정치+국회&hl=ko&gl=KR&ceid=KR:ko'),
    ],
    '사회': [
        ('연합뉴스 사회',  'https://www.yna.co.kr/rss/society.xml'),
        ('구글뉴스 사회',  'https://news.google.com/rss/search?q=한국+사회+생활&hl=ko&gl=KR&ceid=KR:ko'),
    ],
    '국제': [
        ('연합뉴스 국제',  'https://www.yna.co.kr/rss/international.xml'),
        ('구글뉴스 국제',  'https://news.google.com/rss/search?q=국제뉴스+세계&hl=ko&gl=KR&ceid=KR:ko'),
    ],
}

DEFAULT_MAX_PER_FEED = 5


def get_news_settings() -> dict:
    """news 관련 설정값 반환"""
    try:
        db = get_client()
        res = db.table('settings').select('key,value').execute()
        return {r['key']: r['value'] for r in (res.data or [])}
    except Exception:
        return {}


def fetch_rss_items(max_per_feed: int = DEFAULT_MAX_PER_FEED,
                    categories: list[str] | None = None) -> list[dict]:
    """RSS 피드에서 뉴스 수집. categories=None이면 설정된 분야만 수집"""
    if categories is None:
        # settings에서 활성화된 분야 읽기
        settings = get_news_settings()
        raw = settings.get('news_categories', '경제')
        categories = [c.strip() for c in raw.split(',') if c.strip()]

    feeds = []
    for cat in categories:
        for source, url in RSS_FEEDS_BY_CATEGORY.get(cat, []):
            feeds.append((source, url, cat))

    items = []
    for source, url, cat in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
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
                        'category':     cat,
                    })
            print(f'   [{source}] {len(feed.entries[:max_per_feed])}건 수집')
        except Exception as e:
            print(f'   [{source}] 수집 실패: {e}')
    return items


def _jaccard_title(a: str, b: str) -> float:
    """두 제목의 Jaccard 유사도 (2글자 이상 단어 기준)"""
    import re
    tokenize = lambda s: set(w for w in re.split(r'[\s\-·|,]+', s) if len(w) >= 2)
    sa, sb = tokenize(a), tokenize(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def save_new_items(items: list[dict]) -> int:
    """중복 제외하고 신규 뉴스만 DB에 저장 (관심도 채점 포함)"""
    from src.news_scorer import score_items, print_score_summary

    # 관심도 채점 (저장 전 일괄 처리)
    scored = score_items(items)
    print_score_summary(scored)

    # 낮음 관심도 제외 설정 확인
    settings = get_news_settings()
    skip_low = settings.get('news_skip_low', 'false').lower() == 'true'
    if skip_low:
        before = len(scored)
        scored = [it for it in scored if it.get('interest_level') != 'low']
        print(f'   🔽 낮음 관심도 제외: {before - len(scored)}건 스킵 → {len(scored)}건 저장 대상')

    db = get_client()

    # 최근 48시간 내 DB 제목 로드 (제목 유사도 중복 체크용)
    cutoff_48h = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    existing_titles_res = db.table('news_items').select('title') \
        .gte('created_at', cutoff_48h).execute()
    known_titles: list[str] = [r['title'] for r in (existing_titles_res.data or [])]

    saved = 0
    dup_skipped = 0
    for item in scored:
        try:
            # 1) URL 중복 체크
            if db.table('news_items').select('id').eq('url', item['url']).execute().data:
                continue

            # 2) 제목 유사도 중복 체크 (Jaccard >= 0.40)
            is_title_dup = any(
                _jaccard_title(item['title'], t) >= 0.40 for t in known_titles
            )
            if is_title_dup:
                dup_skipped += 1
                continue

            db.table('news_items').insert({
                'title':           item['title'],
                'url':             item['url'],
                'source':          item['source'],
                'summary':         item['summary'],
                'status':          'pending',
                'published_at':    item.get('published_at'),
                'category':        item.get('category', '경제'),
                'interest_score':  item.get('interest_score', 0),
                'interest_level':  item.get('interest_level', 'medium'),
            }).execute()
            known_titles.append(item['title'])  # 같은 배치 내 중복도 방지
            saved += 1
        except Exception as e:
            print(f'   저장 실패 ({item["title"][:30]}): {e}')
    if dup_skipped:
        print(f'   🔁 유사 제목 중복 {dup_skipped}건 스킵')
    return saved


def get_news_by_id(news_id: str) -> dict | None:
    """ID로 특정 뉴스 항목 반환 (status 무관)"""
    res = get_client().table('news_items').select('*').eq('id', news_id).limit(1).execute()
    return res.data[0] if res.data else None


def get_next_news() -> dict | None:
    """queued 우선, 없으면 pending (interest_score DESC → published_at DESC)"""
    db = get_client()
    # 1순위: 사용자가 대기열에 추가한 뉴스 (FIFO)
    res = db.table('news_items') \
            .select('*') \
            .eq('status', 'queued') \
            .order('created_at') \
            .limit(1) \
            .execute()
    if res.data:
        print(f'   📋 대기 큐에서 선택: {res.data[0]["title"][:40]}')
        return res.data[0]
    # 2순위: 자동 선택 (관심도 높은 순)
    res = db.table('news_items') \
            .select('*') \
            .eq('status', 'pending') \
            .order('interest_score', desc=True) \
            .order('published_at', desc=True) \
            .limit(1) \
            .execute()
    return res.data[0] if res.data else None


def get_next_high_interest_news() -> dict | None:
    """
    예약 발행 모드용: queued 우선 → high → medium → 전체 순으로 뉴스 1건 반환.
    """
    db = get_client()
    # 0순위: 사용자 대기 큐 (FIFO)
    res = db.table('news_items') \
            .select('*') \
            .eq('status', 'queued') \
            .order('created_at') \
            .limit(1) \
            .execute()
    if res.data:
        print(f'   📋 대기 큐에서 선택: {res.data[0]["title"][:40]}')
        return res.data[0]
    # 1~3순위: pending 중 관심도 순
    for level in ('high', 'medium', None):
        q = (db.table('news_items')
               .select('*')
               .eq('status', 'pending')
               .order('interest_score', desc=True)
               .order('published_at', desc=True)
               .limit(1))
        if level:
            q = q.eq('interest_level', level)
        res = q.execute()
        if res.data:
            chosen_level = res.data[0].get('interest_level', '?')
            print(f'   🎯 관심도 {chosen_level} 뉴스 선택: {res.data[0]["title"][:40]}')
            return res.data[0]
    return None


def refresh_and_fetch_news(max_per_feed: int = 5) -> int:
    """
    예약 발행 직전 호출:
    기존 pending 뉴스를 모두 삭제하고 RSS에서 최신 뉴스를 새로 수집·저장.
    저장된 건수 반환.
    """
    db = get_client()
    db.table('news_items').delete().eq('status', 'pending').execute()
    print('   🗑️  기존 pending 뉴스 삭제 완료')
    items = fetch_rss_items(max_per_feed=max_per_feed)
    saved = save_new_items(items)
    print(f'   📰 최신 뉴스 {len(items)}건 수집 / {saved}건 저장')
    return saved


def mark_news_in_progress(news_id: str):
    get_client().table('news_items').update({'status': 'in_progress'}).eq('id', news_id).execute()


def mark_news_done(news_id: str, youtube_id: str):
    get_client().table('news_items').update({
        'status': 'done', 'youtube_id': youtube_id
    }).eq('id', news_id).execute()


def mark_news_pending(news_id: str):
    get_client().table('news_items').update({'status': 'pending'}).eq('id', news_id).execute()


def mark_news_queued(news_id: str):
    get_client().table('news_items').update({'status': 'queued'}).eq('id', news_id).execute()


def mark_news_failed(news_id: str):
    get_client().table('news_items').update({'status': 'failed'}).eq('id', news_id).execute()


def delete_old_news(days: int) -> int:
    """n일 이상 지난 뉴스 삭제 (done/failed 상태만), 삭제 건수 반환"""
    if days <= 0:
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    db = get_client()
    res = db.table('news_items') \
            .delete() \
            .in_('status', ['done', 'failed']) \
            .lt('created_at', cutoff) \
            .execute()
    return len(res.data) if res.data else 0
