"""
DALL-E 3로 슬라이드 배경 이미지 생성 (1024×1792 세로형)
"""
import os
import requests
from openai import OpenAI

client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])

BASE_STYLE = (
    "minimalist flat design illustration, dark navy blue background (#0D1B3E), "
    "clean professional finance infographic style, subtle geometric shapes, "
    "soft glow accents in sky blue and indigo, no text, no letters, no words"
)


def generate_slide_image(prompt: str, output_path: str) -> str:
    """DALL-E 3로 이미지 생성 후 로컬 저장"""
    full_prompt = f"{prompt}, {BASE_STYLE}"

    response = client.images.generate(
        model="dall-e-3",
        prompt=full_prompt,
        size="1024x1792",   # 9:16 세로형
        quality="standard",
        n=1,
    )
    image_url = response.data[0].url

    # 다운로드
    img_data = requests.get(image_url, timeout=30).content
    with open(output_path, 'wb') as f:
        f.write(img_data)

    return output_path


def generate_all_images(segments: list, out_dir: str) -> list:
    """세그먼트 리스트에서 dalle_prompt 추출해 전체 이미지 생성"""
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for seg in segments:
        idx    = seg.get('index', len(paths))
        prompt = seg.get('dalle_prompt', 'abstract finance concept visualization')
        path   = os.path.join(out_dir, f'image_{idx:02d}.png')
        print(f'   이미지 생성 중 [{idx+1}/{len(segments)}]: {prompt[:60]}...')
        generate_slide_image(prompt, path)
        paths.append(path)
    return paths
