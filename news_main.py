"""
뉴스 Shorts 자동 생성 파이프라인
커리큘럼(main.py)과 완전 분리 — 별도 GitHub Actions 워크플로우로 실행
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

from src.news_fetcher        import (fetch_rss_items, save_new_items, get_next_news,
                                      mark_news_in_progress, mark_news_done, mark_news_pending)
from src.news_script_generator import generate_news_script
from src.image_generator      import generate_all_images
from src.tts_generator        import generate_segments_tts
from src.video_composer       import compose_video
from src.youtube_uploader     import upload_shorts

load_dotenv()


def main():
    ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
    work_dir = f'output/news_{ts}'
    os.makedirs(work_dir, exist_ok=True)

    # ── 1. RSS 수집 + DB 저장 ─────────────────────────
    print('📰 뉴스 RSS 수집 중...')
    items = fetch_rss_items()
    saved = save_new_items(items)
    print(f'   총 {len(items)}건 수집 / {saved}건 신규 저장')

    # ── 2. 다음 처리할 뉴스 선택 ──────────────────────
    news = get_next_news()
    if not news:
        print('📭 처리할 뉴스가 없습니다. 내일 다시 시도합니다.')
        sys.exit(0)
    print(f'📌 선택된 뉴스: {news["title"]}')
    print(f'   출처: {news["source"]} | {news.get("published_at","")[:10]}')
    mark_news_in_progress(news['id'])

    # ── 3. 스크립트 생성 ──────────────────────────────
    print('✍️  뉴스 스크립트 생성 중...')
    script   = generate_news_script(news)
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
    tts_results = generate_segments_tts(segments, tts_dir)
    for seg, tts in zip(segments, tts_results):
        seg['audio_path'] = tts['audio_path']

    # ── 6. 영상 합성 ──────────────────────────────────
    print('🎬 영상 합성 중...')
    video_path = os.path.join(work_dir, 'video.mp4')
    compose_video(segments, script['title'], video_path)

    # ── 7. YouTube 업로드 ─────────────────────────────
    print('📤 YouTube 업로드 중...')
    try:
        video_id = upload_shorts(video_path, script)
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


if __name__ == '__main__':
    main()
