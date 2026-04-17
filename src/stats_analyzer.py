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

    # DB 매칭률
    db_matched   = sum(1 for r in records if r.get('video_type') != 'unknown')
    db_unmatched = total - db_matched

    # ── 최신 10개 vs 이전 10개 트렌드 ──────────────────────────
    by_date = sorted(
        [r for r in records if r.get('published_at')],
        key=lambda x: x['published_at'], reverse=True
    )
    recent10 = by_date[:10]
    prev10   = by_date[10:20]

    r10_views = [r['view_count'] for r in recent10]
    p10_views = [r['view_count'] for r in prev10]
    r10_avg   = round(sum(r10_views) / len(r10_views)) if r10_views else 0
    p10_avg   = round(sum(p10_views) / len(p10_views)) if p10_views else 0
    trend_pct = round((r10_avg - p10_avg) / p10_avg * 100, 1) if p10_avg else 0
    trend_vs_all_pct = round((r10_avg - avg_views) / avg_views * 100, 1) if avg_views else 0

    r10_er = [round(r['like_count'] / r['view_count'] * 100, 2)
              for r in recent10 if r['view_count'] > 0]
    p10_er = [round(r['like_count'] / r['view_count'] * 100, 2)
              for r in prev10   if r['view_count'] > 0]
    r10_er_avg = round(sum(r10_er) / len(r10_er), 2) if r10_er else 0
    p10_er_avg = round(sum(p10_er) / len(p10_er), 2) if p10_er else 0

    recent10_summary = [
        {'title': r['title'], 'views': r['view_count'],
         'likes': r['like_count'], 'type': r.get('video_type', ''),
         'category': r.get('category', ''), 'published_at': r.get('published_at', '')[:10]}
        for r in recent10
    ]

    return {
        'total_videos':       total,
        'db_matched':         db_matched,
        'db_unmatched':       db_unmatched,
        'avg_views':          round(avg_views),
        'max_views':          max(views),
        'min_views':          min(views),
        'std_dev':            round((sum((v - avg_views) ** 2 for v in views) / total) ** 0.5) if total > 1 else 0,
        'category_avg':       cat_avg,
        'type_avg':           type_avg,
        'dow_avg':            dow_avg,
        'hour_avg':           hour_avg,
        'top5':               top5,
        'bottom5':            bottom5,
        'recent7_avg':        recent_avg,
        'older_avg':          older_avg,
        'recent_count':       len(recent),
        'older_count':        len(older),
        # 최신 10개 트렌드
        'recent10_videos':    recent10_summary,
        'recent10_avg':       r10_avg,
        'prev10_avg':         p10_avg,
        'trend_vs_prev10_pct': trend_pct,       # 이전 10개 대비 %
        'trend_vs_all_pct':   trend_vs_all_pct,  # 전체 평균 대비 %
        'recent10_er_avg':    r10_er_avg,
        'prev10_er_avg':      p10_er_avg,
    }


def generate_report(records: list[dict], summary: dict | None = None) -> str:
    """Claude API로 분석 리포트 생성 (마크다운)"""
    if summary is None:
        summary = _compute_summary(records)
    if not summary:
        return '# 분석 리포트\n\n분석할 영상 데이터가 없습니다.'

    client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

    prompt = f"""당신은 유튜브 채널 데이터 분석 전문가입니다.
아래는 경제 교육 YouTube Shorts 채널의 **채널 전체 영상** 통계 요약입니다.
(YouTube 업로드 플레이리스트에서 직접 수집한 실제 데이터입니다.)

## 통계 요약
```json
{json.dumps(summary, ensure_ascii=False, indent=2)}
```

## 참고
- `video_type`: curriculum(경제 교육), news(뉴스), unknown(DB 미등록 영상)
- `std_dev`: 조회수 표준편차 — 클수록 편차가 심함
- `db_unmatched`: DB에 없지만 채널에 올라간 영상 수

## 리포트 작성 지침
- 마크다운 형식, 한국어 작성
- 아래 섹션을 순서대로 포함하세요:
  1. **전체 현황 요약** — 총 영상 수, 평균/최고/최저 조회수, 표준편차로 편차 수준 평가
  2. **최신 10개 트렌드 분석** ← 핵심 섹션
     - 최신 10개 avg {recent10_avg}회 vs 이전 10개 avg {prev10_avg}회 → {trend_sign}{abs_trend}% 변화
     - 전체 평균({avg_views}회) 대비 최신 10개 성과 평가
     - 최신 10개 중 잘된 영상 / 부진 영상 특징
     - Engagement Rate 변화 (좋아요/조회수): {recent10_er}% vs {prev10_er}%
     - **채널이 개선 중인지 하락 중인지 명확히 판단** (숫자 근거 포함)
  3. **조회수 편차 원인 분석** — 카테고리별, 콘텐츠 유형별, 요일/시간대 관점
  4. **상위 5개 영상 특징** — 공통점 및 성공 요인
  5. **하위 5개 영상 특징** — 공통점 및 개선 포인트
  6. **핵심 개선 제언** — 최신 트렌드를 반영한 우선순위 3가지 (구체적 실행 방법 포함)
- 모든 수치는 실제 데이터 기반으로 작성
- 각 섹션 첫 줄에 핵심 인사이트 한 줄 요약 (예: ✅ 개선 중 / ⚠️ 하락세 / ➡️ 보합)
""".format(
        recent10_avg=summary.get('recent10_avg', 0),
        prev10_avg=summary.get('prev10_avg', 0),
        trend_sign='+' if summary.get('trend_vs_prev10_pct', 0) >= 0 else '',
        abs_trend=abs(summary.get('trend_vs_prev10_pct', 0)),
        avg_views=summary.get('avg_views', 0),
        recent10_er=summary.get('recent10_er_avg', 0),
        prev10_er=summary.get('prev10_er_avg', 0),
    )

    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=8096,
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
    try:
        report_md = generate_report(records, summary)
    except Exception as e:
        err = str(e)
        if 'usage' in err.lower() or '400' in err or 'limit' in err.lower():
            print(f'⚠️  Claude API 한도 초과 — 통계 수집만 저장합니다: {err}')
            report_md = f'# 통계 수집 완료 (리포트 생성 불가)\n\nClaude API 사용 한도 초과로 분석 리포트를 생성하지 못했습니다.\n\n> {err}'
        else:
            raise

    report_id = save_report(report_md, summary)
    print(f'   리포트 저장 완료 (id: {report_id})')
    print('─' * 60)
    print(report_md[:500] + '...' if len(report_md) > 500 else report_md)
    print('─' * 60)
    return report_md
