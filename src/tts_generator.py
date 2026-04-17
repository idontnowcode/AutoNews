import os
import requests

DEFAULT_VOICE_ID = 'pNInz6obpgDQGcFmaJgB'  # Adam (multilingual) — Korean
EN_VOICE_ID      = '21m00Tcm4TlvDq8ikWAM'  # Rachel — natural American English


def get_voice_id(language: str = 'ko') -> str:
    """언어에 맞는 ElevenLabs Voice ID 반환"""
    return EN_VOICE_ID if language == 'en' else DEFAULT_VOICE_ID


def generate_tts(text: str, output_path: str,
                 voice_id: str = DEFAULT_VOICE_ID) -> str:
    """ElevenLabs TTS → MP3 파일 저장"""
    url = f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}'
    headers = {
        'xi-api-key':   os.environ['ELEVENLABS_API_KEY'],
        'Content-Type': 'application/json',
    }
    payload = {
        'text': text,
        'model_id': 'eleven_multilingual_v2',
        'voice_settings': {
            'stability':         0.55,
            'similarity_boost':  0.75,
            'style':             0.30,
            'use_speaker_boost': True
        }
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    if resp.status_code == 401:
        raise RuntimeError(
            'ElevenLabs 인증 실패 (401). '
            'GitHub Secrets의 ELEVENLABS_API_KEY를 확인/재발급하세요. '
            '발급: https://elevenlabs.io → Profile → API Keys'
        )
    resp.raise_for_status()
    with open(output_path, 'wb') as f:
        f.write(resp.content)
    return output_path


def generate_segments_tts(segments: list, out_dir: str, language: str = 'ko') -> list:
    """세그먼트별 TTS 생성 → [(audio_path, narration), ...] 반환.
    세그먼트에 audio_path 가 이미 설정돼 있으면 해당 파일을 그대로 사용 (고정 asset 재사용).
    language: 'ko' → Adam 음성 / 'en' → Rachel 음성
    """
    os.makedirs(out_dir, exist_ok=True)
    voice_id = get_voice_id(language)
    results = []
    for seg in segments:
        idx       = seg['index']
        narration = seg['narration']

        # 이미 경로가 주입된 고정 asset → TTS 생성 건너뜀
        if seg.get('audio_path') and os.path.exists(seg['audio_path']):
            print(f'   TTS 스킵 [{idx}]: 고정 asset 사용')
            results.append({'audio_path': seg['audio_path'], 'narration': narration, 'index': idx})
            continue

        path = os.path.join(out_dir, f'audio_{idx:02d}.mp3')
        print(f'   TTS [{idx+1}/{len(segments)}]: {narration[:35]}...')
        generate_tts(narration, path, voice_id=voice_id)
        results.append({'audio_path': path, 'narration': narration, 'index': idx})
    return results
