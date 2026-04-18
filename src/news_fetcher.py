"""
RSS 피드에서 뉴스 수집 → Supabase news_items 저장
content_language 설정에 따라 한국어(KO) 또는 해외(EN) 피드 자동 선택
"""
import os
from datetime import datetime, timezone, timedelta
import feedparser
from src.db_client import get_client

# ── 국내 언론사 피드 (content_language='ko') ───────────────
RSS_FEEDS_KO = {
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

# ── 해외 언론사 피드 (content_language='en') ───────────────
RSS_FEEDS_EN = {
    '경제': [
        ('Yahoo Finance',      'https://finance.yahoo.com/news/rssindex'),
        ('CNBC Economy',       'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664'),
        ('Google News Economy','https://news.google.com/rss/search?q=economy+finance+market+stocks&hl=en&gl=US&ceid=US:en'),
        ('Google News Fed',    'https://news.google.com/rss/search?q=Federal+Reserve+interest+rate+inflation&hl=en&gl=US&ceid=US:en'),
    ],
    'IT/테크': [
        ('TechCrunch',         'https://techcrunch.com/feed/'),
        ('The Verge',          'https://www.theverge.com/rss/index.xml'),
        ('Google News AI',     'https://news.google.com/rss/search?q=artificial+intelligence+AI+tech+Apple+Google&hl=en&gl=US&ceid=US:en'),
    ],
    '스포츠': [
        ('BBC Sport',          'https://feeds.bbci.co.uk/sport/rss.xml'),
        ('Google News Sports', 'https://news.google.com/rss/search?q=sports+NFL+NBA+MLB+soccer+transfer&hl=en&gl=US&ceid=US:en'),
    ],
    '정치': [
        ('Politico',           'https://www.politico.com/rss/politicopicks.xml'),
        ('Google News Politics','https://news.google.com/rss/search?q=US+politics+policy+Trump+Congress&hl=en&gl=US&ceid=US:en'),
    ],
    '사회': [
        ('BBC News',           'https://feeds.bbci.co.uk/news/rss.xml'),
        ('NPR News',           'https://feeds.npr.org/1001/rss.xml'),
        ('Google News Society','https://news.google.com/rss/search?q=social+issues+health+climate+society&hl=en&gl=US&ceid=US:en'),
    ],
    '국제': [
        ('BBC World',          'https://feeds.bbci.co.uk/news/world/rss.xml'),
        ('The Guardian World', 'https://www.theguardian.com/world/rss'),
        ('Google News World',  'https://news.google.com/rss/search?q=world+news+international+geopolitics&hl=en&gl=US&ceid=US:en'),
    ],
}

# 하위 호환: 기존 코드가 RSS_FEEDS_BY_CATEGORY를 직접 참조하는 경우 대비
RSS_FEEDS_BY_CATEGORY = RSS_FEEDS_KO

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
                    categories: list[str] | None = None,
                    language: str = 'ko') -> list[dict]:
    """
    RSS 피드에서 뉴스 수집.
    국내(RSS_FEEDS_KO) + 해외(RSS_FEEDS_EN) 피드를 항상 동시에 수집.
    language 파라미터는 스크립트 생성 단계에서만 사용 (수집 시 무시).
    categories=None이면 settings의 news_categories 사용
    """
    if categories is None:
        settings = get_news_settings()
        raw = settings.get('news_categories', '경제')
        categories = [c.strip() for c in raw.split(',') if c.strip()]

    print(f'   🇰🇷 국내 + 🌐 해외 피드 동시 수집')

    feeds = []
    for cat in categories:
        for source, url in RSS_FEEDS_KO.get(cat, []):
            feeds.append((source, url, cat))
        for source, url in RSS_FEEDS_EN.get(cat, []):
            feeds.append((source, url, cat))

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)  # 24시간 이내만 허용

    items = []
    for source, url, cat in feeds:
        try:
            feed = feedparser.parse(url)
            import re
            accepted = 0
            skipped  = 0
            for entry in feed.entries[:max_per_feed * 3]:  # 넉넉히 읽고 날짜 필터 후 max_per_feed 채움
                title   = entry.get('title', '').strip()
                link    = entry.get('link', '').strip()
                summary = entry.get('summary', entry.get('description', '')).strip()
                summary = re.sub(r'<[^>]+>', '', summary)[:500]

                pub = entry.get('published_parsed') or entry.get('updated_parsed')
                published_at = None
                if pub:
                    pub_dt       = datetime(*pub[:6], tzinfo=timezone.utc)
                    published_at = pub_dt.isoformat()
                    # ── 24시간 초과 기사 제외 ──────────────────────
                    if pub_dt < cutoff:
                        skipped += 1
                        continue
                # published_at 없으면 날짜 미상 → 허용

                if title and link:
                    items.append({
                        'title':        title,
                        'url':          link,
                        'source':       source,
                        'summary':      summary,
                        'published_at': published_at,
                        'category':     cat,
                    })
                    accepted += 1
                    if accepted >= max_per_feed:
                        break

            msg = f'   [{source}] {accepted}건 수집'
            if skipped:
                msg += f' ({skipped}건 오래된 기사 제외)'
            print(msg)
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


INTL_CATEGORIES = ('국제', '사회')   # 국제·사회 분야 우선 순위 기준

def auto_queue_top_news() -> bool:
    """
    pending 중 최적 뉴스 1건을 queued로 자동 등록.
    이미 queued 항목이 있으면 스킵 (중복 방지).

    우선순위:
      1. high 관심도 (분야 무관)
      2. medium 관심도 중 국제·사회 분야
      3. medium 관심도 (분야 무관)

    반환: 등록 여부 (True=등록됨, False=스킵)
    """
    db = get_client()

    # 이미 queued 항목이 있으면 추가 등록 불필요
    existing = db.table('news_items').select('id').eq('status', 'queued').limit(1).execute()
    if existing.data:
        print('   ⏭️  이미 대기 큐에 항목 있음 — 자동 큐 등록 스킵')
        return False

    def _query(level: str, categories: tuple | None = None):
        q = (db.table('news_items')
               .select('id,title,category,interest_level,interest_score')
               .eq('status', 'pending')
               .eq('interest_level', level)
               .order('interest_score', desc=True)
               .order('published_at', desc=True)
               .limit(1))
        if categories:
            q = q.in_('category', list(categories))
        return q.execute()

    candidates = [
        ('high',   None),                # 1순위: high 전체
        ('medium', INTL_CATEGORIES),     # 2순위: medium 중 국제·사회
        ('medium', None),                # 3순위: medium 전체
    ]

    for level, cats in candidates:
        res = _query(level, cats)
        if res.data:
            item = res.data[0]
            mark_news_queued(item['id'])
            cat_label = f'[{item["category"]}]' if cats else ''
            print(f'   🤖 자동 큐 등록: [{item["interest_level"]}|{item["interest_score"]}]'
                  f'{cat_label} {item["title"][:45]}')
            return True

    print('   📭 자동 큐 등록할 pending 뉴스 없음')
    return False


def refresh_and_fetch_news(max_per_feed: int = 5, language: str = 'ko') -> int:
    """
    예약 발행 직전 호출:
    기존 pending 뉴스를 모두 삭제하고 RSS에서 최신 뉴스를 새로 수집·저장.
    language에 따라 국내/해외 피드 자동 선택. queued 항목은 보존.
    저장된 건수 반환.
    """
    db = get_client()
    db.table('news_items').delete().eq('status', 'pending').execute()
    print('   🗑️  기존 pending 뉴스 삭제 완료')
    items = fetch_rss_items(max_per_feed=max_per_feed, language=language)
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
