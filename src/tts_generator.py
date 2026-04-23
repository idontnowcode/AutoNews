import os
import re
import subprocess
import requests

DEFAULT_VOICE_ID = 'pNInz6obpgDQGcFmaJgB'  # Adam (multilingual) — Korean
EN_VOICE_ID      = '21m00Tcm4TlvDq8ikWAM'  # Rachel — natural American English


TTS_SPEED = 1.2  # 음성 재생 속도 배율 (ffmpeg atempo)


def _speedup_audio(path: str, speed: float = TTS_SPEED) -> None:
    """ffmpeg atempo 필터로 오디오 속도를 speed 배율로 조정 (in-place)."""
    tmp = path + '.tmp.mp3'
    subprocess.run(
        ['ffmpeg', '-y', '-i', path, '-filter:a', f'atempo={speed}', tmp],
        check=True, capture_output=True
    )
    os.replace(tmp, path)


def split_narration_chunks(narration: str, max_chars: int = 16) -> list:
    """나레이션을 자막 단위로 자연스럽게 분할.

    분할 우선순위:
      1. 마침표·느낌표·물음표·쉼표 뒤 → 항상 분할
      2. 분할 후에도 max_chars(공백 제외) 초과 시 → 글자 수 기준 균등 분할
         (절반 위치에 가장 가까운 단어 경계를 찾아 분할)
    """
    # 구두점 뒤에서 분할 (구두점 자체는 앞 조각에 포함)
    raw_parts = re.split(r'(?<=[.!?。！？,，、])\s*', narration.strip())
    raw_parts = [p.strip() for p in raw_parts if p.strip()]

    result = []
    for p in raw_parts:
        if len(p.replace(' ', '')) <= max_chars:
            result.append(p)
            continue

        # 너무 길면 글자 수 기준 균등 이분할
        words = p.split()
        if len(words) <= 1:
            result.append(p)
            continue

        total_chars = sum(len(w) for w in words)
        half, cum, split_idx = total_chars / 2, 0, max(1, len(words) // 2)
        for i, w in enumerate(words):
            cum += len(w)
            if cum >= half:
                split_idx = i + 1
                break

        chunk1 = ' '.join(words[:split_idx])
        chunk2 = ' '.join(words[split_idx:])
        if chunk1:
            result.append(chunk1)
        if chunk2:
            result.append(chunk2)

    return result or [narration]


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
    """세그먼트별 TTS 생성.
    나레이션을 자막 단위로 분할하여 청크별 TTS 파일을 생성한다.
    반환값: [{'audio_path', 'narration', 'index', 'audio_chunks'}, ...]
      audio_chunks: [{'text': str, 'audio_path': str}, ...]
    """
    os.makedirs(out_dir, exist_ok=True)
    voice_id = get_voice_id(language)
    results = []
    for seg in segments:
        idx       = seg['index']
        narration = seg['narration']

        # 이미 경로가 주입된 고정 asset → 분할 없이 그대로 사용
        if seg.get('audio_path') and os.path.exists(seg['audio_path']):
            print(f'   TTS 스킵 [{idx}]: 고정 asset 사용')
            audio_chunks = [{'text': narration, 'audio_path': seg['audio_path']}]
            results.append({'audio_path': seg['audio_path'], 'narration': narration,
                            'index': idx, 'audio_chunks': audio_chunks})
            continue

        # 나레이션 분할 → 청크별 TTS 생성
        chunks_text = split_narration_chunks(narration)
        audio_chunks = []
        for c_idx, chunk_text in enumerate(chunks_text):
            chunk_path = os.path.join(out_dir, f'audio_{idx:02d}_{c_idx:02d}.mp3')
            label = f'[{idx+1}/{len(segments)}] 청크{c_idx+1}/{len(chunks_text)}'
            print(f'   TTS {label}: {chunk_text[:35]}')
            generate_tts(chunk_text, chunk_path, voice_id=voice_id)
            _speedup_audio(chunk_path)
            audio_chunks.append({'text': chunk_text, 'audio_path': chunk_path})

        first_path = audio_chunks[0]['audio_path'] if audio_chunks else ''
        results.append({'audio_path': first_path, 'narration': narration,
                        'index': idx, 'audio_chunks': audio_chunks})
    return results
