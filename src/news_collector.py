import os
import requests
from tavily import TavilyClient


def get_naver_news(query: str, display: int = 5) -> list:
    """Naver 뉴스 검색"""
    url = 'https://openapi.naver.com/v1/search/news.json'
    headers = {
        'X-Naver-Client-Id':     os.environ['NAVER_CLIENT_ID'],
        'X-Naver-Client-Secret': os.environ['NAVER_CLIENT_SECRET'],
    }
    params = {'query': query, 'display': display, 'sort': 'date'}
    resp = requests.get(url, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json().get('items', [])


def enrich_with_tavily(topic: str) -> dict:
    """Tavily로 심화 정보 수집"""
    client = TavilyClient(api_key=os.environ['TAVILY_API_KEY'])
    result = client.search(
        topic,
        search_depth='advanced',
        max_results=3,
        include_answer=True
    )
    return result


def collect_news() -> dict:
    """오늘의 핫이슈 수집 (메인 진입 함수)"""
    keywords = ['오늘 주요 뉴스', '최신 과학 기술', '경제 이슈']
    articles = []
    for kw in keywords:
        items = get_naver_news(kw, display=3)
        articles.extend(items)

    # 첫 번째 기사를 대표 주제로 선택해 심화 검색
    if articles:
        top_title = articles[0].get('title', '').replace('<b>', '').replace('</b>', '')
        detail = enrich_with_tavily(top_title)
    else:
        detail = {}

    return {'articles': articles[:5], 'detail': detail}
