import os
import sys
from datetime import datetime
from dotenv import load_dotenv

from src.topic_manager    import get_next_topic, mark_in_progress, mark_done, mark_pending, mark_failed, save_video
from src.settings_manager import check_should_run, get_settings
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
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs('output', exist_ok=True)
    work_dir = f'output/{ts}'
    os.makedirs(work_dir, exist_ok=True)
    topic = None

    try:
        # ── 1. 주제 선택 ───────────────────────────────────
        print('📚 다음 주제 선택 중...')
        topic = get_next_topic()
        print(f'   [{topic["level"]}] {topic["title"]} ({topic["category"]})')
        mark_in_progress(topic['id'])

        # ── 2. 스크립트 생성 ───────────────────────────────
        print('✍️  스크립트 생성 중...')
        script = generate_script(topic)
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
        tts_results = generate_segments_tts(segments, tts_dir)
        for seg, tts in zip(segments, tts_results):
            seg['audio_path'] = tts['audio_path']

        # ── 5. 영상 합성 ───────────────────────────────────
        print('🎬 영상 합성 중...')
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
            video_id = upload_shorts(video_path, script, youtube_title_prefix='[일분 경제] ',
                                     publish_at=publish_at)
        except Exception as e:
            err = str(e)
            print(f'❌ 업로드 실패: {err}')
            mark_pending(topic['id'])
            if 'uploadLimitExceeded' in err:
                print('⚠️  YouTube 일일 업로드 한도 초과.')
                print('   해결: https://www.youtube.com/verify 에서 채널 인증 후 재시도')
            sys.exit(1)
        print(f'✅ 업로드 완료: https://youtube.com/shorts/{video_id}')

        # ── 7. DB 저장 ────────────────────────────────────
        print('💾 DB 저장 중...')
        slide_prompts = [s.get('image_prompt') or s.get('dalle_prompt', '') for s in segments]
        save_video(topic['id'], video_id, script, slide_prompts)
        mark_done(topic['id'])
        print('   완료!')

    except SystemExit:
        raise
    except Exception as e:
        print(f'❌ 파이프라인 오류: {e}')
        if topic:
            mark_failed(topic['id'])
        raise


if __name__ == '__main__':
    main()
