"""
뉴스 기사 → YouTube Shorts 스크립트 생성 (Claude Sonnet)
커리큘럼용 script_generator.py와 별도 — 뉴스 요약 특화
"""
import os
import re
import anthropic
from src.script_generator import fix_title_grammar, extract_json, append_outro

_client = None

def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
    return _client

NEWS_PROMPT = '''
당신은 뉴스 YouTube Shorts 채널의 콘텐츠 제작자입니다.
아래 뉴스 기사를 60초 Shorts 영상 스크립트로 만들어주세요.

뉴스 제목: {title}
뉴스 출처: {source}
기사 요약: {summary}
분야: {category}

[요구사항]
- 대상: {category} 분야에 관심 있는 20~40대
- 세그먼트 수: 6~8개
- ★ 각 세그먼트 나레이션은 반드시 20~40자 이내 ★
- 뉴스 내용을 이해하기 쉽게 요약 (전문용어 최소화)
- ★ 말투: 친구에게 이야기하듯 자연스러운 구어체 ★
    좋은 예시: 이거 진짜 큰일 났어요 / 그래서 어떻게 됐냐면요 / 쉽게 말하면요
    나쁜 예시: 발표했습니다 / 밝혔습니다 / 시행될 예정입니다 (뉴스 리딩체 금지)
    → ~했어요, ~거든요, ~는데요, ~인 거예요 등 구어 표현 사용
- 세그먼트 구성:
    0: 헤드라인 한 줄 요약 (시청자 관심 유발 — 반드시 구어체)
    1: 무슨 일이 일어났나? (쉽고 친근하게)
    2~5: 핵심 내용 / 배경 / 숫자/데이터 (대화하듯)
    마지막: 영향 또는 전망 (짧고 임팩트 있게)

[이미지 프롬프트 규칙 — 영어로만]
- 반드시 영어로 작성 (한글/한자 절대 금지)
- {image_rule}
- 캐릭터, 차트, 화살표, 건물, 아이콘 등 활용
- 첫 세그먼트: 뉴스 핵심 오브젝트 + 놀란 캐릭터
- 마지막 세그먼트: 영향 받는 사람들 또는 미래 전망 이미지

[출력 형식 — 반드시 아래 JSON만 반환]
{{
    "title": "뉴스 핵심을 담은 제목 (30자 이내)",
    "description": "유튜브 설명문 (150자 이내) — 시간 표현 금지",
    "hashtags": ["{category}뉴스", "{category}", "뉴스요약", "주제태그"],
    "person_name": "기사의 핵심 인물 이름 (없으면 null)",
    "segments": [
        {{
            "index": 0,
            "narration": "★ 20~40자 한 문장 ★",
            "image_prompt": "[영어로 된 카툰 이미지 프롬프트]"
        }}
    ]
}}
'''

# 이미지 프롬프트 규칙 — 인물 관련 여부에 따라 분기
IMAGE_RULE_PERSON = (
    "When drawing the key person ({person_name}), use cartoon caricature style: "
    "exaggerated features, bold outlines, flat colors, editorial cartoon look. "
    "No photorealism. No realistic faces. Caricature only. "
    "Include the word 'caricature' in the image prompt for segments featuring this person."
)
IMAGE_RULE_DEFAULT = (
    "Draw educational cartoon scenes that visually represent the news content."
)


NEWS_PROMPT_EN = '''
You are a content creator for an English news YouTube Shorts channel.
Turn the news article below into a 60-second Shorts script.

News Title: {title}
Source: {source}
Summary: {summary}
Category: {category}

[Requirements]
- Target: 20-40s interested in {category}
- Segments: 6-8
- ★ Each narration MUST be 10-20 words ★
- Simplify the news clearly (minimize jargon)
- ★ Tone: conversational, like telling a friend ★
  Good: "Okay so here's what happened..." / "This is actually a big deal because..."
  Bad: "announced" / "stated" / "will be implemented" (no news-anchor language)
  → Use contractions and casual phrasing
- Structure:
    0: One-line headline hook (grab attention — conversational)
    1: What happened? (simple, friendly)
    2-5: Key facts / background / numbers (informal)
    Last: Impact or outlook (short, punchy)

[Image prompt rules — English only]
- Write in English only
- {image_rule}
- Use characters, charts, arrows, buildings, icons
- First segment: core news object + surprised character
- Last segment: affected people or future outlook image

[Output — return ONLY the JSON below]
{{
    "title": "Core news title in English (under 70 chars)",
    "description": "YouTube description under 150 chars — no time expressions",
    "hashtags": ["{category}news", "{category}", "newsupdate", "topic_tag"],
    "person_name": "key person's name (null if none)",
    "segments": [
        {{
            "index": 0,
            "narration": "★ 10-20 words, one punchy sentence ★",
            "image_prompt": "[English cartoon image prompt]"
        }}
    ]
}}
'''

FACT_CHECK_PROMPT = '''
아래는 뉴스 기사를 바탕으로 작성된 YouTube Shorts 스크립트입니다.
웹 검색을 통해 주요 사실(수치, 날짜, 기관명, 정책 내용 등)을 팩트체크하고,
잘못되거나 불정확한 내용이 있으면 수정하세요.

원본 뉴스 제목: {title}
원본 출처: {source}

스크립트 나레이션:
{narrations}

[지시사항]
1. 핵심 사실(숫자, 기관, 날짜, 정책명)을 웹 검색으로 확인하세요.
2. 확인된 내용 기반으로 스크립트를 수정하세요.
3. 사실과 다른 내용은 정정하고, 불확실한 내용은 "~로 알려짐", "~예상" 등으로 완화하세요.
4. 수정이 없는 경우 원본 그대로 반환하세요.
5. 반드시 아래 JSON 형식으로만 반환하세요 (각 나레이션은 20~40자 이내 유지):

{{
    "checked": true,
    "corrections": ["수정 내용 요약 (없으면 빈 배열)"],
    "narrations": ["세그먼트0 나레이션", "세그먼트1 나레이션", ...]
}}
'''


def _fact_check_script(news_item: dict, script: dict) -> dict:
    """Claude web search로 스크립트 팩트체크 후 나레이션 보정"""
    narrations = [s['narration'] for s in script.get('segments', [])]
    prompt = FACT_CHECK_PROMPT.format(
        title=news_item.get('title', ''),
        source=news_item.get('source', ''),
        narrations='\n'.join(f'{i}: {n}' for i, n in enumerate(narrations))
    )

    try:
        msg = _get_client().messages.create(
            model='claude-sonnet-4-6',
            max_tokens=2048,
            tools=[{'type': 'web_search_20250305', 'name': 'web_search'}],
            messages=[{'role': 'user', 'content': prompt}]
        )

        # 텍스트 블록만 추출
        raw = ''
        for block in msg.content:
            if hasattr(block, 'text'):
                raw += block.text

        try:
            fc = extract_json(raw.strip())
        except (ValueError, Exception):
            print('   ⚠️  팩트체크 JSON 파싱 실패 — 원본 유지')
            return script
        corrections = fc.get('corrections', [])
        if corrections:
            print(f'   🔍 팩트체크 수정사항: {corrections}')
        else:
            print('   ✅ 팩트체크 이상 없음')

        # 나레이션 교체
        new_narrations = fc.get('narrations', [])
        for i, seg in enumerate(script.get('segments', [])):
            if i < len(new_narrations) and new_narrations[i]:
                seg['narration'] = new_narrations[i]

    except Exception as e:
        print(f'   ⚠️  팩트체크 오류 ({e}) — 원본 유지')

    return script


def _detect_person(title: str, summary: str) -> str | None:
    """제목/요약에서 핵심 인물 이름 간단 감지 (Claude 호출 없이)"""
    # 인물 관련 패턴: '이름 + 직책/동사' 형태
    import re
    # 한국인 이름 패턴 (2~4자 한글)
    patterns = [
        r'([가-힣]{2,4})\s*(대통령|장관|대표|총리|의원|회장|CEO|감독|선수|코치)',
        r'(트럼프|바이든|머스크|시진핑|푸틴|기시다|젤렌스키)',  # 주요 외국 인물
    ]
    for pat in patterns:
        m = re.search(pat, title + ' ' + summary)
        if m:
            return m.group(1)
    return None


def generate_news_script(news_item: dict, language: str = 'ko') -> dict:
    category = news_item.get('category', '경제' if language == 'ko' else 'economy')

    # 인물 감지 → 이미지 규칙 분기
    person = _detect_person(
        news_item.get('title', ''),
        news_item.get('summary', '')
    )
    if person:
        image_rule = IMAGE_RULE_PERSON.format(person_name=person)
        print(f'   👤 인물 감지: {person} → 카리커처 모드')
    else:
        image_rule = IMAGE_RULE_DEFAULT

    # ── 1단계: 스크립트 초안 생성 ─────────────────────
    prompt_tpl = NEWS_PROMPT_EN if language == 'en' else NEWS_PROMPT
    msg = _get_client().messages.create(
        model='claude-sonnet-4-6',
        max_tokens=2048,
        messages=[{
            'role': 'user',
            'content': prompt_tpl.format(
                title=news_item.get('title', ''),
                source=news_item.get('source', ''),
                summary=news_item.get('summary', news_item.get('title', '')),
                category=category,
                image_rule=image_rule,
            )
        }]
    )
    result = extract_json(msg.content[0].text.strip())

    # 제목 후처리 (한국어 이란/란 문법 교정)
    if language == 'ko' and 'title' in result and ('이란?' in result['title'] or '란?' in result['title']):
        result['title'] = fix_title_grammar(result['title'])

    # ── 2단계: 웹 검색 팩트체크 ──────────────────────
    print('   🔍 웹 검색 팩트체크 중...')
    result = _fact_check_script(news_item, result)

    # ── 3단계: 구독/좋아요 유도 아웃트로 추가 ────────
    result['segments'] = append_outro(result.get('segments', []), language=language)

    return result
