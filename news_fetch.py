"""
뉴스 RSS 수집만 실행 (영상 생성 없이)
웹 대시보드 '수집' 버튼 → news_fetch.yml 워크플로우로 실행
content_language 설정에 따라 국내/해외 피드 자동 선택
"""
import sys
from dotenv import load_dotenv
from src.news_fetcher import fetch_rss_items, save_new_items, get_news_settings

load_dotenv()


def main():
    print('📰 뉴스 RSS 수집 중...')
    settings = get_news_settings()
    max_per_feed = int(settings.get('news_max_per_feed', 5))
    language     = settings.get('content_language', 'ko').strip().lower()
    if language not in ('ko', 'en'):
        language = 'ko'

    # pending 항목만 삭제 후 신규 수집 (queued 보존)
    from src.db_client import get_client
    db = get_client()
    db.table('news_items').delete().eq('status', 'pending').execute()
    print('🗑️ 기존 pending 뉴스 삭제 완료')

    print(f'   피드당 최대 {max_per_feed}건 | 언어: {language.upper()}')
    items = fetch_rss_items(max_per_feed=max_per_feed, language=language)
    saved = save_new_items(items)
    print(f'   총 {len(items)}건 수집 / {saved}건 신규 저장')


if __name__ == '__main__':
    main()
