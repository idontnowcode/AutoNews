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

SUB_BG_ALPHA  = 160  # 자막 배경 박스 투명도 (0=완전투명, 255=불투명)
SUB_BG_PAD    = 18   # 자막 배경 박스 여백(px)
# YouTube Shorts 우측 버튼(좋아요/댓글/공유) 영역 약 130px 차지
# 좌우 각 120px 여백을 두어 자막이 버튼에 가리지 않도록 제한
SUB_MAX_WIDTH = W - 240  # 1080 - 240 = 840px


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
    """베이스 이미지에 자막 text를 그린 numpy 배열 반환 (정적 프레임 / make_frame 용)."""
    img  = base_img.copy()
    draw = ImageDraw.Draw(img)

    if text:
        lines   = _wrap_text(draw, text, sub_font, SUB_MAX_WIDTH)[:3]
        total_h = line_h * len(lines)
        y_start = max(sub_top, sub_bottom - total_h)

        max_line_w = max(draw.textlength(ln, font=sub_font) for ln in lines)
        box_w = int(max_line_w) + SUB_BG_PAD * 2
        box_h = total_h + SUB_BG_PAD * 2
        box_x = (W - box_w) // 2
        box_y = y_start - SUB_BG_PAD

        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        ov_draw.rounded_rectangle(
            [(box_x, box_y), (box_x + box_w, box_y + box_h)],
            radius=12, fill=(0, 0, 0, SUB_BG_ALPHA),
        )
        img  = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
        draw = ImageDraw.Draw(img)

        y = y_start
        for line in lines:
            lw = draw.textlength(line, font=sub_font)
            draw.text(((W - lw) // 2, y), line, font=sub_font, fill=C_WHITE)
            y += line_h

    return np.array(img)


TYPING_SPEED = 8    # 초당 타이핑 글자 수


# ── 타이핑 효과 클립 생성 ─────────────────────────────────────────

def _make_subtitle_clip(title: str, image_path: str,
                        narration: str, audio_path: str):
    """
    자막이 한 글자씩 타이핑되는 VideoClip 반환.

    핵심: 배경 박스 위치·크기와 텍스트 Y를 전체 나레이션 기준으로 미리 고정.
    타이핑 중 박스가 늘어나거나 위치가 바뀌지 않는다.
    """
    base_img, sub_font, line_h, sub_top, sub_bottom, pad = _make_base(title, image_path)
    audio        = AudioFileClip(audio_path)
    duration     = audio.duration
    total_chars  = len(narration)
    total_frames = max(1, int(duration * FPS))

    # ── 전체 나레이션 기준으로 레이아웃 고정 ──────────────────────
    _ref_draw   = ImageDraw.Draw(base_img.copy())
    full_lines  = _wrap_text(_ref_draw, narration, sub_font, SUB_MAX_WIDTH)[:3]
    full_n_lines = len(full_lines)
    full_max_w   = max((_ref_draw.textlength(ln, font=sub_font) for ln in full_lines),
                       default=0)

    y_fixed   = max(sub_top, sub_bottom - line_h * full_n_lines)
    box_w     = int(full_max_w) + SUB_BG_PAD * 2
    box_h     = line_h * full_n_lines + SUB_BG_PAD * 2
    box_x     = (W - box_w) // 2
    box_y     = y_fixed - SUB_BG_PAD

    # 배경 박스가 그려진 베이스 이미지 1회만 합성
    overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    ov_draw.rounded_rectangle(
        [(box_x, box_y), (box_x + box_w, box_y + box_h)],
        radius=12,
        fill=(0, 0, 0, SUB_BG_ALPHA),
    )
    base_with_box = Image.alpha_composite(
        base_img.convert('RGBA'), overlay
    ).convert('RGB')

    # ── 자막 상태(글자 수) → numpy 배열 캐시 ───────────────────────
    _cache: dict[int, np.ndarray] = {}

    def get_arr(n: int) -> np.ndarray:
        if n not in _cache:
            img  = base_with_box.copy()
            draw = ImageDraw.Draw(img)
            if n:
                lines = _wrap_text(draw, narration[:n], sub_font, SUB_MAX_WIDTH)[:3]
                y = y_fixed
                for line in lines:
                    lw = draw.textlength(line, font=sub_font)
                    draw.text(((W - lw) // 2, y), line, font=sub_font, fill=C_WHITE)
                    y += line_h
            _cache[n] = np.array(img)
        return _cache[n]

    # 타이핑 완료 시점: 전체 길이의 최대 50% 또는 타이핑 소요 시간
    typing_end = min(total_chars / TYPING_SPEED, duration * 0.5)

    frames = []
    for i in range(total_frames):
        t = i / FPS
        n = total_chars if t >= typing_end else min(int(t * TYPING_SPEED) + 1, total_chars)
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
        clip = _make_subtitle_clip(
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
