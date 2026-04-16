"""
영상 합성:
- Pillow로 각 세그먼트 프레임 합성 (검정 배경 + 노란 제목 + 이미지 + 흰 자막)
- MoviePy로 프레임 + 오디오 → MP4
- 나레이션 자막: 타이핑 효과 (문자가 하나씩 나타남)
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:
    from moviepy.editor import ImageSequenceClip, AudioFileClip, concatenate_videoclips
    MOVIEPY_V2 = False
except ModuleNotFoundError:
    from moviepy import ImageSequenceClip, AudioFileClip, concatenate_videoclips
    MOVIEPY_V2 = True

W, H   = 1080, 1920
FPS    = 30
C_BLACK  = (0,   0,   0)
C_YELLOW = (255, 214,  10)
C_WHITE  = (255, 255, 255)

TITLE_TOP    = 120
IMG_Y        = 360
IMG_SIZE     = 1080

TYPING_SPEED = 8    # 초당 타이핑 글자 수 (음성과 함께 읽기 좋은 속도)


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf' if bold
            else '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
        '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
        '/usr/share/fonts/truetype/nanum/NanumGothicExtraBold.ttf',
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
                return ImageFont.truetype(path, size)
            except Exception:
                continue
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
    for line in _wrap_text(draw, text, font, max_width):
        lw = draw.textlength(line, font=font)
        draw.text(((W - lw) // 2, y), line, font=font, fill=fill)
        bbox = draw.textbbox((0, 0), line, font=font)
        y += (bbox[3] - bbox[1]) + line_gap
    return y


def _measure_text_height(draw, text: str, font, max_width: int,
                         line_gap: int = 16) -> int:
    total = 0
    for line in _wrap_text(draw, text, font, max_width):
        bbox = draw.textbbox((0, 0), line, font=font)
        total += (bbox[3] - bbox[1]) + line_gap
    return total


def _fit_title_font(draw, title: str, max_width: int,
                    max_height: int = 230) -> ImageFont.FreeTypeFont:
    for size in (96, 76, 60, 48):
        font = _get_font(size, bold=True)
        if _measure_text_height(draw, title, font, max_width) <= max_height:
            return font
    return _get_font(48, bold=True)


# ── 베이스 프레임 (자막 제외) ─────────────────────────────────────

def _make_base(title: str, image_path: str) -> tuple:
    """
    자막 없이 제목 + 이미지만 렌더링.
    반환: (PIL Image, sub_font, line_h, sub_y, sub_bottom, pad)
    """
    pad   = 50
    frame = Image.new('RGB', (W, H), C_BLACK)
    draw  = ImageDraw.Draw(frame)

    # 제목
    title_font = _fit_title_font(draw, title, W - pad * 2, max_height=230)
    title_h    = _measure_text_height(draw, title, title_font, W - pad * 2)
    _draw_centered_text(draw, title, TITLE_TOP, title_font, C_YELLOW, W - pad * 2, line_gap=16)

    img_y = max(IMG_Y, TITLE_TOP + title_h + 40)
    img_y = min(img_y, H - IMG_SIZE - 360)

    # 이미지
    if image_path and os.path.exists(image_path):
        img = Image.open(image_path).convert('RGB')
        iw, ih = img.size
        side = min(iw, ih)
        img  = img.crop(((iw - side) // 2, (ih - side) // 2,
                          (iw + side) // 2, (ih + side) // 2))
        img  = img.resize((IMG_SIZE, IMG_SIZE), Image.LANCZOS)
        frame.paste(img, (0, img_y))
    else:
        draw.rectangle([(0, img_y), (W, img_y + IMG_SIZE)], fill=C_BLACK)

    # 자막 레이아웃 파라미터 계산 (실제 그리기는 안 함)
    sub_font   = _get_font(62, bold=True)
    line_h     = sub_font.getbbox('가')[3] + 14
    sub_top    = img_y + IMG_SIZE + 20
    sub_bottom = H - 80 - line_h

    return frame, sub_font, line_h, sub_top, sub_bottom, pad


def _draw_subtitle(base_img: Image.Image, text: str,
                   sub_font, line_h: int, sub_top: int,
                   sub_bottom: int, pad: int) -> np.ndarray:
    """베이스 이미지에 자막 text를 그린 numpy 배열 반환"""
    img  = base_img.copy()
    draw = ImageDraw.Draw(img)

    if text:
        lines   = _wrap_text(draw, text, sub_font, W - pad * 2)[:3]
        total_h = line_h * len(lines)
        y       = max(sub_top, sub_bottom - total_h)
        for line in lines:
            draw.text((pad, y), line, font=sub_font, fill=C_WHITE)  # 왼쪽 정렬
            y += line_h

    return np.array(img)


# ── 타이핑 효과 클립 생성 ─────────────────────────────────────────

def _make_typing_clip(title: str, image_path: str,
                      narration: str, audio_path: str):
    """
    자막이 한 글자씩 타이핑되는 VideoClip 반환.
    - TYPING_SPEED 글자/초로 타이핑 → 이후 전체 자막 유지
    - 베이스 프레임은 1회만 렌더링, 자막 상태별 numpy 배열 캐싱
    """
    base_img, sub_font, line_h, sub_top, sub_bottom, pad = _make_base(title, image_path)
    audio        = AudioFileClip(audio_path)
    duration     = audio.duration
    total_chars  = len(narration)
    total_frames = max(1, int(duration * FPS))

    # 자막 상태(글자 수) → numpy 배열 캐시
    _cache: dict[int, np.ndarray] = {}

    def get_arr(n: int) -> np.ndarray:
        if n not in _cache:
            _cache[n] = _draw_subtitle(base_img, narration[:n],
                                       sub_font, line_h, sub_top, sub_bottom, pad)
        return _cache[n]

    # 타이핑 완료 시점: 전체 길이의 최대 50% 또는 타이핑 소요 시간
    typing_end = min(total_chars / TYPING_SPEED, duration * 0.5)

    frames = []
    for i in range(total_frames):
        t = i / FPS
        if t >= typing_end:
            n = total_chars
        else:
            n = min(int(t * TYPING_SPEED) + 1, total_chars)
        frames.append(get_arr(n))

    clip = ImageSequenceClip(frames, fps=FPS)

    if MOVIEPY_V2:
        clip = clip.with_audio(audio)
    else:
        clip = clip.set_audio(audio)

    print(f'   [타이핑] "{narration[:20]}..." '
          f'→ {total_chars}자 / {typing_end:.1f}s 내 완성 / 총 {duration:.1f}s')
    return clip


# ── 공개 API ──────────────────────────────────────────────────────

def make_frame(title: str, image_path: str, narration: str,
               frame_path: str) -> str:
    """단일 정적 프레임 PNG 저장 (하위 호환용)"""
    base_img, sub_font, line_h, sub_top, sub_bottom, pad = _make_base(title, image_path)
    arr = _draw_subtitle(base_img, narration, sub_font, line_h, sub_top, sub_bottom, pad)
    Image.fromarray(arr).save(frame_path)
    return frame_path


def compose_video(segments_data: list, title: str, output_path: str) -> str:
    """
    segments_data: [{'audio_path': ..., 'narration': ..., 'image_path': ..., 'index': ...}]
    타이핑 효과 자막으로 영상 합성
    """
    clips = []
    for seg in segments_data:
        clip = _make_typing_clip(
            title      = title,
            image_path = seg.get('image_path', ''),
            narration  = seg['narration'],
            audio_path = seg['audio_path'],
        )
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
