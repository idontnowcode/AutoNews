import os
import json
import re
import anthropic

client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

PROMPT_TEMPLATE = '''
아래 뉴스를 바탕으로 YouTube Shorts 콘텐츠를 만들어 주세요.

뉴스 데이터:
{news_text}

[요구사항]
- 대상: 중학생 (쉬운 단어, 짧은 문장)
- 나레이션: 30~60초 분량, 반드시 600자 이내
- 슬라이드: 4장 (제목 1 + 본문 3)
- 본문 슬라이드 구성:
  * 슬라이드 1, 3: type=card — 카드 2개 (각각 소제목+설명)
  * 슬라이드 2: type=stat — 핵심 숫자 2개 강조

[출력 형식 — 반드시 아래 JSON만 반환]
{{
    "title": "영상 제목 (30자 이내, 숫자·느낌표 포함)",
    "subtitle": "한 줄 요약 (50자 이내)",
    "description": "유튜브 설명문 (100자 이내)",
    "hashtags": ["태그1", "태그2", "태그3"],
    "narration": "전체 나레이션 텍스트",
    "slides": [
        {{
            "type": "card",
            "emoji": "📱",
            "heading": "무슨 일이?",
            "title_big": "슬라이드 큰 제목 (15자 이내)",
            "card1": {{"title": "소제목1 (10자 이내)", "body": "설명 2줄"}},
            "card2": {{"title": "소제목2 (10자 이내)", "body": "설명 2줄"}}
        }},
        {{
            "type": "stat",
            "emoji": "💡",
            "heading": "왜 중요할까?",
            "title_big": "슬라이드 큰 제목 (15자 이내)",
            "stats": [
                {{"number": "43%", "label": "레이블", "desc": "짧은 설명"}},
                {{"number": "0%",  "label": "레이블", "desc": "짧은 설명"}}
            ]
        }},
        {{
            "type": "card",
            "emoji": "🔮",
            "heading": "앞으로는?",
            "title_big": "슬라이드 큰 제목 (15자 이내)",
            "card1": {{"title": "소제목1 (10자 이내)", "body": "설명 2줄"}},
            "card2": {{"title": "소제목2 (10자 이내)", "body": "설명 2줄"}}
        }}
    ]
}}
'''


def extract_json(raw: str) -> dict:
    """Claude 응답에서 JSON 블록 추출"""
    # 코드 블록 제거
    raw = re.sub(r'```[a-z]*', '', raw).strip('`').strip()
    # 첫 번째 { ... } 블록 추출
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        raise ValueError('JSON 블록을 찾을 수 없음')
    return json.loads(match.group())


def generate_script(news_data: dict) -> dict:
    """Claude API로 스크립트 생성"""
    articles = news_data.get('articles', [])
    detail   = news_data.get('detail', {})

    news_text = '\n'.join([
        f"제목: {a.get('title', '').replace('<b>', '').replace('</b>', '')}"
        for a in articles[:3]
    ])
    if detail.get('answer'):
        news_text += f"\n\n심화 정보: {detail['answer']}"

    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=1024,
        messages=[{
            'role': 'user',
            'content': PROMPT_TEMPLATE.format(news_text=news_text)
        }]
    )
    raw = message.content[0].text.strip()
    return extract_json(raw)
