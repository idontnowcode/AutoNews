"""
뉴스 RSS 수집만 실행 (영상 생성 없이)
웹 대시보드 '수집' 버튼 → news_fetch.yml 워크플로우로 실행
"""
import sys
from dotenv import load_dotenv
from src.news_fetcher import fetch_rss_items, save_new_items, get_news_settings

load_dotenv()


def main():
    print('📰 뉴스 RSS 수집 중...')
    settings = get_news_settings()
    max_per_feed = int(settings.get('news_max_per_feed', 5))
    print(f'   피드당 최대 {max_per_feed}건')

    items = fetch_rss_items(max_per_feed=max_per_feed)
    saved = save_new_items(items)
    print(f'   총 {len(items)}건 수집 / {saved}건 신규 저장')


if __name__ == '__main__':
    main()
