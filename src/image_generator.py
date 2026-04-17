"""
gpt-image-1 (GPT-4o 이미지)로 슬라이드 이미지 생성 (1024×1024)
"""
import os
import base64
import time
from openai import OpenAI, RateLimitError

_client = None

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
    return _client

BASE_STYLE = (
    "educational cartoon illustration, bright white background, "
    "colorful cute characters explaining the concept, "
    "vibrant colors, simple and clear layout, "
    "English labels only if text is needed, "
    "absolutely no Korean text, no Chinese text, no Japanese text, no Asian characters"
)

# gpt-image-1: 분당 5장 제한 → 장당 최소 12초 간격
_IMAGE_INTERVAL_SEC = 13


CARICATURE_STYLE = (
    "cartoon caricature illustration, bright white background, "
    "exaggerated facial features, bold outlines, flat colors, "
    "editorial cartoon style, no photorealism, no realistic rendering, "
    "absolutely no Korean text, no Asian characters"
)


def generate_slide_image(prompt: str, output_path: str) -> str:
    """gpt-image-1로 이미지 생성 후 로컬 저장 (base64 응답, rate limit 재시도)"""
    # 카리커처 프롬프트는 BASE_STYLE 대신 CARICATURE_STYLE 적용
    if 'caricature' in prompt.lower():
        full_prompt = f"{prompt}, {CARICATURE_STYLE}"
    else:
        full_prompt = f"{prompt}, {BASE_STYLE}"

    for attempt in range(5):
        try:
            response = _get_client().images.generate(
                model="gpt-image-1",
                prompt=full_prompt,
                size="1024x1024",
                quality="low",
                n=1,
            )
            img_data = base64.b64decode(response.data[0].b64_json)
            with open(output_path, 'wb') as f:
                f.write(img_data)
            return output_path
        except RateLimitError as e:
            wait = 15 * (attempt + 1)
            print(f'   Rate limit 도달, {wait}초 대기 후 재시도 ({attempt+1}/5)...')
            time.sleep(wait)

    raise RuntimeError(f'이미지 생성 실패 (5회 재시도 초과): {output_path}')


def generate_all_images(segments: list, out_dir: str) -> list:
    """세그먼트 리스트에서 dalle_prompt 추출해 전체 이미지 생성.
    세그먼트에 image_path 가 이미 설정돼 있으면 해당 경로를 그대로 반환 (고정 asset 재사용).
    """
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    gen_count = 0  # rate-limit sleep 은 실제 생성한 이미지 기준으로 카운트
    for i, seg in enumerate(segments):
        idx = seg.get('index', i)

        # 이미 경로가 주입된 고정 asset → 생성 건너뜀
        if seg.get('image_path') and os.path.exists(seg['image_path']):
            print(f'   이미지 스킵 [{i+1}/{len(segments)}]: 고정 asset 사용')
            paths.append(seg['image_path'])
            continue

        prompt = seg.get('image_prompt') or seg.get('dalle_prompt', 'abstract finance concept visualization')
        path   = os.path.join(out_dir, f'image_{idx:02d}.png')
        print(f'   이미지 생성 중 [{i+1}/{len(segments)}]: {prompt[:60]}...')
        if gen_count > 0:
            time.sleep(_IMAGE_INTERVAL_SEC)
        generate_slide_image(prompt, path)
        paths.append(path)
        gen_count += 1
    return paths
