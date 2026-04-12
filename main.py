import os
from datetime import datetime
from dotenv import load_dotenv

from src.topic_manager    import get_next_topic, mark_in_progress, mark_done, save_video
from src.script_generator import generate_script
from src.image_generator  import generate_all_images
from src.tts_generator    import generate_tts
from src.video_composer   import compose_video
from src.youtube_uploader import upload_shorts

load_dotenv()


def main():
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs('output', exist_ok=True)

    print('📚 다음 주제 선택 중...')
    topic = get_next_topic()
    print(f'   주제: [{topic["level"]}] {topic["title"]} ({topic["category"]})')
    mark_in_progress(topic['id'])

    print('✍️  스크립트 생성 중...')
    script = generate_script(topic)
    print(f'   제목: {script["title"]}')

    print('🎨 DALL-E 3 이미지 생성 중... (슬라이드 4장)')
    img_dir     = f'output/images_{ts}'
    image_paths = generate_all_images(script['slides'], img_dir)

    print('🎙️  TTS 나레이션 생성 중...')
    audio_path = f'output/audio_{ts}.mp3'
    generate_tts(script['narration'], audio_path)

    print('🎬 영상 합성 중...')
    video_path = f'output/video_{ts}.mp4'
    compose_video(image_paths, audio_path, video_path)

    print('📤 YouTube 업로드 중...')
    video_id = upload_shorts(video_path, script)
    print(f'✅ 업로드 완료: https://youtube.com/shorts/{video_id}')

    print('💾 DB 저장 중...')
    slide_prompts = [s.get('dalle_prompt', '') for s in script['slides']]
    save_video(topic['id'], video_id, script, slide_prompts)
    mark_done(topic['id'])
    print('   완료!')


if __name__ == '__main__':
    main()
