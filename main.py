import os
import sys
from datetime import datetime
from dotenv import load_dotenv

from src.topic_manager    import get_next_topic, mark_in_progress, mark_done, mark_pending, mark_failed, save_video
from src.settings_manager import check_should_run, get_settings, get_content_language
from src.pipeline_logger  import log_error, log_warning, log_success
from src.script_generator import generate_script
from src.image_generator  import generate_all_images
from src.tts_generator    import generate_segments_tts
from src.video_composer   import compose_video
from src.youtube_uploader import upload_shorts, get_next_optimal_time

load_dotenv()


def main():
    # ── 0. 자동 업로드 설정 체크 ──────────────────────
    if not check_should_run():
        sys.exit(0)

    settings = get_settings()
    language = get_content_language()
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs('output', exist_ok=True)
    work_dir = f'output/{ts}'
    os.makedirs(work_dir, exist_ok=True)
    topic = None
    lang_flag = '🇺🇸' if language == 'en' else '🇰🇷'
    print(f'{lang_flag} 콘텐츠 언어: {language.upper()}')

    try:
        # ── 1. 주제 선택 ───────────────────────────────────
        print('📚 다음 주제 선택 중...')
        topic = get_next_topic()
        print(f'   [{topic["level"]}] {topic["title"]} ({topic["category"]})')
        mark_in_progress(topic['id'])

        # ── 2. 스크립트 생성 ───────────────────────────────
        print('✍️  스크립트 생성 중...')
        script = generate_script(topic, language=language)
        print(f'   제목: {script["title"]}')
        segments = script['segments']

        # ── 3. DALL-E 이미지 생성 ──────────────────────────
        print(f'🎨 DALL-E 3 이미지 생성 중... ({len(segments)}장)')
        img_dir     = os.path.join(work_dir, 'images')
        image_paths = generate_all_images(segments, img_dir)
        for seg, img_path in zip(segments, image_paths):
            seg['image_path'] = img_path

        # ── 4. 세그먼트별 TTS 생성 ────────────────────────
        print(f'🎙️  TTS 생성 중... ({len(segments)}개 세그먼트)')
        tts_dir     = os.path.join(work_dir, 'audio')
        tts_results = generate_segments_tts(segments, tts_dir, language=language)
        for seg, tts in zip(segments, tts_results):
            seg['audio_path']   = tts['audio_path']
            seg['audio_chunks'] = tts['audio_chunks']

        # ── 5. 영상 합성 ───────────────────────────────────
        seg_preview = " / ".join(s["narration"][:8] for s in segments)
        print(f'🎬 영상 합성 중... (총 {len(segments)}개 세그먼트: {seg_preview})')
        video_path = os.path.join(work_dir, 'video.mp4')
        compose_video(segments, script['title'], video_path)

        # ── 6. YouTube 업로드 ──────────────────────────────
        print('📤 YouTube 업로드 중...')
        try:
            publish_at = None
            if settings.get('upload_schedule_enabled', 'false').lower() == 'true':
                publish_at = get_next_optimal_time(
                    days_str   = settings.get('upload_schedule_days', 'everyday'),
                    slots_json = settings.get('upload_schedule_slots', '[]'),
                    category   = 'curriculum',
                )
                print(f'   📅 예약 발행 설정: {publish_at} (UTC)')
            title_prefix = '[One Minute Economy] ' if language == 'en' else '[일분 경제] '
            video_id = upload_shorts(video_path, script,
                                     youtube_title_prefix=title_prefix,
                                     publish_at=publish_at,
                                     language=language)
        except Exception as e:
            err = str(e)
            print(f'❌ 업로드 실패: {err}')
            mark_pending(topic['id'])
            if 'uploadLimitExceeded' in err:
                print('⚠️  YouTube 일일 업로드 한도 초과.')
                print('   해결: https://www.youtube.com/verify 에서 채널 인증 후 재시도')
                log_warning('curriculum', 'YouTube 일일 업로드 한도 초과',
                            error_type='upload_limit', topic_id=topic['id'])
            else:
                log_error('curriculum', e, topic_id=topic['id'],
                          context={'step': 'youtube_upload'})
            sys.exit(1)
        print(f'✅ 업로드 완료: https://youtube.com/shorts/{video_id}')

        # ── 7. DB 저장 ────────────────────────────────────
        print('💾 DB 저장 중...')
        slide_prompts = [s.get('image_prompt') or s.get('dalle_prompt', '') for s in segments]
        save_video(topic['id'], video_id, script, slide_prompts)
        mark_done(topic['id'])
        log_success('curriculum', f'업로드 완료: {script["title"]}', topic_id=topic['id'])
        print('   완료!')

    except SystemExit:
        raise
    except Exception as e:
        err = str(e)
        is_api_limit  = 'usage' in err.lower() and ('limit' in err.lower() or '400' in err)
        is_overloaded = '529' in err or 'overloaded' in err.lower()
        if is_api_limit or is_overloaded:
            reason = 'Anthropic API 과부하(529)' if is_overloaded else 'Anthropic API 한도 초과'
            print(f'⏸️  {reason} — 주제를 pending 상태로 되돌립니다.')
            print(f'   복구 예정: {err}')
            if topic:
                mark_pending(topic['id'])
            log_warning('curriculum', f'{reason}: {err[:200]}',
                        error_type='overloaded' if is_overloaded else 'api_limit',
                        topic_id=topic['id'] if topic else None)
            sys.exit(0)
        print(f'❌ 파이프라인 오류: {e}')
        if topic:
            mark_failed(topic['id'])
        log_error('curriculum', e, topic_id=topic['id'] if topic else None)
        raise


if __name__ == '__main__':
    main()
