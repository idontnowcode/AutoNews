"""
아웃트로 고정 asset 생성 (최초 1회만 실행)
생성 결과: assets/outro_image.png, assets/outro_audio.mp3

실행 방법:
    python tools/generate_outro_assets.py
"""
import os
import sys

# 프로젝트 루트를 경로에 추가 (import보다 먼저)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

# .env 파일을 프로젝트 루트 기준으로 명시적으로 로드
from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, '.env'))

from src.script_generator import OUTRO_NARRATION, OUTRO_IMAGE_PROMPT, OUTRO_IMAGE, OUTRO_AUDIO
from src.image_generator   import generate_slide_image
from src.tts_generator     import generate_tts

os.makedirs(os.path.dirname(OUTRO_IMAGE), exist_ok=True)


def generate():
    # ── 이미지 ─────────────────────────────────────────────────────
    if os.path.exists(OUTRO_IMAGE):
        print(f'✅ 이미지 이미 존재: {OUTRO_IMAGE}')
    else:
        print(f'🎨 아웃트로 이미지 생성 중...')
        generate_slide_image(OUTRO_IMAGE_PROMPT, OUTRO_IMAGE)
        print(f'   저장: {OUTRO_IMAGE}')

    # ── TTS ────────────────────────────────────────────────────────
    if os.path.exists(OUTRO_AUDIO):
        print(f'✅ 오디오 이미 존재: {OUTRO_AUDIO}')
    else:
        print(f'🎙️  아웃트로 TTS 생성 중...')
        print(f'   멘트: {OUTRO_NARRATION}')
        generate_tts(OUTRO_NARRATION, OUTRO_AUDIO)
        print(f'   저장: {OUTRO_AUDIO}')

    print('\n✅ 아웃트로 asset 준비 완료!')
    print('   이제 모든 영상 말미에 이 이미지/사운드가 고정으로 사용됩니다.')
    print('   멘트를 바꾸려면 src/script_generator.py의 OUTRO_NARRATION을 수정 후 재실행하세요.')


if __name__ == '__main__':
    generate()
