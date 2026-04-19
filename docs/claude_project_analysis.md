# 프로젝트 코드 분석 메모

작성일: 2026-04-19  
최종 수정: 2026-04-19 (검증 후 오류 수정)  
대상: Claude 설계 전달용  
검토 범위: `HANDOVER.md`, `main.py`, `news_main.py`, `src/*.py`, `supabase_schema.sql`, GitHub Actions workflow 일부

> **참고:** `AGENTS.md`는 실제 코드와 맞지 않는 구버전 문서입니다 (DALL-E 3, 1024×1792, Codex 언급 등).  
> 아키텍처 판단은 반드시 실제 코드 또는 `HANDOVER.md` 기준으로 하세요.

---

## 1. 한눈에 보는 프로젝트 이해

이 프로젝트는 크게 3개 파이프라인으로 나뉩니다.

1. 커리큘럼형 경제 교육 Shorts
   - `main.py`
   - `topics` 테이블에서 다음 주제를 뽑고
   - Claude로 스크립트 생성
   - `gpt-image-1` (1024×1024, quality=low)로 세그먼트당 이미지 1장씩 생성
   - ElevenLabs로 TTS 생성
   - MoviePy로 영상 합성 (정사각형 이미지를 1080×1920 프레임에 삽입)
   - YouTube 업로드 후 `videos`/`topics` 상태 갱신

2. 뉴스형 Shorts
   - `news_main.py`
   - RSS 수집 후 `news_items` 저장
   - 관심도 규칙 기반 점수화 (API 호출 없음)
   - Claude로 뉴스 스크립트 생성 (경제 관련성 앵글 재구성 포함)
   - 이미지/TTS/영상 합성
   - YouTube 업로드 후 `news_items` 상태 갱신

3. 성과 분석 리포트
   - `stats_report.py`
   - YouTube 채널의 전체 업로드 영상을 수집
   - Supabase 메타정보와 결합
   - Claude로 분석 리포트 생성
   - `video_stats`, `analysis_reports` 저장

전체 구조는 명확하고, 모듈 분리도 꽤 잘 되어 있습니다.  
특히 `news`, `curriculum`, `stats`가 파일 레벨에서 잘 분리되어 있어 이후 Claude가 재설계하거나 리팩터링하기 좋은 상태입니다.

---

## 2. 실제 코드와 문서의 차이

`HANDOVER.md`와 AGENTS 문서 기준 아키텍처는 대체로 맞지만, 실제 구현은 몇 군데 달라져 있습니다.

- 문서상 이미지 생성기는 `DALL-E 3`, 세로형 `1024×1792`, 4장으로 설명되어 있음
- 실제 코드는 `gpt-image-1`, `1024x1024`, `quality="low"`, 세그먼트 수만큼 생성
  - 근거: `src/image_generator.py:47-53`

- 문서상 언어별로 한국어/영어 채널, 언어별 피드 선택처럼 읽히지만
- 실제 **뉴스 수집(fetch)** 단계는 `language` 파라미터를 무시하고 국내/해외 RSS를 항상 동시에 수집함
  - 단, **스크립트 생성** 단계에서는 `language='ko'`/`'en'`에 따라 프롬프트가 분기됨 (`NEWS_PROMPT` vs `NEWS_PROMPT_EN`)
  - 즉, 수집 소스 언어와 생성 콘텐츠 언어가 완전히 연결되지 않은 구조
  - 근거: `src/news_fetcher.py:96-111`, `src/news_script_generator.py:19, 93`

- 문서상 커리큘럼 파이프라인도 안정적으로 보이지만
- 실제 `topics` 스키마와 상태 전이 코드 사이에 불일치가 있음 (→ 3절 P0 참조)
  - 근거: `supabase_schema.sql:17`, `src/topic_manager.py:66-68`

즉, 현재 문서는 운영 개념 설명에는 좋지만, Claude가 설계 판단을 할 때는 실제 코드 기준으로 봐야 합니다.

---

## 3. 우선순위 높은 문제점

### P0. `topics.status` 스키마와 코드가 충돌함

- 스키마는 `topics.status`를 `pending / in_progress / done`만 허용
  - `supabase_schema.sql:17`
- 그런데 코드에서는 실패 시 `failed`로 업데이트함
  - `src/topic_manager.py:66-68`
  - 호출부: `main.py:120`

영향:

- 커리큘럼 파이프라인에서 예외가 나면 원래 예외 처리 중 `mark_failed()`가 다시 DB constraint 오류를 일으킬 수 있습니다.
- 결과적으로 진짜 원인보다 상태 업데이트 실패가 앞에 드러나서 디버깅이 더 어려워질 가능성이 큽니다.

권장 조치:

- `topics.status`에 `failed`를 추가 (스키마 수정 + 기존 DB ALTER TABLE 마이그레이션)
- **→ `supabase_schema.sql` 수정 완료.** 기존 DB에는 파일 하단의 ALTER TABLE 마이그레이션 쿼리를 Supabase SQL Editor에서 실행해야 합니다.

### P0. `videos.published_at` 저장 방식이 잘못될 가능성이 큼

- `save_video()`에서 `published_at`을 문자열 `'NOW()'`로 insert
  - `src/topic_manager.py:81`

영향:

- Supabase/PostgREST는 Python dict 값을 SQL로 실행하지 않습니다. `'NOW()'`는 SQL 함수가 아니라 문자열 그대로 들어가거나, TIMESTAMPTZ 타입 불일치로 insert 자체가 실패할 수 있습니다.
- 업로드 기록 저장이 실패하면 `mark_done()` 이전에 파이프라인이 중단될 수 있습니다.

권장 조치:

- Python에서 UTC ISO 문자열을 만들어 넣는다: `datetime.now(timezone.utc).isoformat()`
- **→ `src/topic_manager.py` 수정 완료.**

### P0. `topics.status = 'in_progress'` stuck 상태 — 크래시 복구 없음

- `main.py`는 파이프라인 시작 시 `mark_in_progress()`를 호출함
  - `main.py:38`
- 이후 파이프라인이 프로세스 강제 종료(SIGKILL, Actions 타임아웃 등)로 중단되면 `in_progress` 상태 그대로 남음
- `get_next_topic()`은 `pending`만 조회하므로 해당 주제는 영구적으로 처리 불가 상태가 됨
  - `src/topic_manager.py:25-27`

뉴스 파이프라인(`news_main.py`)도 동일 구조.

권장 조치:

- 파이프라인 시작 시 오래된 `in_progress` 항목(예: 2시간 이상)을 `pending`으로 자동 복구하는 함수 추가
- 또는 Actions workflow에 타임아웃 설정 + 실패 후 상태 복구 step 추가

### P1. 뉴스 스케줄 실행이 슬롯보다 최대 90분 일찍 실행되며, 중복 방지 장치가 없음

- 스케줄 판정은 현재 시각이 슬롯 90분 이내면 실행 허용
  - `src/settings_manager.py:66-73`
- 워크플로우는 매시간 실행
  - `.github/workflows/news_shorts.yml:5`
- `main.py`, `news_main.py`에는 `stats_report.py` 같은 마지막 실행 시각 잠금이 없음
  - `main.py:20`
  - `news_main.py:28`

영향:

- 예를 들어 오전 9시 슬롯이면 7시 30분~9시 사이의 실행이 모두 허용됩니다.
- 동일 슬롯에 대해 재실행, 수동 재실행, GitHub Actions 재시도 등이 겹치면 중복 업로드 또는 예정보다 너무 이른 게시가 일어날 수 있습니다.

권장 조치:

- 슬롯별 실행 lock을 `settings` 또는 별도 `job_runs` 테이블에 저장
- "이번 슬롯 이미 처리함" 체크 추가
- 실행 허용 윈도우를 더 좁히거나, 슬롯 기준 가장 가까운 1회만 허용하도록 변경

### P1. 뉴스 갱신 시 `pending` 뉴스 전체 삭제

- `refresh_and_fetch_news()`가 기존 `pending`을 전부 삭제
  - `src/news_fetcher.py:357`
- **`queued` 상태 보존은 이미 구현되어 있음** (`.eq('status', 'pending')`만 삭제)

영향:

- 관심도 점수가 높더라도 `queued`에 올리지 않은 `pending` 뉴스 후보는 매 refresh마다 사라집니다.
- 관심도 기반 백로그 운영이 아니라, 사실상 "매 실행마다 후보 풀을 재구성"하는 구조가 됩니다.

권장 조치:

- `published_at` 기준 TTL 아카이브 방식으로 변경
- `pending` 유지 + 새 뉴스 upsert
- `interest_level = 'high'`인 pending은 refresh 후에도 보존하는 정책 추가

### P1. 커리큘럼 통계 카테고리 메타가 거의 제대로 쌓이지 않을 가능성

- 통계 수집은 `videos.script_json.category`를 읽어 카테고리를 복원
  - `src/youtube_stats.py:129-142`
- 그런데 스크립트 생성 결과 JSON에는 `category` 필드가 없음
  - `src/script_generator.py:63-66`, `206-209`

영향:

- 커리큘럼 영상 통계가 대부분 기본값 `'커리큘럼'`으로만 들어갈 가능성이 큽니다.
- 카테고리별 성과 분석의 정확도가 떨어집니다.

권장 조치:

- `save_video()` 시 `topic.category`, `topic.level`, `language`를 별도 컬럼 또는 `script_json`에 명시 저장
- 분석 파이프라인은 생성 결과가 아니라 원본 topic 메타를 기준으로 집계

---

## 4. 중간 우선순위 개선 포인트

### 4-1. 이미지 전략과 문서 전략이 분리되어 있음

- 문서/설계는 4장의 세로형 슬라이드 기반으로 읽히는데
- 실제 코드는 세그먼트 수만큼 1:1 정사각형 이미지를 생성하고, 영상 합성 단계에서 1080×1920 프레임에 붙입니다.

이 구조도 동작은 가능하지만, Claude가 추후 비주얼 설계를 할 때 기준이 혼선될 수 있습니다.

권장:

- "정사각형 이미지 여러 장 + 영상에서 세로 합성"으로 문서를 업데이트하거나
- 반대로 세로형 소수 장면 구조로 실제 코드를 재설계

### 4-2. 뉴스 수집이 언어 설정과 분리되어 있어 채널 정체성이 섞일 수 있음

- 코드 주석에도 명시적으로 "국내 + 해외 피드를 항상 동시에 수집"이라고 되어 있음
  - `src/news_fetcher.py:96-97`
- 스크립트 생성은 language 파라미터로 한/영 프롬프트를 분기하지만, 소스 뉴스 자체의 언어는 걸러지지 않음

영향:

- 한국어 채널에서 영어권 이슈(BBC, Yahoo Finance 기사 기반)가 들어오거나, 영어 채널에서 한국 RSS 기반 뉴스가 섞일 수 있습니다.

권장:

- `language=ko`면 한국 소스 우선
- `language=en`면 해외 소스 우선
- 또는 소스 언어와 채널 언어를 분리한 뒤 번역형 콘텐츠인지 명시하는 구조로 확장

### 4-3. 업로드 메타데이터가 너무 고정적임

- `categoryId`가 항상 `25`로 고정
  - `src/youtube_uploader.py:117`

영향:

- 뉴스형은 맞을 수 있지만 커리큘럼형 경제 교육 영상까지 `News & Politics`로 들어갑니다.
- 채널 분류와 추천 품질에 불리할 수 있습니다.

권장:

- 뉴스와 커리큘럼의 `categoryId` 분리
- 설명문/태그/playlist 정책도 파이프라인별로 나누기

### 4-4. YouTube 업로드 resumable 설정인데 실제 resumable loop는 없음

- `MediaFileUpload(... resumable=True)`를 쓰지만
- 업로드는 `request.execute()` 한 번으로 끝냄
  - `src/youtube_uploader.py:125-133`

즉시 깨지는 버그라고 단정하긴 어렵지만, 큰 파일/네트워크 이슈 복구 관점에서는 반쪽짜리 설정입니다.

권장:

- `next_chunk()` 기반 resumable 업로드로 변경
- 실패 시 재시도/로그 분리

### 4-5. 외부 API 의존성이 큰데 idempotency 키가 없음

현재 구조는 다음 단계로 바로 넘어가는 직렬 파이프라인입니다.

- 스크립트 생성 성공
- 이미지 생성 성공
- TTS 생성 성공
- 영상 합성 성공
- 업로드 성공

중간 실패 후 재시도 시 이미 생성된 산출물을 재사용하는 정책이 약합니다.  
특히 동일 topic/news에 대해 이미 생성된 이미지/오디오/영상 캐시 재사용 로직이 거의 없습니다.

권장:

- `output` 산출물과 DB status를 연결하는 작업 단위 ID 도입
- `script_generated`, `images_generated`, `tts_generated`, `video_composed`, `uploaded` 식의 단계형 상태관리 도입

### 4-6. `topic_manager.py` 모듈 임포트 타임에 API 클라이언트 초기화

- 파일 최상단에서 즉시 초기화: `_anthropic = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])`
  - `src/topic_manager.py:9`
- 다른 모듈들(news_fetcher 등)은 함수 내부에서 lazy init 패턴을 사용함

영향:

- `ANTHROPIC_API_KEY` 환경변수 없이 import 시 즉시 크래시
- 테스트, 부분 실행, 모킹 등이 어려워짐

권장:

- 다른 모듈과 일관성 있게 lazy init 패턴으로 변경

---

## 5. 현재 코드에서 좋은 점

이 프로젝트는 개선 포인트가 분명하지만, 기반 자체는 나쁘지 않습니다.

- `news_main.py`, `main.py`, `stats_report.py`로 책임 분리가 선명함
- `settings_manager.py`로 스케줄 정책이 어느 정도 중앙화되어 있음
- `pipeline_logger.py`가 있어 운영 로그 확장 기반이 있음
- `video_composer.py`가 자막 타이핑, Ken Burns, 전환 효과 등 표현 품질을 꽤 신경 쓴 구조
- `news_script_generator.py`에서 경제 관련성 앵글 재구성, 정치 뉴스 중립화, 스포츠 경제 각도 설정 등 콘텐츠 정책을 프롬프트에 체계적으로 반영한 점이 좋음
- `auto_queue_top_news()`로 관심도 기반 자동 큐 등록이 구현되어 있어 완전 자동화 기반이 있음
- `python -m compileall .` 기준 문법 오류는 발견되지 않음

즉, "처음부터 갈아엎어야 하는 코드"는 아니고,  
"운영 안정성과 메타데이터 일관성을 보강하면 훨씬 좋아지는 코드"에 가깝습니다.

---

## 6. Claude에게 권장하는 설계 방향

Claude가 이 프로젝트를 다음 단계로 설계한다면, 아래 순서가 가장 효율적입니다.

1. 데이터 모델 정합성 먼저 고치기
   - `topics.status` 상태값 통일 (→ 완료: `failed` 추가)
   - `videos`/`news_items`에 저장할 메타데이터 표준화
   - `published_at`, `language`, `video_type`, `category`, `run_id` 명확화 (→ 완료: `published_at` 버그 수정)

2. 파이프라인을 단계형 상태 머신으로 바꾸기
   - 한 번 실패해도 다음 재실행이 안전하게 이어지도록 설계
   - `in_progress` stuck 상태 복구 포함
   - API 비용 절약을 위해 생성물 캐시 전략 포함

3. 스케줄 실행 idempotency 추가
   - 슬롯 기반 락
   - 중복 업로드 방지
   - 수동 실행과 자동 실행의 정책 분리

4. 채널/언어/콘텐츠 타입 정책 명확화
   - 한국어/영어 채널의 소스, 스크립트, 태그, 업로드 설정 분리
   - 뉴스형 vs 커리큘럼형 메타데이터 분리

5. 분석 리포트 신뢰도 높이기
   - 통계용 category/type가 생성 시점부터 정확히 저장되도록 변경
   - title 추론 fallback 의존도를 줄이기

---

## 7. 빠른 수정 우선순위 제안

| 순위 | 항목 | 상태 |
|------|------|------|
| 1 | `topics.status`에 `failed` 추가 | ✅ 완료 (기존 DB는 ALTER TABLE 마이그레이션 실행 필요) |
| 2 | `save_video()`의 `published_at='NOW()'` 수정 | ✅ 완료 |
| 3 | `in_progress` stuck 상태 자동 복구 | 미완 |
| 4 | 스케줄 슬롯 중복 실행 방지 장치 추가 | 미완 |
| 5 | `refresh_and_fetch_news()`의 전체 삭제 정책 완화 | 미완 |
| 6 | `videos` 저장 시 `topic.category`, `level`, `language` 명시 저장 | 미완 |
| 7 | 이미지/문서 아키텍처 설명 일치시키기 | 미완 |
| 8 | `topic_manager.py` lazy init 패턴 적용 | 미완 |

---

## 8. 참고 근거 파일

> ⚠️ `AGENTS.md`는 실제 구현과 맞지 않는 구버전 문서입니다. 아키텍처 근거로 사용하지 마세요.

- `HANDOVER.md` ← 최신 운영 문서
- `main.py`
- `news_main.py`
- `src/topic_manager.py`
- `src/settings_manager.py`
- `src/news_fetcher.py`
- `src/script_generator.py`
- `src/news_script_generator.py`
- `src/image_generator.py`
- `src/youtube_uploader.py`
- `src/youtube_stats.py`
- `supabase_schema.sql`
- `.github/workflows/news_shorts.yml`

---

## 9. 한 줄 총평

현재 프로젝트는 "아이디어 검증용 MVP를 꽤 멀리 밀어붙인 상태"로 보이며, 구조는 충분히 재사용 가능하지만 운영 안정성, 상태 관리, 메타데이터 정합성을 보강하지 않으면 자동화가 길게 갈수록 꼬일 가능성이 큽니다.
