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
- 세그먼트 수: 6~8개 (주제 복잡도에 따라 자유롭게)
- ★ 각 세그먼트 나레이션은 반드시 20~40자 이내 ★
  → 나레이션 하나가 짧은 한 문장이 되도록 핵심만 압축
  → 긴 설명은 여러 세그먼트로 나눔
- 세그먼트 구성 예시 (8개 기준):
    0: 호기심 유발 한 문장
    1: 개념 한 줄 정의
    2: 작동 원리 장면 1
    3: 작동 원리 장면 2
    4: 실생활 예시
    5: 구체적 수치
    6: 핵심 요약
    7: 마무리 한 마디
- 각 세그먼트 나레이션은 TTS로 읽히는 동안 해당 이미지와 자막이 함께 표시됨

[이미지 프롬프트 작성 규칙 — gpt-image-1 카툰 교육 스타일]
- 반드시 영어로만 작성 (한글/한자/일본어 절대 사용 금지)
- 해당 세그먼트 나레이션 내용을 시각적으로 설명하는 교육용 카툰 장면 묘사 (영어)
- 귀여운 캐릭터, 건물, 화살표, 말풍선 등을 활용한 스토리텔링 구성
- 나레이션 핵심 개념을 장면으로 표현:
  예) "금리가 오르면" → cute character borrowing money from bank, large % sign with red upward arrow
  예) "집을 담보로" → cartoon person holding house as collateral, bank building with money bags
  예) "주식이란" → colorful stock chart with small investor character looking at rising bars
  예) "인플레이션" → shopping cart overflowing, price tags rising, worried cartoon shopper
  예) "중앙은행" → grand bank building center, gears turning, currency flowing outward
- 첫 세그먼트(index 0): 주제 오브젝트 + 궁금해하는 캐릭터 or 물음표
- 마지막 세그먼트: 캐릭터가 이해한 표정 + 체크마크 or 상승 그래프

[출력 형식 — 반드시 아래 JSON만 반환, segments 배열 길이는 6~8]
{{
    "title": "받침 없으면 '란?', 받침 있으면 '이란?' 사용. 예) '금리'란? / '주식'이란? / '인플레이션'이란? / 'GDP'란?",
    "description": "유튜브 설명문 (150자 이내) — 'nn초', 'X분', '1분 만에', '60초 안에' 등 시간 표현 절대 사용 금지",
    "hashtags": ["경제", "경제교육", "재테크", "주제태그1", "주제태그2"],
    "segments": [
        {{
            "index": 0,
            "narration": "★ 20~40자 한 문장 ★",
            "image_prompt": "[나레이션 장면을 영어로 묘사한 카툰 이미지 프롬프트]"
        }}
    ]
}}
'''


def fix_title_grammar(title: str) -> str:
    """'주제명'(이)란? — 받침 유무에 따라 이란/란 자동 교정"""
    m = re.search(r"['\u2018\u2019\u201c\u201d](.+?)['\u2018\u2019\u201c\u201d]", title)
    if not m:
        return title
    topic = m.group(1).strip()
    last  = topic[-1] if topic else ''
    code  = ord(last)
    if 0xAC00 <= code <= 0xD7A3:          # 한글
        jongseong = (code - 0xAC00) % 28
        suffix = '란?' if jongseong == 0 else '이란?'
    else:                                  # 영문/숫자 등
        suffix = '란?' if last.lower() in 'aeiou' else '이란?'
    return f"'{topic}'{suffix}"


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
    result = extract_json(msg.content[0].text.strip())
    if 'title' in result:
        result['title'] = fix_title_grammar(result['title'])
    return result
