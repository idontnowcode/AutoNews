"""
뉴스 RSS 수집만 실행 (영상 생성 없이)
웹 대시보드 '수집' 버튼 / 3시간 cron → news_fetch.yml 워크플로우로 실행

실행 순서:
  1. pending 삭제 후 최신 RSS 수집 (queued 보존)
  2. high/medium 관심도 뉴스 1건 자동 큐 등록 (queued 없을 때만)
  3. 오래된 done/failed 항목 정리 (news_delete_days 설정 기준)
"""
import sys
from dotenv import load_dotenv
from src.news_fetcher import (fetch_rss_items, save_new_items, get_news_settings,
                               auto_queue_top_news, delete_old_news)

load_dotenv()


def main():
    print('📰 뉴스 RSS 수집 중...')
    settings = get_news_settings()
    max_per_feed = int(settings.get('news_max_per_feed', 5))
    language     = settings.get('content_language', 'ko').strip().lower()
    if language not in ('ko', 'en'):
        language = 'ko'
    delete_days  = int(settings.get('news_delete_days', 3))  # 기본 3일

    # ── 1. pending 삭제 후 신규 수집 (queued 보존) ────────────
    from src.db_client import get_client
    db = get_client()
    db.table('news_items').delete().eq('status', 'pending').execute()
    print('🗑️  기존 pending 뉴스 삭제 완료')

    print(f'   피드당 최대 {max_per_feed}건 | 언어: {language.upper()}')
    items = fetch_rss_items(max_per_feed=max_per_feed, language=language)
    saved = save_new_items(items)
    print(f'   총 {len(items)}건 수집 / {saved}건 신규 저장')

    # ── 2. 자동 큐 등록 (high → medium 최고점 1건) ────────────
    print('🤖 자동 큐 등록 체크...')
    auto_queue_top_news()

    # ── 3. 오래된 done/failed 정리 ────────────────────────────
    if delete_days > 0:
        deleted = delete_old_news(delete_days)
        if deleted:
            print(f'🗑️  {delete_days}일 이상 된 완료/실패 뉴스 {deleted}건 삭제')


if __name__ == '__main__':
    main()
