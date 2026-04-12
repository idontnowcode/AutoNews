"""
gpt-image-1 (GPT-4o 이미지)로 슬라이드 이미지 생성 (1024×1024)
"""
import os
import base64
from openai import OpenAI

client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])

BASE_STYLE = (
    "educational cartoon illustration, bright white background, "
    "colorful cute characters explaining the concept, "
    "Korean webtoon style, vibrant colors, simple and clear layout, "
    "no English text, Korean labels are OK if needed"
)


def generate_slide_image(prompt: str, output_path: str) -> str:
    """gpt-image-1로 이미지 생성 후 로컬 저장 (base64 응답)"""
    full_prompt = f"{prompt}, {BASE_STYLE}"

    response = client.images.generate(
        model="gpt-image-1",
        prompt=full_prompt,
        size="1024x1024",
        quality="medium",
        n=1,
    )

    img_data = base64.b64decode(response.data[0].b64_json)
    with open(output_path, 'wb') as f:
        f.write(img_data)

    return output_path


def generate_all_images(segments: list, out_dir: str) -> list:
    """세그먼트 리스트에서 dalle_prompt 추출해 전체 이미지 생성"""
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for seg in segments:
        idx    = seg.get('index', len(paths))
        prompt = seg.get('image_prompt') or seg.get('dalle_prompt', 'abstract finance concept visualization')
        path   = os.path.join(out_dir, f'image_{idx:02d}.png')
        print(f'   이미지 생성 중 [{idx+1}/{len(segments)}]: {prompt[:60]}...')
        generate_slide_image(prompt, path)
        paths.append(path)
    return paths
