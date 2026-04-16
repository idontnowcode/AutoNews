# stats-report Plan

## Executive Summary

| 항목 | 내용 |
|------|------|
| Feature | stats-report |
| 목적 | YouTube 영상 조회수 불균형 원인 파악 |
| 주기 | 6시간마다 자동 실행 |

### Value Delivered

| 관점 | 내용 |
|------|------|
| Problem | 업로드된 영상의 조회수가 들쭉날쭉하지만 원인을 알 수 없음 |
| Solution | 6시간마다 모든 영상 통계를 수집 후 Claude가 패턴 분석 리포트 자동 생성 |
| Function UX Effect | 대시보드에서 최신 분석 리포트를 즉시 열람 가능 |
| Core Value | 데이터 기반으로 콘텐츠 전략(카테고리·업로드 시간대·제목 등) 개선 근거 마련 |

---

## 1. 요구사항

- 6시간마다 GitHub Actions 워크플로우 실행
- 대상: Supabase `videos` + `news_items` 테이블의 모든 `youtube_id`
- YouTube Data API `videos.list(part='statistics,contentDetails')` 로 통계 수집
- 수집 데이터: viewCount, likeCount, commentCount, duration
- Claude API로 패턴 분석 → 마크다운 리포트 생성
- 리포트를 Supabase `analysis_reports` 테이블에 저장
- 대시보드 새 탭에서 최신 리포트 표시

---

## 2. 분석 항목

| 분석 | 설명 |
|------|------|
| 카테고리별 평균 조회수 | 경제/IT/스포츠/정치 등 |
| 업로드 요일·시간대 | 언제 올린 영상이 잘 되는지 |
| 뉴스 관심도 vs 조회수 | interest_level(high/medium/low)과 조회수 상관 |
| 난이도별 성과 | basic / intermediate / advanced |
| Engagement Rate | 좋아요 ÷ 조회수 (낮으면 제목·썸네일 문제) |
| 조회수 상위/하위 5개 | 극단값 원인 파악 |
| 최근 7일 트렌드 | 최근 영상이 과거보다 잘 되는지 |

---

## 3. 신규 파일

| 파일 | 역할 |
|------|------|
| `src/youtube_stats.py` | YouTube API 통계 수집 (배치 50개) |
| `src/stats_analyzer.py` | Claude API 분석 리포트 생성 |
| `stats_report.py` | 메인 실행 진입점 |
| `.github/workflows/stats_report.yml` | 6시간 cron 워크플로우 |

---

## 4. Supabase 신규 테이블

```sql
-- 영상별 최신 통계 스냅샷 (youtube_id 기준 upsert)
CREATE TABLE video_stats (
  youtube_id    TEXT PRIMARY KEY,
  title         TEXT,
  video_type    TEXT,   -- 'curriculum' | 'news'
  category      TEXT,
  view_count    INTEGER DEFAULT 0,
  like_count    INTEGER DEFAULT 0,
  comment_count INTEGER DEFAULT 0,
  duration_sec  INTEGER DEFAULT 0,
  published_at  TIMESTAMPTZ,
  fetched_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 분석 리포트 히스토리
CREATE TABLE analysis_reports (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  report_md   TEXT,
  stats_json  JSONB
);
```

---

## 5. 대시보드

- 기존 탭 옆에 "📊 리포트" 탭 추가
- 최신 `analysis_reports` 1건 마크다운 렌더링
- 이전 리포트 목록 (날짜 선택)

---

## 6. 환경 변수 (추가 없음)

기존 Secret 재사용: `YOUTUBE_TOKEN`, `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`

---

## 7. 구현 순서

1. `supabase_schema.sql` — `video_stats`, `analysis_reports` 테이블 추가
2. `src/youtube_stats.py` — 통계 수집 + Supabase upsert
3. `src/stats_analyzer.py` — Claude 분석 리포트 생성
4. `stats_report.py` — 진입점
5. `.github/workflows/stats_report.yml` — 6h cron
6. `docs/index.html` — 리포트 탭 추가
