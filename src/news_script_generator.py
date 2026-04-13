"""
뉴스 기사 → YouTube Shorts 스크립트 생성 (Claude Sonnet)
커리큘럼용 script_generator.py와 별도 — 뉴스 요약 특화
"""
import os
import json
import re
import anthropic
from src.script_generator import fix_title_grammar

client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

NEWS_PROMPT = '''
당신은 경제 뉴스 YouTube Shorts 채널의 콘텐츠 제작자입니다.
아래 뉴스 기사를 60초 Shorts 영상 스크립트로 만들어주세요.

뉴스 제목: {title}
뉴스 출처: {source}
기사 요약: {summary}

[요구사항]
- 대상: 경제에 관심 있는 20~40대 직장인
- 세그먼트 수: 6~8개
- ★ 각 세그먼트 나레이션은 반드시 20~40자 이내 ★
- 뉴스 내용을 이해하기 쉽게 요약 (전문용어 최소화)
- 세그먼트 구성:
    0: 헤드라인 한 줄 요약 (시청자 관심 유발)
    1: 무슨 일이 일어났나?
    2~5: 핵심 내용 / 배경 / 숫자/데이터
    마지막: 우리 생활에 미치는 영향 또는 전망

[이미지 프롬프트 규칙 — 영어로만, 뉴스 내용 시각화]
- 반드시 영어로 작성 (한글/한자 절대 금지)
- 뉴스 내용을 직관적으로 보여주는 교육용 카툰 장면
- 캐릭터, 차트, 화살표, 건물, 아이콘 등 활용
- 첫 세그먼트: 뉴스 핵심 오브젝트 + 놀란 캐릭터
- 마지막 세그먼트: 영향 받는 사람들 또는 미래 전망 이미지

[출력 형식 — 반드시 아래 JSON만 반환]
{{
    "title": "뉴스 핵심을 담은 제목 (예: '금리 인상'이란? 형식 아니어도 됨, 30자 이내)",
    "description": "유튜브 설명문 (150자 이내) — 시간 표현 금지",
    "hashtags": ["경제뉴스", "경제", "재테크", "뉴스요약", "주제태그"],
    "segments": [
        {{
            "index": 0,
            "narration": "★ 20~40자 한 문장 ★",
            "image_prompt": "[영어로 된 카툰 이미지 프롬프트]"
        }}
    ]
}}
'''


def generate_news_script(news_item: dict) -> dict:
    msg = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=2048,
        messages=[{
            'role': 'user',
            'content': NEWS_PROMPT.format(
                title=news_item.get('title', ''),
                source=news_item.get('source', ''),
                summary=news_item.get('summary', news_item.get('title', ''))
            )
        }]
    )
    raw = msg.content[0].text.strip()
    raw = re.sub(r'```[a-z]*', '', raw).strip('`').strip()
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        raise ValueError('JSON 블록을 찾을 수 없음')
    result = json.loads(match.group())

    # 제목 후처리 (이란/란 문법 교정 — 해당하는 경우)
    if 'title' in result and ('이란?' in result['title'] or '란?' in result['title']):
        result['title'] = fix_title_grammar(result['title'])
    return result
