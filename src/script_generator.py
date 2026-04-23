"""
콘텐츠 스크립트 생성 (Claude Sonnet)
카테고리(스포츠 / 경제 / 국제정세)에 따라 프롬프트 자동 선택.
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


# ── 카테고리 감지 ─────────────────────────────────────────────────────

_SPORTS_KEYWORDS = {
    '스포츠', 'sport', '축구', '야구', '농구', '테니스', '골프',
    '격투기', 'mma', '수영', '육상', '배구', '배드민턴', '사이클',
    '스키', '올림픽', '월드컵', '선수', '리그', '경기', '우승',
}

def _is_sports(topic: dict) -> bool:
    cat = topic.get('category', '').lower()
    return any(kw in cat for kw in _SPORTS_KEYWORDS)


# ── 경제 교육 프롬프트 (KO) ──────────────────────────────────────────

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
    0: ★★ 3초 훅 (절대 원칙) ★★
       시청자가 스와이프를 멈추게 만드는 첫 문장. 아래 3가지 유형 중 하나:
       A) 충격 수치형: "우리나라 사람 10명 중 7명이 이걸 모른다고요?"
       B) 반전 질문형: "금리 내리면 집값이 오른다고요? 사실 반대일 수 있어요"
       C) 공감 유발형: "월급 받자마자 통장이 텅 비는 이유, 사실 이거 때문이에요"
       → 절대 '안녕하세요' / '오늘은 ~에 대해' 같은 소개 금지
       → 시청자가 '왜?' '어떻게?' 를 묻게 만드는 문장
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
- 첫 세그먼트(index 0): 충격/놀람 표정의 캐릭터 + 주제 오브젝트 + 큰 물음표
- 마지막 세그먼트: 캐릭터가 이해한 표정 + 체크마크 or 상승 그래프

[출력 형식 — 반드시 아래 JSON만 반환, segments 배열 길이는 6~8]
{{
    "title": "아래 3가지 형식 중 주제에 맞는 것 선택 (단순 '란?/이란?' 형식 지양):\n  A) 뉴스 연동형: '코스피 6000 돌파! 그래서 금리가 뭔데?' — 최근 이슈와 연결\n  B) 공감/숫자형: '월급 300만원인데 통장이 텅텅? 원인 30초 정리' — 숫자+공감\n  C) 질문형: '금리란? 30초면 이해됨' — 명확한 질문+시간 암시\n  — 반드시 숫자 또는 감탄/의문 표현 포함, 20자 이내",
    "description": "유튜브 설명문 (150자 이내) — 'nn초', 'X분', '1분 만에', '60초 안에' 등 시간 표현 절대 사용 금지",
    "hashtags": ["경제", "경제교육", "재테크", "1분뉴스", "경제뉴스", "주제태그1", "주제태그2"],
    "segments": [
        {{
            "index": 0,
            "narration": "★ 20~40자 한 문장 — 강력한 3초 훅 ★",
            "image_prompt": "[나레이션 장면을 영어로 묘사한 카툰 이미지 프롬프트]"
        }}
    ]
}}
'''


# ── 스포츠 프롬프트 (KO) ─────────────────────────────────────────────

PROMPT_TEMPLATE_SPORTS = '''
당신은 스포츠 YouTube Shorts 채널의 콘텐츠 제작자입니다.
아래 스포츠 주제로 60초 분량의 숏폼 영상 스크립트를 만들어주세요.

주제: {title}
카테고리: {category}
설명: {description}

[요구사항]
- 대상: 스포츠를 즐기는 모든 연령대 시청자
- 세그먼트 수: 6~8개 (주제 복잡도에 따라 자유롭게)
- ★ 각 세그먼트 나레이션은 반드시 20~40자 이내 ★
  → 나레이션 하나가 짧은 한 문장이 되도록 핵심만 압축
  → 긴 내용은 여러 세그먼트로 나눔
- ★ 말투: 스포츠 중계처럼 생동감 있게, 친구에게 설명하듯 ★
  좋은 예시: 이게 진짜 대박이거든요 / 믿기지 않죠? / 역대급이에요 / 진짜 말이 안 돼요
  나쁜 예시: 의미합니다 / 나타납니다 / ~입니다 (딱딱한 교과서체 금지)
  → ~거든요, ~는데요, ~인 거예요, ~해요 등 자연스러운 구어 표현 사용
- 세그먼트 구성 예시 (8개 기준):
    0: ★★ 3초 훅 (절대 원칙) ★★
       시청자가 스와이프를 멈추게 만드는 첫 문장. 아래 3가지 유형 중 하나:
       A) 충격 기록형: "이 선수, 60년 만에 나온 기록을 세웠거든요"
       B) 반전형: "질 것 같았던 그 경기, 결말이 충격이에요"
       C) 공감 유발형: "이 장면 보고 소름 안 돋는 사람이 있을까요?"
       → 절대 '안녕하세요' / '오늘은 ~에 대해' 같은 소개 금지
       → 시청자가 '대박' '진짜?' 라는 반응을 보이게 만드는 문장
    1: 선수/팀/사건 배경 한 줄 소개
    2: 핵심 장면 또는 사건 1
    3: 핵심 장면 또는 사건 2
    4: 기록/통계로 임팩트 강조
    5: 비하인드 또는 뒷이야기
    6: 핵심 요약
    7: 마무리 한 마디
- 각 세그먼트 나레이션은 TTS로 읽히는 동안 해당 이미지와 자막이 함께 표시됨

[이미지 프롬프트 작성 규칙 — gpt-image-1 카툰 스포츠 스타일]
- 반드시 영어로만 작성 (한글/한자/일본어 절대 사용 금지)
- 스포츠 장면을 역동적이고 카툰 스타일로 묘사 (에너지 넘치는 구도)
- 나레이션 핵심 장면을 시각화:
  예) "손흥민 역전골" → cartoon soccer player scoring goal, ball flying into net, crowd going wild
  예) "타율 4할 달성" → cartoon baseball batter in powerful swing, ".400" stat badge glowing
  예) "역전 우승" → cartoon athlete holding gold trophy, scoreboard showing comeback, confetti
  예) "세계 신기록" → cartoon sprinter breaking finish line tape, "WR" badge, digital timer
  예) "연장 결승골" → cartoon player celebrating in extra time, opponents shocked, crowd erupting
- 첫 세그먼트(index 0): 충격/흥분 표정의 캐릭터 + 주제 오브젝트 + 폭발 이펙트
- 마지막 세그먼트: 캐릭터 승리/환호 포즈 + 트로피/메달 + 체크마크

[출력 형식 — 반드시 아래 JSON만 반환, segments 배열 길이는 6~8]
{{
    "title": "스포츠 뉴스 숏폼 스타일 제목 (아래 형식 중 선택):\n  A) 충격형: '손흥민 이번엔 진짜 역대급이다'\n  B) 기록형: '타율 4할? 60년 만에 나왔다'\n  C) 반전형: '전반 0:3으로 지다가 결국..'\n  — 숫자 또는 감탄/의문 표현 포함, 20자 이내",
    "description": "유튜브 설명문 (150자 이내) — 시간 표현 절대 사용 금지",
    "hashtags": ["스포츠", "스포츠뉴스", "1분뉴스", "쇼츠뉴스", "주제태그1", "주제태그2"],
    "segments": [
        {{
            "index": 0,
            "narration": "★ 20~40자 한 문장 — 강력한 3초 훅 ★",
            "image_prompt": "[스포츠 장면을 영어로 묘사한 카툰 이미지 프롬프트]"
        }}
    ]
}}
'''


# ── 경제 교육 프롬프트 (EN) ──────────────────────────────────────────

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
    0: ★★ 3-Second Hook (non-negotiable) ★★
       The opening line that stops the scroll. Choose one type:
       A) Shocking stat: "9 out of 10 people get THIS completely wrong about money"
       B) Counterintuitive: "Lower interest rates → higher prices? Here's the truth"
       C) Relatable pain: "Your paycheck disappears every month because of THIS"
       → Never start with "Hi" / "Today we'll learn about..." / "Welcome back"
       → Make the viewer think "wait, what?" in the first 3 seconds
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
- First segment (index 0): shocked/curious character + topic object + big question mark
- Last segment: "aha!" expression + checkmark or rising graph

[Output — return ONLY the JSON below, segments array length 6-8]
{{
    "title": "Hook title in one of these styles (avoid plain 'What is X?'):\\n  A) News-linked: 'Fed raised rates — but what IS a rate hike?' \\n  B) Number+Relatable: 'Why your $3,000/mo salary feels like nothing' \\n  C) Question: 'What is inflation? Explained in 30 sec' \\n  — Include a number or emotion word. Max 70 chars",
    "description": "YouTube description under 150 chars — no time expressions like 'in 60 seconds'",
    "hashtags": ["economics", "finance", "investing", "1minnews", "econshorts", "topic_tag1", "topic_tag2"],
    "segments": [
        {{
            "index": 0,
            "narration": "★ 10-20 words — powerful 3-second hook ★",
            "image_prompt": "[Cartoon scene matching the narration]"
        }}
    ]
}}
'''


# ── 스포츠 프롬프트 (EN) ─────────────────────────────────────────────

PROMPT_TEMPLATE_SPORTS_EN = '''
You are a content creator for an English sports YouTube Shorts channel.
Create a 60-second sports highlight script on the topic below.

Topic: {title}
Category: {category}
Description: {description}

[Requirements]
- Target audience: sports fans of all ages
- Number of segments: 6-8 (based on topic complexity)
- ★ Each segment narration MUST be 10-20 words ★
  → One short punchy sentence, core point only
- ★ Tone: exciting like a sports commentary, like talking to a friend ★
  Good: "This is absolutely insane..." / "You won't believe this..." / "All-time record right here"
  Bad: "It represents..." / "It indicates..." (no dry textbook language)
  → Use energy, emotion, contractions — keep it hype
- Segment structure (8 segments):
    0: ★★ 3-Second Hook (non-negotiable) ★★
       The opening line that stops the scroll. Choose one type:
       A) Shocking record: "This athlete just broke a 60-year-old record"
       B) Comeback: "They were losing 0-3 at halftime. What happened next is insane"
       C) Relatable awe: "This moment gave goosebumps to an entire stadium"
       → Never start with "Hi" / "Today we'll talk about..." / "Welcome back"
       → Make the viewer think "wait, seriously?" in 3 seconds
    1: Background — player/team/event in one line
    2: Key moment 1
    3: Key moment 2
    4: Numbers/stats for impact
    5: Behind-the-scenes or fun fact
    6: Core takeaway
    7: Punchy sign-off

[Image prompt rules — gpt-image-1 cartoon sports style]
- Write in English only
- Describe dynamic, action-packed cartoon sports scenes
- Use energy lines, crowd reactions, scoreboard, trophies
- First segment (index 0): shocked/amazed cartoon character + sport object + explosion effect
- Last segment: victory pose character + trophy/medal + checkmark

[Output — return ONLY the JSON below, segments array length 6-8]
{{
    "title": "Sports news shorts style title:\\n  A) Shock: 'This athlete just broke a record nobody expected'\\n  B) Record: 'A .400 batting average? Hasn't happened in 60 years'\\n  C) Comeback: 'Down 0-3 at halftime. Then THIS happened'\\n  — Include a number or emotion word. Max 70 chars",
    "description": "YouTube description under 150 chars — no time expressions",
    "hashtags": ["sports", "sportsnews", "shorts", "1minnews", "topic_tag1", "topic_tag2"],
    "segments": [
        {{
            "index": 0,
            "narration": "★ 10-20 words — powerful 3-second hook ★",
            "image_prompt": "[Dynamic cartoon sports scene matching the narration]"
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
    def fix_value(m):
        inner = m.group(1)
        inner = inner.replace('"', '')
        return f'"{inner}"'
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

OUTRO_NARRATION    = "구독이랑 좋아요 눌러주시면 더 열심히 만들게요!"
OUTRO_NARRATION_EN = "Like and subscribe for more!"

OUTRO_IMAGE_PROMPT = (
    "Cute cartoon character smiling and waving at the camera, "
    "holding a large red subscribe button in one hand and a blue thumbs-up like button "
    "in the other hand, bright cheerful colors, simple flat design, YouTube Shorts style"
)

_ASSET_DIR      = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'assets')
OUTRO_IMAGE     = _os.path.join(_ASSET_DIR, 'outro_image.png')
OUTRO_AUDIO     = _os.path.join(_ASSET_DIR, 'outro_audio.mp3')
OUTRO_AUDIO_EN  = _os.path.join(_ASSET_DIR, 'outro_audio_en.mp3')


def append_outro(segments: list, language: str = 'ko') -> list:
    """마지막 세그먼트 뒤에 구독/좋아요 유도 멘트 추가."""
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


def generate_script(topic: dict, language: str = 'ko') -> dict:
    sports = _is_sports(topic)
    if language == 'en':
        template = PROMPT_TEMPLATE_SPORTS_EN if sports else PROMPT_TEMPLATE_EN
    else:
        template = PROMPT_TEMPLATE_SPORTS if sports else PROMPT_TEMPLATE

    template_name = ('sports_en' if sports else 'econ_en') if language == 'en' \
                 else ('sports_ko' if sports else 'econ_ko')
    print(f'   [스크립트] 템플릿={template_name} | category={topic.get("category", "")}')

    title_key = 'title_en' if language == 'en' else 'title'
    title = topic.get(title_key) or topic.get('title', '')

    fmt_kwargs = dict(
        title=title,
        category=topic.get('category', ''),
        description=topic.get('description', ''),
    )
    if not sports:
        fmt_kwargs['level'] = topic.get('level', 'basic')

    msg = _get_client().messages.create(
        model='claude-sonnet-4-6',
        max_tokens=2048,
        messages=[{
            'role': 'user',
            'content': template.format(**fmt_kwargs)
        }]
    )
    result = extract_json(msg.content[0].text.strip())
    if language == 'ko' and 'title' in result:
        result['title'] = fix_title_grammar(result['title'])
    result['segments'] = append_outro(result.get('segments', []), language=language)
    return result
