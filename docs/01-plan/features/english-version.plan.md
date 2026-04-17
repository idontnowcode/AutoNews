# english-version Plan

## Executive Summary

| 항목 | 내용 |
|------|------|
| Feature | english-version |
| 목적 | 한국어 파이프라인과 병행하여 영어 Shorts 콘텐츠를 별도 채널에 자동 업로드 |
| 전략 | 한국 낮 시간(KST 9-21시) → 한국어 업로드 / 미국 낮 시간(EST 9-21시) → 영어 업로드 |

### Value Delivered

| 관점 | 내용 |
|------|------|
| Problem | 현재 파이프라인은 한국어만 지원 → 영어권 시장 완전 미개척 |
| Solution | `LANGUAGE` 환경변수로 언어 분기 + 영어 전용 GitHub Actions 워크플로우 추가 |
| Function UX Effect | 기존 코드 최소 수정으로 영어 채널 자동화 → 대시보드에서 두 채널 함께 관리 |
| Core Value | 미국 황금 시간대(EST 9-21시) 업로드로 글로벌 조회수 확보 |

---

## 1. 요구사항

### 1.1 언어 분기 설계
- `LANGUAGE` 환경변수: `ko` (기본값, 기존 동작 유지) / `en` (영어 모드)
- 영어 모드 활성화 시:
  - Claude 프롬프트 → 영어 스크립트 생성
  - ElevenLabs → 영어 최적화 음성(Rachel, `21m00Tcm4TlvDq8ikWAM`)
  - YouTube 업로드 → `YOUTUBE_TOKEN_EN` 시크릿 사용 (영어 전용 채널)
  - 업로드 타이틀 prefix: `[One Minute Economy] ` (한국어: `[일분 경제] `)

### 1.2 스케줄 전략 (한/영 병행)
| 언어 | 타겟 시청자 | 업로드 시간 | UTC 기준 |
|------|------------|------------|---------|
| 한국어(KO) | 한국 (KST) | KST 9-21시 | UTC 0-12시 |
| 영어(EN) | 미국 동부 (EST) | EST 12-21시 | UTC 17-02시 |

- 두 파이프라인은 독립 실행 → 겹침 없음
- 영어 스케줄은 별도 Supabase settings 키로 관리 (`upload_schedule_enabled_en`, `upload_schedule_days_en`, `upload_schedule_slots_en`)

### 1.3 커리큘럼 (영어)
- `topics` 테이블 기존 `title_en` 컬럼 재활용
- `title_en`이 없는 경우 Claude가 `title`을 영어로 번역하여 스크립트 작성
- `description`도 영어로 번역하여 프롬프트에 주입

### 1.4 뉴스 (영어)
- RSS 피드를 영어 소스로 교체: Reuters, AP News, Bloomberg RSS
- `news_items` 테이블에 `language` 컬럼 추가 (`ko` / `en`)
- 영어 뉴스 스크립트는 현지화 없이 원문 기반으로 영어로 직접 생성

---

## 2. 구현 범위

### Phase 1: 코어 언어 분기 (최우선)
- [ ] `src/script_generator.py` — `LANGUAGE=en`이면 영어 프롬프트 사용
- [ ] `src/news_script_generator.py` — `LANGUAGE=en`이면 영어 프롬프트 사용
- [ ] `src/tts_generator.py` — `LANGUAGE=en`이면 Rachel 음성 사용
- [ ] `src/youtube_uploader.py` — `LANGUAGE=en`이면 `YOUTUBE_TOKEN_EN` + 영어 prefix

### Phase 2: 스케줄 게이트 (영어용)
- [ ] `src/settings_manager.py` — `check_should_run_en()`, `check_news_should_run_en()` 추가
  - `upload_schedule_enabled_en`, `upload_schedule_days_en`, `upload_schedule_slots_en` 읽기
  - EST → UTC 변환: `(h + 5) % 24` (EST, 서머타임 미적용 기준)
- [ ] `main.py` / `news_main.py` — `LANGUAGE=en`이면 영어 스케줄 게이트 호출

### Phase 3: GitHub Actions 워크플로우
- [ ] `.github/workflows/daily_shorts_en.yml` — `LANGUAGE=en`, `YOUTUBE_TOKEN_EN` 사용
- [ ] `.github/workflows/news_shorts_en.yml` — `LANGUAGE=en`, `YOUTUBE_TOKEN_EN` 사용
- [ ] 영어 아웃트로 assets 캐시 키: `outro-assets-en-v1`

### Phase 4: 영어 뉴스 RSS
- [ ] `src/news_fetcher.py` — `LANGUAGE` 파라미터로 RSS 피드 분기
  - 영어 기본 피드: Reuters, AP News Top Stories
- [ ] `news_items` 테이블 `language` 컬럼 추가 (supabase_schema.sql 업데이트)
- [ ] `news_main.py` — 영어 모드 시 `get_next_news(language='en')` 호출

### Phase 5: 대시보드 (영어 설정)
- [ ] `docs/index.html` — 설정 탭에 영어 스케줄 섹션 추가
  - `upload_schedule_enabled_en`, `upload_schedule_days_en`, `upload_schedule_slots_en`
- [ ] 뉴스 리스트에 언어 배지(🇰🇷 / 🇺🇸) 표시

---

## 3. 기술 상세

### 3.1 언어별 TTS 음성
| 언어 | Voice | Voice ID | 특징 |
|------|-------|----------|------|
| 한국어 | Adam | `pNInz6obpgDQGcFmaJgB` | 현재 사용 중, 다국어 지원 |
| 영어 | Rachel | `21m00Tcm4TlvDq8ikWAM` | 자연스러운 미국 영어, 교육 콘텐츠 적합 |

- 모델: `eleven_multilingual_v2` (변경 없음)

### 3.2 영어 스크립트 생성 프롬프트 요구사항
```
- Target: 20-30s learning economics for the first time
- Segments: 6-8 per topic
- Narration: 10-20 words per segment (short, punchy)
- Tone: conversational, friendly (not textbook)
- Good examples: "Here's the thing..." / "Think of it this way..." / "So basically..."
- Bad examples: "It represents..." / "It indicates..." (too formal)
- Image prompts: English only (same as KO version)
```

### 3.3 영어 YouTube 설정
- 채널: 별도 영어 채널 (새로 생성 또는 기존 채널 활용)
- 시크릿: `YOUTUBE_TOKEN_EN` (OAuth2 token.json)
- 업로드 타이틀 prefix:
  - 커리큘럼: `[One Minute Economy] `
  - 뉴스: `[One Minute News] `

### 3.4 설정 키 (Supabase settings 테이블)
| 키 | 설명 | 기본값 |
|----|------|--------|
| `upload_schedule_enabled_en` | 영어 채널 자동화 on/off | `false` |
| `upload_schedule_days_en` | 업로드 요일 | `everyday` |
| `upload_schedule_slots_en` | 업로드 시간 슬롯 (EST 기준) | `[]` |
| `upload_news_enabled_en` | 영어 뉴스 on/off | `false` |

### 3.5 서머타임(DST) 처리
- EST (UTC-5): 11월~3월
- EDT (UTC-4): 3월~11월
- 단순화: `python-dateutil` 또는 `pytz` 사용하여 `US/Eastern` 타임존으로 정확 처리
- 기존 KST 처리와 동일한 방식 적용

---

## 4. DB 변경

### 4.1 news_items 테이블
```sql
ALTER TABLE news_items ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'ko';
CREATE INDEX IF NOT EXISTS idx_news_language ON news_items(language, status, interest_score DESC);
```

### 4.2 Supabase settings (추가 키)
```
upload_schedule_enabled_en = false
upload_schedule_days_en    = everyday
upload_schedule_slots_en   = []
upload_news_enabled_en     = false
```

---

## 5. 구현 순서

1. `src/script_generator.py` — 영어 프롬프트 분기
2. `src/news_script_generator.py` — 영어 프롬프트 분기
3. `src/tts_generator.py` — 영어 음성 분기
4. `src/youtube_uploader.py` — 토큰/prefix 분기
5. `src/settings_manager.py` — 영어 스케줄 게이트 추가
6. `main.py` / `news_main.py` — `LANGUAGE` 분기 적용
7. `.github/workflows/daily_shorts_en.yml` 생성
8. `.github/workflows/news_shorts_en.yml` 생성
9. `src/news_fetcher.py` — 영어 RSS 피드 + language 컬럼
10. `supabase_schema.sql` — news_items language 컬럼 추가
11. `docs/index.html` — 영어 설정 UI + 언어 배지

---

## 6. GitHub Secrets 추가 필요

| Secret | 설명 |
|--------|------|
| `YOUTUBE_TOKEN_EN` | 영어 채널 OAuth2 token.json |

---

## 7. 리스크 및 고려사항

| 리스크 | 대응 |
|--------|------|
| 영어 채널 YouTube OAuth 토큰 만료 | 기존 KO 채널과 동일한 갱신 절차 |
| ElevenLabs 크레딧 2배 소비 | 영어 모드 별도 on/off로 필요 시만 활성화 |
| DST(서머타임) 오차 | pytz `US/Eastern` 타임존으로 정확 처리 |
| `topics` 테이블 `title_en` 누락 | Claude가 `title`(한국어) → 영어 번역 fallback |
| 영어 스크립트 품질 | 프롬프트에 예시 나레이션 포함, 초기 수동 검토 권장 |
