"""
뉴스 Shorts 자동 생성 파이프라인
커리큘럼(main.py)과 완전 분리 — 별도 GitHub Actions 워크플로우로 실행
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

from src.news_fetcher        import (fetch_rss_items, save_new_items, get_next_news,
                                      get_next_high_interest_news, refresh_and_fetch_news,
                                      mark_news_in_progress, mark_news_done, mark_news_pending,
                                      mark_news_failed, delete_old_news, get_news_settings,
                                      get_news_by_id)
from src.news_script_generator import generate_news_script
from src.image_generator      import generate_all_images
from src.tts_generator        import generate_segments_tts
from src.video_composer       import compose_video
from src.youtube_uploader     import upload_shorts, get_next_optimal_time
from src.settings_manager     import check_news_should_run, get_settings, get_content_language

load_dotenv()


def main():
    # ── 0. 자동 실행 체크 ─────────────────────────────
    if not check_news_should_run():
        sys.exit(0)

    settings     = get_settings()
    language     = get_content_language()
    ts           = datetime.now().strftime('%Y%m%d_%H%M%S')
    work_dir     = f'output/news_{ts}'
    os.makedirs(work_dir, exist_ok=True)
    lang_flag = '🇺🇸' if language == 'en' else '🇰🇷'
    print(f'{lang_flag} 콘텐츠 언어: {language.upper()}')

    news_settings = get_news_settings()
    max_per_feed  = int(news_settings.get('news_max_per_feed', 5))
    schedule_on   = settings.get('upload_schedule_enabled', 'false').lower() == 'true'

    # NEWS_ID 지정 여부를 먼저 확인 — 있으면 RSS 수집/삭제 전체 건너뜀
    news_id_override = os.environ.get('NEWS_ID', '').strip()

    # ── 1. RSS 수집 + 관심도 채점 + DB 저장 ──────────
    if news_id_override:
        # 특정 뉴스 직접 지정 시: pending 삭제나 RSS 재수집 없이 바로 진행
        print(f'📌 특정 뉴스 ID 지정 — RSS 수집 건너뜁니다 ({news_id_override})')
    elif schedule_on:
        # 예약 발행 모드: pending 뉴스 전체 삭제 후 최신 뉴스 재수집
        print('🔄 예약 발행 모드: 최신 뉴스 실시간 수집 중...')
        refresh_and_fetch_news(max_per_feed=max_per_feed)
    else:
        print('📰 뉴스 RSS 수집 중...')
        items = fetch_rss_items(max_per_feed=max_per_feed)
        saved = save_new_items(items)
        print(f'   총 {len(items)}건 수집 / {saved}건 신규 저장')

        # ── 1-1. 오래된 뉴스 자동 삭제 (일반 모드만) ─────
        delete_days = int(news_settings.get('news_delete_days', 0))
        if delete_days > 0:
            deleted = delete_old_news(delete_days)
            if deleted:
                print(f'   🗑️  {delete_days}일 이상 된 뉴스 {deleted}건 삭제')

    news = None

    try:
        # ── 2. 다음 처리할 뉴스 선택 ──────────────────────
        if news_id_override:
            news = get_news_by_id(news_id_override)
            if news:
                print(f'📌 지정된 뉴스: {news["title"]}')
            else:
                print(f'⚠️  지정된 뉴스 ID를 찾을 수 없음: {news_id_override} — 자동 선택으로 전환')
        if not news:
            if schedule_on:
                news = get_next_high_interest_news()  # high → medium → any 우선순위
            else:
                news = get_next_news()
        if not news:
            print('📭 처리할 뉴스가 없습니다. 내일 다시 시도합니다.')
            sys.exit(0)
        print(f'📌 선택된 뉴스: {news["title"]}')
        print(f'   출처: {news["source"]} | {news.get("published_at","")[:10]}')
        mark_news_in_progress(news['id'])

        # ── 3. 스크립트 생성 ──────────────────────────────
        print('✍️  뉴스 스크립트 생성 중...')
        script   = generate_news_script(news, language=language)
        segments = script['segments']
        print(f'   제목: {script["title"]}')

        # ── 4. 이미지 생성 ────────────────────────────────
        print(f'🎨 이미지 생성 중... ({len(segments)}장)')
        img_dir     = os.path.join(work_dir, 'images')
        image_paths = generate_all_images(segments, img_dir)
        for seg, img_path in zip(segments, image_paths):
            seg['image_path'] = img_path

        # ── 5. TTS 생성 ───────────────────────────────────
        print(f'🎙️  TTS 생성 중... ({len(segments)}개)')
        tts_dir     = os.path.join(work_dir, 'audio')
        tts_results = generate_segments_tts(segments, tts_dir, language=language)
        for seg, tts in zip(segments, tts_results):
            seg['audio_path'] = tts['audio_path']

        # ── 6. 영상 합성 ──────────────────────────────────
        seg_preview = " / ".join(s["narration"][:8] for s in segments)
        print(f'🎬 영상 합성 중... (총 {len(segments)}개 세그먼트: {seg_preview})')
        video_path = os.path.join(work_dir, 'video.mp4')
        compose_video(segments, script['title'], video_path)

        # ── 7. YouTube 업로드 ─────────────────────────────
        print('📤 YouTube 업로드 중...')
        try:
            publish_at = None
            if news_id_override:
                # 수동 진행 버튼 → 예약 없이 즉시 공개
                print('   ⚡ 수동 실행 — 즉시 공개 업로드')
            elif settings.get('upload_schedule_enabled', 'false').lower() == 'true':
                publish_at = get_next_optimal_time(
                    days_str   = settings.get('upload_schedule_days', 'everyday'),
                    slots_json = settings.get('upload_schedule_slots', '[]'),
                    category   = 'news',
                )
                print(f'   📅 예약 발행 설정: {publish_at} (UTC)')
            title_prefix = '[One Minute News] ' if language == 'en' else '[일분 뉴스] '
            video_id = upload_shorts(video_path, script,
                                     youtube_title_prefix=title_prefix,
                                     publish_at=publish_at,
                                     language=language)
        except Exception as e:
            err = str(e)
            print(f'❌ 업로드 실패: {err}')
            mark_news_pending(news['id'])
            if 'uploadLimitExceeded' in err:
                print('⚠️  YouTube 일일 업로드 한도 초과. https://www.youtube.com/verify')
            sys.exit(1)
        print(f'✅ 업로드 완료: https://youtube.com/shorts/{video_id}')

        # ── 8. DB 업데이트 ────────────────────────────────
        mark_news_done(news['id'], video_id)
        print('💾 완료!')

    except SystemExit:
        raise
    except Exception as e:
        err = str(e)
        if 'usage' in err.lower() and ('limit' in err.lower() or '400' in err):
            print(f'⏸️  Anthropic API 한도 초과 — 뉴스를 pending 상태로 되돌립니다.')
            print(f'   복구 예정: {err}')
            if news:
                mark_news_pending(news['id'])  # failed 대신 pending으로 복귀
            sys.exit(0)
        print(f'❌ 파이프라인 오류: {e}')
        if news:
            mark_news_failed(news['id'])
        raise


if __name__ == '__main__':
    main()
