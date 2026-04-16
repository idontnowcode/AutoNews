"""
수집된 영상 통계를 Claude API로 분석 → 마크다운 리포트 생성 → Supabase 저장
"""
import os
import json
from datetime import datetime, timezone
from collections import defaultdict
import anthropic
from src.db_client import get_client


def _compute_summary(records: list[dict]) -> dict:
    """통계 요약 딕셔너리 생성 (Claude 프롬프트에 주입)"""
    if not records:
        return {}

    total = len(records)
    views = [r['view_count'] for r in records]
    avg_views = sum(views) / total if total else 0

    # 카테고리별 평균 조회수
    cat_views = defaultdict(list)
    for r in records:
        cat_views[r.get('category', '기타')].append(r['view_count'])
    cat_avg = {cat: round(sum(vs) / len(vs)) for cat, vs in cat_views.items()}

    # 타입별 (커리큘럼 vs 뉴스)
    type_views = defaultdict(list)
    for r in records:
        type_views[r.get('video_type', 'curriculum')].append(r['view_count'])
    type_avg = {t: round(sum(vs) / len(vs)) for t, vs in type_views.items()}

    # 업로드 요일별 평균
    dow_views = defaultdict(list)
    dow_names = ['월', '화', '수', '목', '금', '토', '일']
    for r in records:
        pub = r.get('published_at')
        if pub:
            try:
                dt = datetime.fromisoformat(pub.replace('Z', '+00:00'))
                dow_views[dow_names[dt.weekday()]].append(r['view_count'])
            except Exception:
                pass
    dow_avg = {d: round(sum(vs) / len(vs)) for d, vs in dow_views.items()}

    # 업로드 시간대별 (0~23시 → 새벽/오전/오후/저녁)
    hour_views = defaultdict(list)
    for r in records:
        pub = r.get('published_at')
        if pub:
            try:
                dt = datetime.fromisoformat(pub.replace('Z', '+00:00'))
                slot = '새벽(0-6)' if dt.hour < 6 else \
                       '오전(6-12)' if dt.hour < 12 else \
                       '오후(12-18)' if dt.hour < 18 else '저녁(18-24)'
                hour_views[slot].append(r['view_count'])
            except Exception:
                pass
    hour_avg = {s: round(sum(vs) / len(vs)) for s, vs in hour_views.items()}

    # Engagement Rate
    for r in records:
        r['engagement_rate'] = round(r['like_count'] / r['view_count'] * 100, 2) \
            if r['view_count'] > 0 else 0

    # 상위 / 하위 5개
    sorted_by_views = sorted(records, key=lambda x: x['view_count'], reverse=True)
    top5    = [{'title': r['title'], 'views': r['view_count'],
                'likes': r['like_count'], 'type': r['video_type'],
                'category': r['category'], 'er': r['engagement_rate']}
               for r in sorted_by_views[:5]]
    bottom5 = [{'title': r['title'], 'views': r['view_count'],
                'likes': r['like_count'], 'type': r['video_type'],
                'category': r['category'], 'er': r['engagement_rate']}
               for r in sorted_by_views[-5:]]

    # 최근 7일 vs 이전 평균
    now = datetime.now(timezone.utc)
    recent, older = [], []
    for r in records:
        pub = r.get('published_at')
        if pub:
            try:
                dt = datetime.fromisoformat(pub.replace('Z', '+00:00'))
                if (now - dt).days <= 7:
                    recent.append(r['view_count'])
                else:
                    older.append(r['view_count'])
            except Exception:
                pass
    recent_avg = round(sum(recent) / len(recent)) if recent else 0
    older_avg  = round(sum(older)  / len(older))  if older  else 0

    return {
        'total_videos':  total,
        'avg_views':     round(avg_views),
        'max_views':     max(views),
        'min_views':     min(views),
        'category_avg':  cat_avg,
        'type_avg':      type_avg,
        'dow_avg':       dow_avg,
        'hour_avg':      hour_avg,
        'top5':          top5,
        'bottom5':       bottom5,
        'recent7_avg':   recent_avg,
        'older_avg':     older_avg,
        'recent_count':  len(recent),
        'older_count':   len(older),
    }


def generate_report(records: list[dict]) -> str:
    """Claude API로 분석 리포트 생성 (마크다운)"""
    summary = _compute_summary(records)
    if not summary:
        return '# 분석 리포트\n\n분석할 영상 데이터가 없습니다.'

    client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

    prompt = f"""당신은 유튜브 채널 데이터 분석 전문가입니다.
아래는 경제 교육 YouTube Shorts 채널의 영상 통계 요약입니다.
이 데이터를 바탕으로 조회수가 들쭉날쭉한 원인을 분석하고, 개선 방향을 제시해주세요.

## 통계 요약
```json
{json.dumps(summary, ensure_ascii=False, indent=2)}
```

## 리포트 작성 지침
- 마크다운 형식으로 작성
- 한국어로 작성
- 아래 섹션을 포함하세요:
  1. 전체 현황 요약 (총 영상 수, 평균 조회수, 최고/최저)
  2. 조회수 편차 원인 분석 (카테고리, 요일/시간대, 콘텐츠 유형 관점)
  3. 상위 5개 영상 특징 분석
  4. 하위 5개 영상 특징 분석
  5. 최근 7일 트렌드 (성장 또는 하락 여부)
  6. 핵심 개선 제언 (우선순위 3가지)
- 데이터에 근거한 구체적인 수치를 포함하세요
- 섹션마다 핵심 인사이트를 1~2줄로 요약해주세요
"""

    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=2000,
        messages=[{'role': 'user', 'content': prompt}]
    )
    return message.content[0].text


def save_report(report_md: str, stats_json: dict) -> str:
    """analysis_reports 테이블에 저장, 리포트 ID 반환"""
    db = get_client()
    res = db.table('analysis_reports').insert({
        'report_md':  report_md,
        'stats_json': stats_json,
    }).execute()
    if res.data:
        return res.data[0]['id']
    return ''


def run_analysis(records: list[dict]) -> str:
    """전체 분석 파이프라인: 요약 계산 → Claude 리포트 → DB 저장"""
    print('🤖 Claude 분석 리포트 생성 중...')
    summary = _compute_summary(records)
    report_md = generate_report(records)

    report_id = save_report(report_md, summary)
    print(f'   리포트 저장 완료 (id: {report_id})')
    print('─' * 60)
    print(report_md[:500] + '...' if len(report_md) > 500 else report_md)
    print('─' * 60)
    return report_md
