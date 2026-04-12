import os
import requests

# ElevenLabs 한국어 지원 Voice ID (변경 가능)
# 웹사이트에서 직접 들어보고 선택: https://elevenlabs.io/voice-library
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
