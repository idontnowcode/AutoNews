import os
from datetime import datetime
from dotenv import load_dotenv

from src.news_collector   import collect_news
from src.script_generator import generate_script
from src.slide_creator     import create_slides
from src.tts_generator     import generate_tts
from src.video_composer    import compose_video
from src.youtube_uploader  import upload_shorts

load_dotenv()


def main():
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs('output', exist_ok=True)

    slides_dir = f'output/slides_{ts}'
    audio_path = f'output/audio_{ts}.mp3'
    video_path = f'output/video_{ts}.mp4'

    print('📰 Step 1: 뉴스 수집 중...')
    news = collect_news()

    print('✍️  Step 2: 스크립트 생성 중...')
    script = generate_script(news)
    print(f'   제목: {script["title"]}')

    print('🎨 Step 3: 슬라이드 이미지 생성 중...')
    image_paths = create_slides(script, slides_dir)
    print(f'   슬라이드 {len(image_paths)}장 생성 완료')

    print('🎙️  Step 4A: TTS 나레이션 생성 중...')
    generate_tts(script['narration'], audio_path)

    print('🎬 Step 4B: 영상 합성 중...')
    compose_video(image_paths, audio_path, video_path)

    print('📤 Step 5: YouTube 업로드 중...')
    video_id = upload_shorts(video_path, script)
    print(f'✅ 업로드 완료: https://youtube.com/shorts/{video_id}')


if __name__ == '__main__':
    main()
