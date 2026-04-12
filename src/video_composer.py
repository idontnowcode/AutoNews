"""
영상 합성:
- Pillow로 각 세그먼트 프레임 합성 (검정 배경 + 노란 제목 + 이미지 + 흰 자막)
- MoviePy로 프레임 + 오디오 → MP4
- 나레이션 끝나면 다음 이미지로 전환
"""
import os
from PIL import Image, ImageDraw, ImageFont

try:
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
    MOVIEPY_V2 = False
except ModuleNotFoundError:
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
    MOVIEPY_V2 = True

W, H   = 1080, 1920
FPS    = 30
C_BLACK  = (0,   0,   0)
C_YELLOW = (255, 214,  10)
C_WHITE  = (255, 255, 255)

# 레이아웃 (상단 제목 → 이미지 → 하단 자막)
TITLE_TOP    = 120    # 제목 시작 Y (상단 여백 확보)
IMG_Y        = 360    # 이미지 시작 Y
IMG_SIZE     = 1080   # 이미지 크기 (정사각형, 1:1)
SUB_Y        = H - 340  # 자막 Y (하단에서 고정, 한 줄)


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf' if bold
            else '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
        '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
        '/usr/share/fonts/truetype/nanum/NanumGothicExtraBold.ttf',
        # Ubuntu 기본 폰트 (한글 미지원이지만 폴백용)
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold
            else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf' if bold
            else '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        'C:/Windows/Fonts/malgunbd.ttf' if bold else 'C:/Windows/Fonts/malgun.ttf',
        'C:/Windows/Fonts/malgun.ttf',
        'C:/Windows/Fonts/gulim.ttc',
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                print(f'[font] {path} (size={size})')
                return font
            except Exception:
                continue
    print(f'[font] WARNING: no truetype font found for size={size}, using default (text will be tiny!)')
    return ImageFont.load_default()


def _wrap_text(draw, text: str, font, max_width: int) -> list:
    words = text.split()
    lines, cur = [], ''
    for w in words:
        test = f'{cur} {w}'.strip()
        if draw.textlength(test, font=font) <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _draw_centered_text(draw, text: str, y: int, font, fill,
                        max_width: int, line_gap: int = 12) -> int:
    """중앙 정렬 여러 줄 텍스트, 다음 y 반환"""
    for line in _wrap_text(draw, text, font, max_width):
        lw = draw.textlength(line, font=font)
        draw.text(((W - lw) // 2, y), line, font=font, fill=fill)
        bbox = draw.textbbox((0, 0), line, font=font)
        y += (bbox[3] - bbox[1]) + line_gap
    return y


def make_frame(title: str, image_path: str, narration: str,
               frame_path: str) -> str:
    """한 세그먼트 합성 프레임 PNG 생성"""
    frame = Image.new('RGB', (W, H), C_BLACK)
    draw  = ImageDraw.Draw(frame)
    pad   = 50

    # ── 상단: 노란 강조 제목 ─────────────────────────
    title_font = _get_font(96, bold=True)
    _draw_centered_text(draw, title, TITLE_TOP, title_font,
                        C_YELLOW, W - pad * 2, line_gap=16)

    # ── 중간: DALL-E 이미지 (검정 배경 위에 정사각형) ──
    if image_path and os.path.exists(image_path):
        img = Image.open(image_path).convert('RGB')
        iw, ih = img.size
        side = min(iw, ih)
        img  = img.crop(((iw - side) // 2, (ih - side) // 2,
                          (iw + side) // 2, (ih + side) // 2))
        img  = img.resize((IMG_SIZE, IMG_SIZE), Image.LANCZOS)
        frame.paste(img, (0, IMG_Y))
    else:
        draw.rectangle([(0, IMG_Y), (W, IMG_Y + IMG_SIZE)], fill=C_BLACK)

    # ── 하단: 흰 나레이션 자막 (최대 3줄, 하단 고정) ────
    sub_font = _get_font(58, bold=True)
    lines    = _wrap_text(draw, narration, sub_font, W - pad * 2)[:3]
    line_h   = sub_font.getbbox('가')[3] + 14   # 줄 높이 + 간격
    total_h  = line_h * len(lines)
    y = H - 60 - total_h                        # 하단 60px 여백 기준 위로
    for line in lines:
        lw = draw.textlength(line, font=sub_font)
        draw.text(((W - lw) // 2, y), line, font=sub_font, fill=C_WHITE)
        y += line_h

    frame.save(frame_path)
    return frame_path


def compose_video(segments_data: list, title: str, output_path: str) -> str:
    """
    segments_data: [{'audio_path': ..., 'narration': ..., 'image_path': ..., 'index': ...}]
    각 세그먼트 = 이미지 + 오디오 + 자막 프레임
    """
    frames_dir = output_path.replace('.mp4', '_frames')
    os.makedirs(frames_dir, exist_ok=True)

    clips = []
    for seg in segments_data:
        idx       = seg['index']
        frame_path = os.path.join(frames_dir, f'frame_{idx:02d}.png')

        make_frame(
            title       = title,
            image_path  = seg.get('image_path', ''),
            narration   = seg['narration'],
            frame_path  = frame_path
        )

        audio = AudioFileClip(seg['audio_path'])

        if MOVIEPY_V2:
            clip = ImageClip(frame_path, duration=audio.duration).with_audio(audio)
        else:
            clip = (ImageClip(frame_path)
                    .set_duration(audio.duration)
                    .set_audio(audio))
        clips.append(clip)

    final = concatenate_videoclips(clips, method='compose')
    final.write_videofile(
        output_path,
        fps=FPS,
        codec='libx264',
        audio_codec='aac',
        temp_audiofile='/tmp/temp_audio.m4a',
        remove_temp=True
    )
    return output_path
