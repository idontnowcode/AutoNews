# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**경제 교육 YouTube Shorts 자동화** — Claude + DALL-E 3 + ElevenLabs로 경제 교육 콘텐츠를 매일 자동 생성·업로드하는 파이프라인.

## 아키텍처

```
Supabase topics DB → 다음 주제 선택
    ↓
Claude Sonnet → 교육 스크립트 + DALL-E 프롬프트 생성
    ↓
DALL-E 3 → 슬라이드 이미지 4장 (1024×1792, 세로형)
    ↓
ElevenLabs → TTS 나레이션 MP3
    ↓
MoviePy → 영상 합성 (1080×1920 MP4)
    ↓
YouTube Data API v3 → Shorts 업로드
    ↓
Supabase → 영상 기록 저장, 주제 status=done, 자동 주제 확장
```

## 파일 구조

```
src/
  db_client.py        # Supabase 클라이언트
  topic_manager.py    # 주제 선택/확장/DB 저장
  script_generator.py # Claude 교육 스크립트 생성
  image_generator.py  # DALL-E 3 슬라이드 이미지 생성
  tts_generator.py    # ElevenLabs TTS
  video_composer.py   # MoviePy 영상 합성
  youtube_uploader.py # YouTube 업로드
main.py               # 파이프라인 진입점
supabase_schema.sql   # DB 스키마 (최초 1회 Supabase에서 실행)
```

## Supabase DB 스키마

- **topics**: id, title, title_en, level(basic/intermediate/advanced), category, description, prerequisites[], related_topics[], status(pending/in_progress/done), order_index
- **videos**: id, topic_id, youtube_id, title, subtitle, narration, script_json, slide_prompts, created_at, published_at

## 커리큘럼 로직

- prerequisites가 모두 done인 주제 중 order_index 최소값 선택
- pending 주제가 소진되면 Claude가 자동으로 10개씩 확장
- 카테고리: 거시경제, 투자, 금융시장, 재정, 국제경제, 행동경제학

## 로컬 개발

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env         # API 키 입력
python main.py
```

## GitHub Secrets (6개)

| Secret | 설명 |
|--------|------|
| ANTHROPIC_API_KEY | Claude API |
| OPENAI_API_KEY | DALL-E 3 |
| SUPABASE_URL | Supabase 프로젝트 URL |
| SUPABASE_KEY | Supabase anon key |
| ELEVENLABS_API_KEY | TTS |
| YOUTUBE_TOKEN | OAuth2 token.json 전체 내용 |

## bkit Framework

- Level: **Dynamic** (fullstack with backend)
- PDCA state: `.bkit/state/pdca-status.json`
- `/pdca plan {feature}` → `/pdca design` → `/pdca analyze` → `/pdca report`
