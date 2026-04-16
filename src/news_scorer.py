"""
뉴스 관심도 채점기 (API 호출 없이 규칙 기반)

채점 기준:
  1. 크로스소스 빈도  — 동일 주제를 여러 언론이 다룰수록 높음
  2. 키워드 부스터    — 긴급/속보/주요 키워드 포함 시 점수 상승
  3. 카테고리 가중치  — 정치/경제 > 사회/국제 > IT/스포츠

결과: low / medium / high
"""
import re
from collections import defaultdict


# ── 키워드 점수표 ─────────────────────────────────────────────────
KEYWORD_HIGH = [
    '속보', '긴급', '사망', '붕괴', '폭발', '전쟁', '침공', '탄핵', '계엄',
    '대통령', '총리', '총선', '금리', '기준금리', '환율', '폭락', '폭등',
    '파산', '부도', '재난', '지진', '태풍', '화재',
]
KEYWORD_MED = [
    '발표', '선언', '협약', '조약', '인상', '인하', '동결', '개정',
    '우승', '결승', '챔피언', 'IPO', '상장', '실적', '영업이익',
]

# ── 카테고리 기본 점수 ────────────────────────────────────────────
CATEGORY_BASE = {
    '정치':   4,
    '경제':   4,
    '국제':   3,
    '사회':   3,
    'IT/테크': 2,
    '스포츠':  2,
}

# ── 관심도 임계값 ─────────────────────────────────────────────────
THRESH_HIGH = 10
THRESH_MED  = 5


def _normalize_title(title: str) -> str:
    """제목 정규화: 소문자 + 특수문자 제거 + 공백 단일화"""
    t = title.lower()
    t = re.sub(r'[^\w\s]', ' ', t, flags=re.UNICODE)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def _title_key_nouns(title: str) -> frozenset:
    """제목에서 2자 이상 단어 추출 → 공통 명사 집합 (교집합용)"""
    words = _normalize_title(title).split()
    return frozenset(w for w in words if len(w) >= 2)


def _cross_source_score(items: list[dict]) -> dict[int, int]:
    """
    같은 주제를 다룬 항목끼리 유사도 계산 →
    각 아이템 인덱스에 cross_score(0~5) 반환
    """
    n = len(items)
    noun_sets = [_title_key_nouns(it['title']) for it in items]
    scores = defaultdict(int)

    for i in range(n):
        for j in range(i + 1, n):
            s_i, s_j = noun_sets[i], noun_sets[j]
            if not s_i or not s_j:
                continue
            # Jaccard 유사도
            inter = len(s_i & s_j)
            union = len(s_i | s_j)
            jaccard = inter / union if union else 0
            if jaccard >= 0.35:   # 35% 이상 겹치면 동일 사건으로 간주
                scores[i] += 1
                scores[j] += 1

    # 최대 5점
    return {i: min(scores[i], 5) for i in range(n)}


def _keyword_score(title: str, summary: str) -> int:
    """HIGH 키워드 +3점, MED 키워드 +1점"""
    text = (title + ' ' + summary).lower()
    score = 0
    for kw in KEYWORD_HIGH:
        if kw in text:
            score += 3
            break   # 하나만 적용
    for kw in KEYWORD_MED:
        if kw in text:
            score += 1
            break
    return min(score, 4)


def _category_score(category: str) -> int:
    return CATEGORY_BASE.get(category, 2)


def score_items(items: list[dict]) -> list[dict]:
    """
    items 리스트에 interest_score, interest_level 추가해서 반환.
    items 원본을 수정하지 않고 복사본 반환.
    """
    if not items:
        return items

    cross_scores = _cross_source_score(items)
    result = []
    for i, item in enumerate(items):
        cs  = cross_scores.get(i, 0) * 3        # 최대 15점
        ks  = _keyword_score(item.get('title', ''), item.get('summary', ''))  # 최대 4점
        cats = _category_score(item.get('category', '경제'))                   # 최대 4점
        total = cs + ks + cats

        if total >= THRESH_HIGH:
            level = 'high'
        elif total >= THRESH_MED:
            level = 'medium'
        else:
            level = 'low'

        result.append({
            **item,
            'interest_score': total,
            'interest_level': level,
        })

    return result


def print_score_summary(items: list[dict]):
    """채점 결과 요약 출력"""
    high   = [it for it in items if it.get('interest_level') == 'high']
    medium = [it for it in items if it.get('interest_level') == 'medium']
    low    = [it for it in items if it.get('interest_level') == 'low']

    print(f'   📊 관심도 채점 결과: 높음 {len(high)}건 / 중간 {len(medium)}건 / 낮음 {len(low)}건')
    if high:
        print('   🔥 높음:')
        for it in high[:3]:
            print(f'      [{it["interest_score"]}점] {it["title"][:50]}')
