# 일분 스튜디오 — 인수인계 문서

> 작성일: 2026-04-19  
> 저장소: https://github.com/idontnowcode/AutoNews  
> 대시보드: GitHub Pages (`docs/index.html`)

---

## 1. 프로젝트 한 줄 요약

**경제·뉴스 YouTube Shorts 완전 자동화 파이프라인.**  
Supabase DB에서 주제/뉴스를 선택 → Claude로 스크립트 생성 → DALL-E 3으로 이미지 생성 → ElevenLabs로 TTS → MoviePy로 영상 합성 → YouTube에 자동 업로드한다.  
모든 설정과 모니터링은 GitHub Pages 대시보드 한 곳에서 관리한다.

---

## 2. 전체 아키텍처

```
┌─────────────────────────────────────────────────┐
│              GitHub Actions (서버)               │
│                                                 │
│  매시간 cron                                     │
│  ┌─────────────────┐   ┌──────────────────────┐ │
│  │  news_main.py   │   │      main.py          │ │
│  │  (뉴스 파이프라인) │   │  (커리큘럼 파이프라인)  │ │
│  └────────┬────────┘   └──────────┬───────────┘ │
└───────────┼────────────────────────┼─────────────┘
            │                        │
            ▼                        ▼
┌─────────────────────────────────────────────────┐
│                   Supabase DB                   │
│  news_items │ topics │ videos │ settings        │
│  video_stats │ analysis_reports │ pipeline_logs │
└─────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────┐
│          외부 API 호출            │
│  Anthropic Claude  — 스크립트    │
│  OpenAI DALL-E 3  — 이미지      │
│  ElevenLabs TTS   — 음성        │
│  YouTube Data API — 업로드      │
└──────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────┐
│       YouTube 채널 (결과물)       │
│  KR 채널: [일분 뉴스] / [일분 경제] │
│  EN 채널: [One Minute News/Economy] │
└──────────────────────────────────┘
```

---

## 3. 필요한 계정 & API 키 (6+1개)

| 항목 | 용도 | 발급 위치 |
|------|------|-----------|
| `ANTHROPIC_API_KEY` | Claude 스크립트 생성 | console.anthropic.com |
| `OPENAI_API_KEY` | DALL-E 3 이미지 생성 | platform.openai.com |
| `ELEVENLABS_API_KEY` | TTS 음성 생성 | elevenlabs.io |
| `SUPABASE_URL` | DB 접속 URL | Supabase 프로젝트 설정 |
| `SUPABASE_KEY` | DB anon key | Supabase 프로젝트 설정 |
| `YOUTUBE_TOKEN` | KR 채널 OAuth2 token.json 전체 | `tools/get_youtube_token.py` 실행 |
| `YOUTUBE_TOKEN_EN` | EN 채널 OAuth2 token.json 전체 (없으면 KR 채널로 fallback) | 동일 |

> **GitHub Secrets 등록 위치:** 저장소 → Settings → Secrets and variables → Actions

---

## 4. 최초 세팅 순서

### 4-1. Supabase DB 초기화
1. [supabase.com](https://supabase.com) 에서 새 프로젝트 생성
2. SQL Editor에서 `supabase_schema.sql` 전체 실행
   - 생성 테이블: `topics`, `videos`, `news_items`, `settings`, `video_stats`, `analysis_reports`, `pipeline_logs`
   - 커리큘럼 초기 시드 20개 자동 삽입됨

### 4-2. YouTube OAuth 토큰 발급

```bash
# 로컬에서 한 번만 실행
python tools/get_youtube_token.py
# → token.json 생성됨
# token.json 파일 전체 내용을 YOUTUBE_TOKEN secret에 붙여넣기
```

토큰 만료 시 재발급:
```bash
python tools/refresh_youtube_token.py
```

### 4-3. GitHub Secrets 등록
위 표의 6개 secret을 모두 등록한다.

### 4-4. 로컬 개발 환경 (선택)
```bash
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env    # API 키 입력
python news_main.py     # 뉴스 파이프라인 테스트
```

---

## 5. 대시보드 사용법

**접속:** GitHub Pages URL (저장소 → Settings → Pages에서 확인)

| 탭 | 기능 |
|----|------|
| 🏠 홈 | KST/UTC 시계, 예약 업로드 현황 카드, 최근 뉴스 처리 현황 |
| 📚 커리큘럼 | 경제 교육 주제 목록, 상태 변경 (pending/in_progress/done) |
| 📰 뉴스 | RSS 수집 뉴스 목록, 대기열 추가 버튼 |
| 📋 대기열 | 수동으로 대기 등록된 뉴스 목록, 즉시 실행 / 취소 버튼 |
| 📊 통계 | 영상별 조회수·좋아요·댓글 통계, AI 분석 리포트 |
| ⚙️ 자동화 | 예약 업로드 ON/OFF, 요일·시간대·언어·카테고리 슬롯 설정 |
| 🔔 로그 | 파이프라인 오류/경고/성공 기록, 오류 유형별 대응 방법 안내 |

### 자동화 탭 설정 방법
1. **예약 업로드** 스위치 ON
2. **업로드 요일** 선택 (매일 또는 요일 개별 선택)
3. **슬롯 추가** 버튼으로 시간대 추가:
   - `시간(KST)` / `카테고리(news|curriculum)` / `언어(ko|en)` 입력
   - 예: 오전 9시 뉴스(한국어), 오후 11시 뉴스(영어)
4. **저장** 버튼 클릭

---

## 6. 파이프라인 상세

### 6-1. 뉴스 파이프라인 (`news_main.py`)

```
RSS 수집 (feedparser)
  → 관심도 자동 채점 (news_scorer.py: low/medium/high)
  → Supabase news_items 저장
  → 대기열(queued) 우선 → pending 순으로 처리할 뉴스 선택
  → Claude로 뉴스 스크립트 생성 (news_script_generator.py)
  → DALL-E 3 이미지 생성 (image_generator.py)
  → ElevenLabs TTS (tts_generator.py)
  → MoviePy 영상 합성 (video_composer.py)
    - Ken Burns 효과 (zoom_in / pan_r / zoom_pan)
    - 전환 효과 (slide / push / wipe)
    - 타이핑 자막 효과
  → YouTube 업로드 (youtube_uploader.py)
  → DB 상태 업데이트 (status: done, youtube_id 저장)
```

**뉴스 status 흐름:**
```
pending → queued (대시보드에서 수동 대기 등록)
queued  → pending (취소)
queued / pending → in_progress → done (파이프라인 처리 완료)
any → failed (오류 발생)
```

### 6-2. 커리큘럼 파이프라인 (`main.py`)

```
Supabase topics에서 prerequisites 완료된 주제 선택 (order_index 최소)
  → pending 주제 소진 시 Claude가 10개 자동 확장
  → 동일 파이프라인 (스크립트→이미지→TTS→영상→업로드)
  → videos 테이블에 저장, topic status = done
```

> **현재 상태:** 커리큘럼 파이프라인의 cron 스케줄은 비활성화되어 있음.  
> 필요 시 `daily_shorts.yml`의 schedule 주석 해제.

### 6-3. 통계 리포트 파이프라인 (`stats_report.py`)

6시간마다 자동 실행:
- YouTube API로 업로드된 영상 통계 수집
- Claude로 분석 리포트 생성
- `video_stats`, `analysis_reports` 테이블 저장
- 대시보드 통계 탭에서 확인

---

## 7. GitHub Actions 워크플로우

| 파일 | 실행 조건 | 설명 |
|------|-----------|------|
| `news_shorts.yml` | 매시간 cron + 수동 | 뉴스 파이프라인 |
| `daily_shorts.yml` | 수동만 (cron 비활성화) | 커리큘럼 파이프라인 |
| `stats_report.yml` | 6시간 cron + 수동 | 통계 수집·분석 |
| `pages.yml` | main push | 대시보드 GitHub Pages 배포 |

### 수동 실행 옵션 (news_shorts.yml)

| 입력 | 설명 | 예시 |
|------|------|------|
| `news_id` | 특정 뉴스 UUID 지정 (없으면 자동 선택) | `abc-123-...` |
| `publish_at` | 예약 발행 UTC 시각 (없으면 즉시 공개) | `2026-04-19T14:30:00Z` |

> **KST → UTC 변환:** KST 시각 − 9시간 = UTC 시각  
> 예) 오후 11:30 KST → 14:30 UTC → `2026-04-19T14:30:00Z`

---

## 8. Supabase 테이블 정리

| 테이블 | 용도 |
|--------|------|
| `topics` | 커리큘럼 주제 목록 (status: pending/in_progress/done) |
| `videos` | 생성된 커리큘럼 영상 기록 |
| `news_items` | 수집된 뉴스 (status: pending/queued/in_progress/done/failed) |
| `settings` | 자동화 설정 키-값 저장소 |
| `video_stats` | YouTube 영상 통계 스냅샷 |
| `analysis_reports` | AI 분석 리포트 히스토리 |
| `pipeline_logs` | 파이프라인 실행 로그 (오류/경고/성공) |

### settings 테이블 주요 키

| key | 설명 | 예시 값 |
|-----|------|---------|
| `upload_schedule_enabled` | 자동화 ON/OFF | `true` / `false` |
| `upload_schedule_days` | 업로드 요일 | `everyday` / `mon,wed,fri` |
| `upload_schedule_slots` | 시간대 슬롯 JSON | `[{"hour":9,"category":"news","lang":"ko"}]` |
| `content_language` | 기본 콘텐츠 언어 | `ko` / `en` |
| `news_max_per_feed` | RSS 피드당 최대 수집 건수 | `5` |
| `news_delete_days` | done/failed 뉴스 보관 일수 | `3` |

---

## 9. 소스 파일 구조

```
src/
  db_client.py          Supabase 클라이언트 싱글톤
  settings_manager.py   자동화 설정 읽기 + 실행 여부 판단
  topic_manager.py      커리큘럼 주제 선택/확장/저장
  news_fetcher.py       RSS 수집, 뉴스 상태 관리 (queued 로직 포함)
  news_scorer.py        뉴스 관심도 규칙 기반 채점 (low/medium/high)
  script_generator.py   커리큘럼 스크립트 생성 (Claude)
  news_script_generator.py  뉴스 스크립트 생성 (Claude)
  image_generator.py    DALL-E 3 이미지 생성
  tts_generator.py      ElevenLabs TTS 생성
  video_composer.py     MoviePy 영상 합성 + 애니메이션 효과
  youtube_uploader.py   YouTube 업로드 + 예약 발행
  youtube_stats.py      YouTube 통계 수집
  stats_analyzer.py     통계 분석 리포트 생성 (Claude)
  pipeline_logger.py    Supabase pipeline_logs 기록

tools/
  get_youtube_token.py       YouTube OAuth 최초 토큰 발급
  refresh_youtube_token.py   YouTube OAuth 토큰 갱신
  generate_outro_assets.py   아웃트로 이미지/오디오 생성 (캐시됨)
  generate_font_samples.py   폰트 샘플 확인용
  reset_old_videos.py        영상 상태 초기화 유틸
  sample_effects.py          애니메이션 효과 샘플 영상 생성

main.py            커리큘럼 파이프라인 진입점
news_main.py       뉴스 파이프라인 진입점
stats_report.py    통계 리포트 진입점
supabase_schema.sql DB 스키마 (최초 1회 실행)
docs/index.html    대시보드 (GitHub Pages)
```

---

## 10. 언어(한국어/영어) 이중 채널 구조

- **KR 채널:** `YOUTUBE_TOKEN` 사용, 제목 접두사 `[일분 뉴스]` / `[일분 경제]`
- **EN 채널:** `YOUTUBE_TOKEN_EN` 사용, 제목 접두사 `[One Minute News]` / `[One Minute Economy]`

**언어 결정 우선순위 (뉴스 파이프라인):**
1. 예약 실행 모드 → 현재 시각에 매칭되는 슬롯의 `lang` 필드
2. 슬롯에 `lang` 없음 → Supabase `settings.content_language`
3. 설정 없음 → 기본값 `ko`

> 대시보드 헤더의 🇰🇷/🇺🇸 버튼은 `content_language` (전역 기본값)만 변경.  
> 특정 시간대에 영어 업로드를 원하면 슬롯에 `lang: en` 설정 필수.

---

## 11. 뉴스 관심도 채점 로직

`src/news_scorer.py`에서 API 호출 없이 규칙 기반으로 채점:

| 기준 | 내용 |
|------|------|
| 크로스소스 빈도 | 동일 주제를 여러 언론이 다룰수록 +가산 |
| 키워드 부스터 | `속보`, `금리`, `탄핵`, `전쟁` 등 포함 시 점수 상승 |
| 카테고리 가중치 | 정치·경제 > 사회·국제 > IT·스포츠 |
| 패널티 | `선임`, `임명`, `위원회` 등 인사 뉴스 감점 |
| 결과 | `low` / `medium` / `high` 3단계 |

예약 실행 모드에서는 `high → medium → any` 우선순위로 선택.

---

## 12. 영상 애니메이션 효과

`src/video_composer.py`에 구현된 6가지 효과:

| 번호 | 이름 | 설명 |
|------|------|------|
| 1 | Ken Burns zoom_in | 중앙을 1.0×→1.08× 천천히 확대 |
| 2 | Ken Burns pan_r | 왼쪽→오른쪽으로 패닝 (1.1× 줌 상태) |
| 3 | Ken Burns zoom_pan | 확대 + 오른쪽 패닝 동시 |
| 6 | Slide | 다음 이미지가 오른쪽에서 밀려 들어옴 |
| 7 | Push | 이전이 왼쪽으로 나가고 다음이 오른쪽에서 들어옴 |
| 8 | Wipe | 경계선이 왼쪽→오른쪽으로 이동하며 드러냄 |

- 영상 제목의 해시 값을 시드로 효과 2~3개 랜덤 선택 → **같은 제목은 항상 같은 효과**
- 전환 효과는 각 세그먼트 앞 0.33초(10프레임)에만 적용 → 오디오 갭 없음

---

## 13. 오류 대응 가이드

대시보드 🔔 로그 탭에서 확인 가능. 주요 오류 유형:

| 오류 유형 | 원인 | 해결 방법 |
|-----------|------|-----------|
| `youtube_auth` | OAuth 토큰 만료 | `tools/refresh_youtube_token.py` 로컬 실행 후 secret 재등록 |
| `upload_limit` | YouTube 일일 업로드 한도 초과 | youtube.com/verify 에서 채널 인증 후 재시도 |
| `api_limit` | Anthropic/OpenAI 사용량 한도 | 다음 날 자동 복구 (status는 pending으로 복귀됨) |
| `tts` | ElevenLabs 크레딧 소진 | ElevenLabs 대시보드에서 크레딧 충전 |
| `image_gen` | OpenAI 이미지 생성 실패 | DALL-E 프롬프트 정책 위반 여부 확인 |
| `rss` | RSS 피드 접속 불가 | 피드 URL 유효성 확인 (일시적 장애는 자동 복구) |
| `video` | FFmpeg 오류 | GitHub Actions 로그 상세 확인 필요 |

---

## 14. 정기 유지보수 항목

| 주기 | 작업 |
|------|------|
| 3~6개월 | YouTube OAuth 토큰 갱신 (`refresh_youtube_token.py`) |
| 커리큘럼 소진 시 | Supabase topics에서 새 주제 추가 (또는 자동 확장 대기) |
| 뉴스 피드 이상 시 | `news_fetcher.py`의 `RSS_FEEDS_KO` / `RSS_FEEDS_EN` 피드 URL 점검 |
| API 비용 급증 시 | `settings.news_max_per_feed` 값 줄이기 (기본 5) |
| 통계 리포트 이상 시 | `video_stats` 테이블 확인, `stats_report.py` 수동 실행 |

---

## 15. 비용 구조 (참고)

| 서비스 | 과금 방식 | 영상 1개당 대략 비용 |
|--------|-----------|---------------------|
| Claude (Anthropic) | 토큰 per 요청 | ~$0.01~0.03 |
| DALL-E 3 (OpenAI) | 이미지당 | ~$0.16 (4장 × $0.04) |
| ElevenLabs | 문자당 | ~$0.01~0.03 |
| GitHub Actions | 무료 tier | 월 2,000분 무료 |
| Supabase | 무료 tier | 500MB DB 무료 |

> 1일 1편 기준 월 약 $6~10 예상 (DALL-E 비중이 가장 큼)

---

## 16. 자주 하는 작업 Quick Reference

```bash
# 뉴스 즉시 실행 (GitHub Actions)
Actions → "일분 스튜디오 - 뉴스 Shorts 업로드" → Run workflow

# 특정 뉴스 예약 업로드
news_id: [뉴스 UUID]
publish_at: 2026-04-19T14:30:00Z   # UTC 기준

# 커리큘럼 수동 실행
Actions → "일분 스튜디오 - 커리큘럼 Shorts 업로드" → Run workflow

# DB 스키마 재실행 (새 테이블 추가 등)
Supabase → SQL Editor → supabase_schema.sql 해당 부분만 실행

# 아웃트로 asset 재생성 (변경 필요 시)
python tools/generate_outro_assets.py

# 로컬 테스트
cp .env.example .env   # API 키 입력
python news_main.py    # 뉴스 1건 처리 후 output/ 폴더에 결과물 저장
```

---

## 17. 알려진 제한사항 및 주의사항

1. **YouTube OAuth 토큰은 저장소에 절대 커밋하지 않는다.** GitHub Secret으로만 관리.
2. **커리큘럼 파이프라인 cron은 현재 비활성화.**  
   `daily_shorts.yml`에서 주석 해제하면 자동 실행 가능하나, 커리큘럼 영상 소진 속도 주의.
3. **DALL-E 생성 이미지 정책:** 특정 인물명, 브랜드명을 이미지 프롬프트에 포함하면 거부될 수 있음.  
   `image_generator.py`에서 프롬프트 가이드라인 참고.
4. **GitHub Actions 무료 tier 한도:** 월 2,000분. 매시간 뉴스 파이프라인 실행 시 한 달 약 720회 실행.  
   영상 1건 합성에 약 2~3분 소요 → 실제 실행은 설정 조건 통과 시에만 이루어짐.
5. **Pillow 버전 고정:** `Pillow>=9.0.0,<10.0.0`. MoviePy 1.0.3와의 호환성 때문. 임의 업그레이드 주의.
6. **대시보드는 정적 HTML.** Supabase JS 클라이언트로 직접 DB에 접근하는 구조.  
   `docs/index.html` 상단의 `SUPABASE_URL`, `SUPABASE_ANON_KEY` 변수값이 실제 프로젝트 값인지 확인.
