"""
경제 교육 콘텐츠 스크립트 생성 (Claude Sonnet)
각 슬라이드에 개별 나레이션 포함 → TTS + 이미지 동기화
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
- 전체 나레이션: 500자 이내 (60초 기준)
- 슬라이드 4장, 각 슬라이드마다 개별 나레이션 포함
- 슬라이드 구성: 도입 → 핵심개념 → 예시/수치 → 정리
- 각 슬라이드 나레이션은 해당 이미지와 함께 표시됨 (TTS 읽는 동안 이미지 유지)

[DALL-E 프롬프트 작성 규칙]
- 해당 세그먼트 나레이션 내용과 직접 연관된 장면 묘사 (영어)
- 아래 고정 스타일을 반드시 끝에 추가:
  "flat design illustration, pure black background (#000000), vibrant colorful objects, clean and simple, no text, no letters, no numbers"
- 나레이션의 핵심 단어를 시각적 오브젝트로 치환
  예) "금리가 오르면" → upward arrow with percentage sign and stacked coins
  예) "집을 담보로" → house with chain and padlock attached to money bag
  예) "주식이란" → colorful rising bar chart with dollar signs floating up
  예) "인플레이션" → shopping cart overflowing with price tag showing rising arrow
  예) "중앙은행" → large bank building with gear mechanism
- 오브젝트 2~4개로 구성, 동작/상태 묘사 포함 (rising, falling, connected, locked 등)
- 세그먼트 0 (도입): 중앙 오브젝트 + question mark
- 세그먼트 3 (정리): 오브젝트 + checkmark or upward trend

[출력 형식 — 반드시 아래 JSON만 반환]
{{
    "title": "영상 제목 (20자 이내, 따옴표로 감싸기: '주제명' 이란?)",
    "description": "유튜브 설명문 (150자 이내)",
    "hashtags": ["경제", "경제교육", "재테크", "주제태그1", "주제태그2"],
    "segments": [
        {{
            "index": 0,
            "narration": "도입 나레이션 (30~50자, 시청자 호기심 유발)",
            "dalle_prompt": "flat design illustration of [나레이션 핵심 장면 영어 묘사], pure black background, vibrant colors, no text"
        }},
        {{
            "index": 1,
            "narration": "핵심 개념 설명 (60~100자)",
            "dalle_prompt": "flat design illustration of [나레이션 핵심 장면 영어 묘사], pure black background, vibrant colors, no text"
        }},
        {{
            "index": 2,
            "narration": "실생활 예시나 수치 (60~100자)",
            "dalle_prompt": "flat design illustration of [나레이션 핵심 장면 영어 묘사], pure black background, vibrant colors, no text"
        }},
        {{
            "index": 3,
            "narration": "핵심 정리 + 다음 편 예고 (40~60자)",
            "dalle_prompt": "flat design illustration of [나레이션 핵심 장면 영어 묘사], pure black background, vibrant colors, no text"
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
