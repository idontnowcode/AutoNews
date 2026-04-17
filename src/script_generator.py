"""
경제 교육 콘텐츠 스크립트 생성 (Claude Sonnet)
각 슬라이드에 개별 나레이션 포함 → TTS + 이미지 동기화
"""
import os
import json
import re
import anthropic

_client = None

def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
    return _client

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
- ★ 말투: 친구에게 설명하듯 자연스러운 구어체 ★
  좋은 예시: 쉽게 말하면요 / 이게 왜 중요하냐면요 / 생각해보면 당연한 거예요
  나쁜 예시: 의미합니다 / 나타납니다 / ~입니다 (딱딱한 교과서체 금지)
  → ~거든요, ~는데요, ~인 거예요, ~해요 등 자연스러운 구어 표현 사용
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
    "title": "아래 3가지 형식 중 주제에 맞는 것 선택 (단순 '란?/이란?' 형식 지양):\n  A) 뉴스 연동형: '코스피 6000 돌파! 그래서 금리가 뭔데?' — 최근 이슈와 연결\n  B) 공감/숫자형: '월급 300만원인데 통장이 텅텅? 원인 30초 정리' — 숫자+공감\n  C) 질문형: '금리란? 30초면 이해됨' — 명확한 질문+시간 암시\n  — 반드시 숫자 또는 감탄/의문 표현 포함, 20자 이내",
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


def _repair_json_string(s: str) -> str:
    """JSON 문자열 값 안의 이스케이프 안 된 큰따옴표를 단순 제거하는 최후 수단"""
    # "narration": "텍스트 안에 "따옴표" 포함" 같은 패턴을 찾아 내부 따옴표를 제거
    def fix_value(m):
        inner = m.group(1)
        # 값 내부의 따옴표를 단순 제거 (의미 손상 최소화)
        inner = inner.replace('"', '')
        return f'"{inner}"'
    # JSON 문자열 값 패턴: ": "..." — 간단한 휴리스틱
    return re.sub(r'": "([^"]*(?:"[^",:}\]]*){1,}[^"]*)"', fix_value, s)


def extract_json(raw: str) -> dict:
    raw = re.sub(r'```[a-z]*', '', raw).strip('`').strip()
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        raise ValueError('JSON 블록을 찾을 수 없음')
    json_str = match.group()
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f'   ⚠️  JSON 파싱 오류: {e} — 복구 시도 중...')
        print(f'   원본 (처음 200자): {json_str[:200]}')
        repaired = _repair_json_string(json_str)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            raise ValueError(f'JSON 복구 실패: {e}') from e


# ── 구독/좋아요 유도 아웃트로 ─────────────────────────────────────

import os as _os

# 고정 멘트 (사운드/이미지 모두 한 번만 생성 후 재사용)
OUTRO_NARRATION    = "구독이랑 좋아요 눌러주시면 더 열심히 만들게요!"
OUTRO_NARRATION_EN = "Like and subscribe for more!"

OUTRO_IMAGE_PROMPT = (
    "Cute cartoon character smiling and waving at the camera, "
    "holding a large red subscribe button in one hand and a blue thumbs-up like button "
    "in the other hand, bright cheerful colors, simple flat design, YouTube Shorts style"
)

# 프로젝트 루트 기준 고정 asset 경로
_ASSET_DIR      = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'assets')
OUTRO_IMAGE     = _os.path.join(_ASSET_DIR, 'outro_image.png')
OUTRO_AUDIO     = _os.path.join(_ASSET_DIR, 'outro_audio.mp3')
OUTRO_AUDIO_EN  = _os.path.join(_ASSET_DIR, 'outro_audio_en.mp3')


def append_outro(segments: list, language: str = 'ko') -> list:
    """마지막 세그먼트 뒤에 구독/좋아요 유도 멘트 추가.
    assets/outro_image.png · outro_audio[_en].mp3 가 존재하면 직접 주입.
    """
    idx = max((s.get('index', i) for i, s in enumerate(segments)), default=-1) + 1
    narration  = OUTRO_NARRATION_EN if language == 'en' else OUTRO_NARRATION
    audio_file = OUTRO_AUDIO_EN     if language == 'en' else OUTRO_AUDIO
    seg: dict = {
        'index':        idx,
        'narration':    narration,
        'image_prompt': OUTRO_IMAGE_PROMPT,
    }
    if _os.path.exists(OUTRO_IMAGE):
        seg['image_path'] = OUTRO_IMAGE
    if _os.path.exists(audio_file):
        seg['audio_path'] = audio_file
    segments.append(seg)
    img_ok = "OK" if _os.path.exists(OUTRO_IMAGE) else "MISSING"
    aud_ok = "OK" if _os.path.exists(audio_file)  else "MISSING"
    print(f'   [아웃트로] idx={idx} | lang={language} | image={img_ok} | audio={aud_ok}')
    return segments


# ── 영어 프롬프트 ─────────────────────────────────────
PROMPT_TEMPLATE_EN = '''
You are a content creator for an English economics education YouTube Shorts channel.
Create a 60-second educational video script on the topic below.

Topic: {title}
Level: {level}
Category: {category}
Description: {description}

[Requirements]
- Target audience: 20-30s learning economics for the first time
- Number of segments: 6-8 (based on topic complexity)
- ★ Each segment narration MUST be 10-20 words ★
  → One short punchy sentence, core point only
  → Split complex ideas across multiple segments
- ★ Tone: conversational, friendly, like explaining to a friend ★
  Good: "Here's the thing..." / "Think of it this way..." / "So basically..."
  Bad: "It represents..." / "It indicates..." (no textbook language)
  → Use contractions (it's, you'll, they're) and casual phrasing
- Segment structure (8 segments):
    0: Hook — curiosity-sparking opener
    1: One-line concept definition
    2: How it works — part 1
    3: How it works — part 2
    4: Real-life everyday example
    5: Key number or stat
    6: Core takeaway
    7: Punchy sign-off

[Image prompt rules — gpt-image-1 cartoon education style]
- Write in English only
- Describe a cartoon scene visually explaining the narration
- Use cute characters, charts, arrows, speech bubbles
- First segment (index 0): topic object + curious character or question mark
- Last segment: "aha!" expression + checkmark or rising graph

[Output — return ONLY the JSON below, segments array length 6-8]
{{
    "title": "Hook title in one of these styles (avoid plain 'What is X?'):\\n  A) News-linked: 'Fed raised rates — but what IS a rate hike?' \\n  B) Number+Relatable: 'Why your $3,000/mo salary feels like nothing' \\n  C) Question: 'What is inflation? Explained in 30 sec' \\n  — Include a number or emotion word. Max 70 chars",
    "description": "YouTube description under 150 chars — no time expressions like 'in 60 seconds'",
    "hashtags": ["economics", "finance", "investing", "topic_tag1", "topic_tag2"],
    "segments": [
        {{
            "index": 0,
            "narration": "★ 10-20 words, one punchy sentence ★",
            "image_prompt": "[Cartoon scene matching the narration]"
        }}
    ]
}}
'''


def generate_script(topic: dict, language: str = 'ko') -> dict:
    template = PROMPT_TEMPLATE_EN if language == 'en' else PROMPT_TEMPLATE
    title_key = 'title_en' if language == 'en' else 'title'
    # title_en 없으면 title로 fallback
    title = topic.get(title_key) or topic.get('title', '')
    msg = _get_client().messages.create(
        model='claude-sonnet-4-6',
        max_tokens=2048,
        messages=[{
            'role': 'user',
            'content': template.format(
                title=title,
                level=topic.get('level', 'basic'),
                category=topic.get('category', ''),
                description=topic.get('description', '')
            )
        }]
    )
    result = extract_json(msg.content[0].text.strip())
    if language == 'ko' and 'title' in result:
        result['title'] = fix_title_grammar(result['title'])
    result['segments'] = append_outro(result.get('segments', []), language=language)
    return result
