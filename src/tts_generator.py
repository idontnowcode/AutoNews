import os
import requests

DEFAULT_VOICE_ID = 'pNInz6obpgDQGcFmaJgB'  # Adam (multilingual)


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
    resp.raise_for_status()
    with open(output_path, 'wb') as f:
        f.write(resp.content)
    return output_path


def generate_segments_tts(segments: list, out_dir: str) -> list:
    """세그먼트별 TTS 생성 → [(audio_path, narration), ...] 반환"""
    os.makedirs(out_dir, exist_ok=True)
    results = []
    for seg in segments:
        idx       = seg['index']
        narration = seg['narration']
        path      = os.path.join(out_dir, f'audio_{idx:02d}.mp3')
        print(f'   TTS [{idx+1}/{len(segments)}]: {narration[:30]}...')
        generate_tts(narration, path)
        results.append({'audio_path': path, 'narration': narration, 'index': idx})
    return results
