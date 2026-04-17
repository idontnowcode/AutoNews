"""
아웃트로 고정 asset 생성 (최초 1회만 실행)
생성 결과: assets/outro_image.png, assets/outro_audio.mp3, assets/outro_audio_en.mp3

실행 방법:
    python tools/generate_outro_assets.py          # 한국어 + 영어 모두 생성
    python tools/generate_outro_assets.py --ko     # 한국어만
    python tools/generate_outro_assets.py --en     # 영어만
"""
import os
import sys

# 프로젝트 루트를 경로에 추가 (import보다 먼저)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

# .env 파일을 프로젝트 루트 기준으로 명시적으로 로드
from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, '.env'))

from src.script_generator import (OUTRO_NARRATION, OUTRO_NARRATION_EN,
                                   OUTRO_IMAGE_PROMPT, OUTRO_IMAGE,
                                   OUTRO_AUDIO, OUTRO_AUDIO_EN)
from src.image_generator   import generate_slide_image
from src.tts_generator     import generate_tts, DEFAULT_VOICE_ID, EN_VOICE_ID

os.makedirs(os.path.dirname(OUTRO_IMAGE), exist_ok=True)


def generate(mode: str = 'all'):
    # ── 이미지 (한/영 공용) ────────────────────────────────────────
    if os.path.exists(OUTRO_IMAGE):
        print(f'✅ 이미지 이미 존재: {OUTRO_IMAGE}')
    else:
        print('🎨 아웃트로 이미지 생성 중...')
        generate_slide_image(OUTRO_IMAGE_PROMPT, OUTRO_IMAGE)
        print(f'   저장: {OUTRO_IMAGE}')

    # ── 한국어 TTS ─────────────────────────────────────────────────
    if mode in ('all', 'ko'):
        if os.path.exists(OUTRO_AUDIO):
            print(f'✅ 한국어 오디오 이미 존재: {OUTRO_AUDIO}')
        else:
            print('🎙️  한국어 아웃트로 TTS 생성 중...')
            print(f'   멘트: {OUTRO_NARRATION}')
            generate_tts(OUTRO_NARRATION, OUTRO_AUDIO, voice_id=DEFAULT_VOICE_ID)
            print(f'   저장: {OUTRO_AUDIO}')

    # ── 영어 TTS ───────────────────────────────────────────────────
    if mode in ('all', 'en'):
        if os.path.exists(OUTRO_AUDIO_EN):
            print(f'✅ 영어 오디오 이미 존재: {OUTRO_AUDIO_EN}')
        else:
            print('🎙️  영어 아웃트로 TTS 생성 중...')
            print(f'   멘트: {OUTRO_NARRATION_EN}')
            generate_tts(OUTRO_NARRATION_EN, OUTRO_AUDIO_EN, voice_id=EN_VOICE_ID)
            print(f'   저장: {OUTRO_AUDIO_EN}')

    print('\n✅ 아웃트로 asset 준비 완료!')


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--ko' in args:
        generate('ko')
    elif '--en' in args:
        generate('en')
    else:
        generate('all')
