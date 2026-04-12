"""
경제 교육 콘텐츠 스크립트 생성 (Claude Sonnet)
"""
import os
import json
import re
import anthropic

client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

PROMPT_TEMPLATE = '''
당신은 경제 교육 YouTube Shorts 채널의 콘텐츠 제작자입니다.
아래 주제로 60초 분량의 교육 영상 스크립트를 만들어주세요.

주제: {title}
난이도: {level}
카테고리: {category}
설명: {description}

[요구사항]
- 대상: 경제를 처음 배우는 20~30대
- 나레이션: 반드시 500자 이내 (60초 기준)
- 구성: 훅(1문장) → 핵심 개념(2~3문장) → 실생활 예시(1~2문장) → 핵심 요약(1문장)
- 슬라이드: 4장 (타이틀 1 + 콘텐츠 3)
- 각 슬라이드에 DALL-E 3 이미지 생성용 영어 프롬프트 포함

[DALL-E 프롬프트 규칙]
- 스타일: "minimalist flat design illustration, dark navy background (#0D1B3E),
  clean infographic style, professional finance visualization, no text"
- 각 슬라이드 내용을 시각적으로 표현하는 개념 이미지

[출력 형식 — 반드시 아래 JSON만 반환]
{{
    "title": "영상 제목 (25자 이내, 숫자나 질문 형식)",
    "subtitle": "한 줄 요약 (40자 이내)",
    "description": "유튜브 설명문 (150자 이내, 핵심 내용 + 다음 편 예고)",
    "hashtags": ["경제", "재테크", "주제관련태그1", "주제관련태그2", "경제교육"],
    "narration": "전체 나레이션 (500자 이내)",
    "slides": [
        {{
            "index": 0,
            "type": "title",
            "heading": "타이틀 슬라이드 제목",
            "subtext": "한 줄 설명",
            "dalle_prompt": "DALL-E 3 image prompt in English"
        }},
        {{
            "index": 1,
            "type": "concept",
            "heading": "핵심 개념 (10자 이내)",
            "key_point": "핵심 한 문장 (20자 이내, 강조 표시됨)",
            "body": "설명 2~3줄",
            "dalle_prompt": "DALL-E 3 image prompt in English"
        }},
        {{
            "index": 2,
            "type": "example",
            "heading": "실생활 예시 (10자 이내)",
            "stat": "핵심 수치나 팩트 (예: 연 5% 금리)",
            "stat_label": "수치 설명",
            "body": "예시 설명 2줄",
            "dalle_prompt": "DALL-E 3 image prompt in English"
        }},
        {{
            "index": 3,
            "type": "summary",
            "heading": "핵심 정리",
            "points": ["요약 포인트 1", "요약 포인트 2", "요약 포인트 3"],
            "next_topic": "다음 편 예고 (예: 다음 편: 복리의 마법)",
            "dalle_prompt": "DALL-E 3 image prompt in English"
        }}
    ]
}}
'''


def extract_json(raw: str) -> dict:
    raw = re.sub(r'```[a-z]*', '', raw).strip('`').strip()
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        raise ValueError('JSON 블록을 찾을 수 없음')
    return json.loads(match.group())


def generate_script(topic: dict) -> dict:
    msg = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=2048,
        messages=[{
            'role': 'user',
            'content': PROMPT_TEMPLATE.format(
                title=topic.get('title', ''),
                level=topic.get('level', 'basic'),
                category=topic.get('category', ''),
                description=topic.get('description', '')
            )
        }]
    )
    return extract_json(msg.content[0].text.strip())
