"""
영상 합성:
- Pillow로 각 세그먼트 프레임 합성 (검정 배경 + 노란 제목 + 이미지 + 흰 자막)
- MoviePy로 프레임 + 오디오 → MP4
- 나레이션 자막: 타이핑 효과 (줄 단위로 한 글자씩 나타남)
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

W, H     = 1080, 1920
FPS      = 30
C_BLACK  = (0,   0,   0)
C_YELLOW = (255, 214,  10)
C_WHITE  = (255, 255, 255)

TITLE_TOP = 120
IMG_Y     = 360
IMG_SIZE  = 1080

SUB_BG_ALPHA  = 160   # 자막 배경 박스 투명도
SUB_BG_PAD    = 18    # 자막 배경 박스 여백(px)
# YouTube Shorts 우측 버튼 영역 ~130px → 좌우 120px 여백
SUB_MAX_WIDTH = W - 240   # 840px

# ── 자막 폰트 크기 후보 (큰 것부터 시도)
SUB_FONT_SIZES = (62, 52, 44, 36)
MAX_SUB_LINES  = 4    # 최대 자막 줄 수 (영어 긴 문장 대응)
TYPING_SPEED   = 12   # chars/sec 기준 (실제 속도는 오디오 길이에 맞게 보정됨)


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


def _auto_sub_font(narration: str) -> ImageFont.FreeTypeFont:
    """나레이션이 MAX_SUB_LINES 이하로 줄바꿈되는 가장 큰 폰트 반환."""
    tmp_draw = ImageDraw.Draw(Image.new('RGB', (10, 10)))
    for size in SUB_FONT_SIZES:
        font = _get_font(size, bold=True)
        if len(_wrap_text(tmp_draw, narration, font, SUB_MAX_WIDTH)) <= MAX_SUB_LINES:
            return font
    return _get_font(SUB_FONT_SIZES[-1], bold=True)


def _line_char_ranges(narration: str, lines: list) -> list:
    """
    각 줄의 (start_char, end_char) 위치를 narration 원문 기준으로 반환.
    줄 사이 공백은 범위에 포함되지 않으므로, 타이핑 시 줄이 자연스럽게 이어짐.
    """
    result = []
    pos = 0
    for line in lines:
        # 줄 사이 공백 건너뜀
        while pos < len(narration) and narration[pos] in (' ', '\t', '\n', '\r'):
            pos += 1
        start = pos
        end   = pos + len(line)
        result.append((start, end))
        pos = end
    return result


# ── 베이스 프레임 (자막 제외) ─────────────────────────────────────────

def _make_base(title: str, image_path: str, narration: str = '') -> tuple:
    """
    자막 없이 제목 + 이미지만 렌더링.
    narration을 받아 최적 폰트 크기 자동 선택.
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

    # 자막 폰트: narration 기준 자동 크기 선택
    sub_font = _auto_sub_font(narration) if narration else _get_font(62, bold=True)
    # 라인 높이: 한글/영문 모두 커버하는 테스트 문자열 사용
    _test_bb = sub_font.getbbox('Ag가')
    line_h   = (_test_bb[3] - _test_bb[1]) + 14

    sub_top    = img_y + IMG_SIZE + 20
    sub_bottom = H - 80 - line_h

    return frame, sub_font, line_h, sub_top, sub_bottom, pad


def _draw_subtitle(base_img: Image.Image, text: str,
                   sub_font, line_h: int, sub_top: int,
                   sub_bottom: int, pad: int) -> np.ndarray:
    """베이스 이미지에 자막 text를 그린 numpy 배열 반환 (정적 프레임 용)."""
    img  = base_img.copy()
    draw = ImageDraw.Draw(img)

    if text:
        lines   = _wrap_text(draw, text, sub_font, SUB_MAX_WIDTH)[:MAX_SUB_LINES]
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


# ── 타이핑 효과 클립 생성 ─────────────────────────────────────────────

def _make_subtitle_clip(title: str, image_path: str,
                        narration: str, audio_path: str):
    """
    자막이 줄 단위로 한 글자씩 타이핑되는 VideoClip 반환.

    개선점:
    - _auto_sub_font: 나레이션 길이에 맞는 폰트 자동 선택 (문장 끊김 방지)
    - _line_char_ranges: 각 줄의 원문 위치를 미리 계산 → 2번째 줄 갑작스러운 등장 방지
    - 유효 타이핑 속도 보정: 오디오 85% 시점까지 모든 글자 완성 (속도 불일치·점프 방지)
    """
    base_img, sub_font, line_h, sub_top, sub_bottom, pad = _make_base(
        title, image_path, narration
    )
    audio        = AudioFileClip(audio_path)
    duration     = audio.duration
    total_chars  = len(narration)
    total_frames = max(1, int(duration * FPS))

    # ── 전체 나레이션 기준 레이아웃 고정 ──────────────────────────────
    _ref_draw    = ImageDraw.Draw(base_img.copy())
    full_lines   = _wrap_text(_ref_draw, narration, sub_font, SUB_MAX_WIDTH)[:MAX_SUB_LINES]
    full_n_lines = len(full_lines)
    char_ranges  = _line_char_ranges(narration, full_lines)   # [(start, end), ...]

    full_max_w = max((_ref_draw.textlength(ln, font=sub_font) for ln in full_lines),
                     default=0)

    y_fixed = max(sub_top, sub_bottom - line_h * full_n_lines)
    box_w   = int(full_max_w) + SUB_BG_PAD * 2
    box_h   = line_h * full_n_lines + SUB_BG_PAD * 2
    box_x   = (W - box_w) // 2
    box_y   = y_fixed - SUB_BG_PAD

    # 배경 박스 1회 합성
    overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    ov_draw.rounded_rectangle(
        [(box_x, box_y), (box_x + box_w, box_y + box_h)],
        radius=12, fill=(0, 0, 0, SUB_BG_ALPHA),
    )
    base_with_box = Image.alpha_composite(
        base_img.convert('RGBA'), overlay
    ).convert('RGB')

    # ── 타이핑 속도 보정 ──────────────────────────────────────────────
    # 기준 속도로 완료되는 시간 vs 오디오 85% 중 짧은 쪽
    # → 유효 속도(eff_speed)를 역산하여 점프 없이 smooth하게 완성
    natural_end = total_chars / TYPING_SPEED
    typing_end  = min(natural_end, duration * 0.85)
    eff_speed   = total_chars / typing_end if typing_end > 0 else float('inf')

    # ── 자막 상태(글자 수) → numpy 배열 캐시 ─────────────────────────
    _cache: dict = {}

    def get_arr(n: int) -> np.ndarray:
        if n not in _cache:
            img  = base_with_box.copy()
            draw = ImageDraw.Draw(img)
            if n:
                y = y_fixed
                for line_text, (c_start, c_end) in zip(full_lines, char_ranges):
                    if n < c_start:
                        # 아직 이 줄에 도달하지 않음
                        break
                    # 이 줄에서 보여줄 글자 수 계산
                    visible = line_text[:n - c_start] if n < c_end else line_text
                    if visible:
                        lw = draw.textlength(visible, font=sub_font)
                        draw.text(((W - lw) // 2, y), visible,
                                  font=sub_font, fill=C_WHITE)
                    y += line_h
            _cache[n] = np.array(img)
        return _cache[n]

    frames = []
    for i in range(total_frames):
        t = i / FPS
        n = total_chars if t >= typing_end else min(int(t * eff_speed) + 1, total_chars)
        frames.append(get_arr(n))

    clip = ImageSequenceClip(frames, fps=FPS)
    if MOVIEPY_V2:
        clip = clip.with_audio(audio)
    else:
        clip = clip.set_audio(audio)

    font_size = sub_font.size if hasattr(sub_font, 'size') else '?'
    print(f'   [타이핑] "{narration[:25]}..." '
          f'| {total_chars}자 | 폰트 {font_size}px | {full_n_lines}줄 '
          f'| {typing_end:.1f}s 내 완성 (속도 {eff_speed:.1f}cps) | 총 {duration:.1f}s')
    return clip


# ── 공개 API ──────────────────────────────────────────────────────────

def make_frame(title: str, image_path: str, narration: str,
               frame_path: str) -> str:
    """단일 정적 프레임 PNG 저장 (하위 호환용)"""
    base_img, sub_font, line_h, sub_top, sub_bottom, pad = _make_base(
        title, image_path, narration
    )
    arr = _draw_subtitle(base_img, narration, sub_font, line_h, sub_top, sub_bottom, pad)
    Image.fromarray(arr).save(frame_path)
    return frame_path


def compose_video(segments_data: list, title: str, output_path: str) -> str:
    """
    segments_data: [{'audio_path': ..., 'narration': ..., 'image_path': ..., 'index': ...}]
    줄 단위 타이핑 자막으로 영상 합성
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
