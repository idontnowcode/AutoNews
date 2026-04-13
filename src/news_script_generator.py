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
- 세그먼트 구성:
    0: 헤드라인 한 줄 요약 (시청자 관심 유발)
    1: 무슨 일이 일어났나?
    2~5: 핵심 내용 / 배경 / 숫자/데이터
    마지막: 영향 또는 전망

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
        msg = client.messages.create(
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

        raw = raw.strip()
        raw = re.sub(r'```[a-z]*', '', raw).strip('`').strip()
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            print('   ⚠️  팩트체크 JSON 파싱 실패 — 원본 유지')
            return script

        fc = json.loads(match.group())
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


def generate_news_script(news_item: dict) -> dict:
    category = news_item.get('category', '경제')

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
    msg = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=2048,
        messages=[{
            'role': 'user',
            'content': NEWS_PROMPT.format(
                title=news_item.get('title', ''),
                source=news_item.get('source', ''),
                summary=news_item.get('summary', news_item.get('title', '')),
                category=category,
                image_rule=image_rule,
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

    # ── 2단계: 웹 검색 팩트체크 ──────────────────────
    print('   🔍 웹 검색 팩트체크 중...')
    result = _fact_check_script(news_item, result)

    return result
