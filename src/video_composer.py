"""
영상 합성:
- Pillow로 각 세그먼트 프레임 합성 (검정 배경 + 노란 제목 + 이미지 + 흰 자막)
- MoviePy로 프레임 + 오디오 → MP4
- 나레이션 자막: 타이핑 효과 (줄 단위로 한 글자씩 나타남)
- 애니메이션 효과: Ken Burns (zoom_in, pan_r, zoom_pan) + 전환 (slide, push, wipe)
"""
import os
import random
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

# ── 애니메이션 효과 상수
TRANS_F = 10   # 전환 효과 적용 프레임 수 (~0.33s at 30fps)


# ── 폰트 유틸리티 ─────────────────────────────────────────────────────

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


# ── 이미지 유틸리티 ───────────────────────────────────────────────────

def _load_img_sq(image_path: str):
    """이미지 로드 → 정사각형 크롭 → IMG_SIZE 리사이즈 → numpy uint8 배열 반환."""
    if not image_path or not os.path.exists(image_path):
        return None
    img  = Image.open(image_path).convert('RGB')
    iw, ih = img.size
    side = min(iw, ih)
    img  = img.crop(((iw - side) // 2, (ih - side) // 2,
                      (iw + side) // 2, (ih + side) // 2))
    img  = img.resize((IMG_SIZE, IMG_SIZE), Image.LANCZOS)
    return np.array(img)


# ── Ken Burns 효과 ────────────────────────────────────────────────────

def _ease_in_out(t: float) -> float:
    """Cubic ease-in-out: 0→1 입력, 0→1 출력."""
    if t <= 0.5:
        return 4.0 * t * t * t
    p = t - 1.0
    return 1.0 + 4.0 * p * p * p


def _kb(img_arr: np.ndarray, prog: float, mode: str) -> np.ndarray:
    """
    Ken Burns 효과 적용.
    img_arr : IMG_SIZE×IMG_SIZE×3  numpy uint8
    prog    : 0.0→1.0 (세그먼트 진행도)
    mode    : 'zoom_in' | 'pan_r' | 'zoom_pan'
    반환    : IMG_SIZE×IMG_SIZE×3  numpy uint8
    """
    S    = IMG_SIZE
    prog = max(0.0, min(1.0, prog))

    if mode == 'zoom_in':
        # 1.0× → 1.08× 중앙 줌인
        scale  = 1.0 + 0.08 * prog
        crop_s = max(1, int(S / scale))
        x0     = (S - crop_s) // 2
        y0     = (S - crop_s) // 2
        region = img_arr[y0:y0 + crop_s, x0:x0 + crop_s]

    elif mode == 'pan_r':
        # 1.1× 줌 상태에서 왼쪽 → 오른쪽 패닝
        scale  = 1.1
        crop_s = max(1, int(S / scale))     # ~982
        max_x  = S - crop_s                  # ~98
        y0     = (S - crop_s) // 2           # 수직 중앙 고정
        x0     = int(max_x * prog)
        region = img_arr[y0:y0 + crop_s, x0:x0 + crop_s]

    elif mode == 'zoom_pan':
        # 1.0× → 1.10× 줌인 + 오른쪽 패닝 동시
        scale  = 1.0 + 0.10 * prog
        crop_s = max(1, int(S / scale))
        max_x  = max(0, S - crop_s)
        x0     = min(int(max_x * prog * 0.6), max_x)
        y0     = max(0, S - crop_s) // 2    # 수직 중앙
        region = img_arr[y0:y0 + crop_s, x0:x0 + crop_s]

    else:
        return img_arr  # 알 수 없는 모드: 원본 반환

    return np.array(
        Image.fromarray(region).resize((S, S), Image.BILINEAR)
    )


# ── 전환 효과 ─────────────────────────────────────────────────────────

def _trans_frame(prev_arr: np.ndarray, curr_arr: np.ndarray,
                 p: float, mode: str) -> np.ndarray:
    """
    두 이미지 사이 전환 효과.
    prev_arr, curr_arr : IMG_SIZE×IMG_SIZE×3  numpy uint8
    p    : 0.0→1.0 (전환 진행도, eased)
    mode : 'slide' | 'push' | 'wipe'
    반환 : IMG_SIZE×IMG_SIZE×3  numpy uint8
    """
    S = IMG_SIZE
    p = max(0.0, min(1.0, p))

    if mode == 'slide':
        # curr가 오른쪽에서 밀려 들어옴 (prev는 고정)
        b_left = int(S * (1.0 - p))
        out = prev_arr.copy()
        if b_left < S:
            out[:, b_left:] = curr_arr[:, :S - b_left]
        return out

    elif mode == 'push':
        # prev가 왼쪽으로 밀려 나가고 curr가 오른쪽에서 들어옴
        offset = int(S * p)
        out    = np.zeros_like(prev_arr)
        rem    = S - offset
        if rem > 0:
            out[:, :rem] = prev_arr[:, offset:]
        if offset > 0:
            out[:, rem:] = curr_arr[:, :offset]
        return out

    elif mode == 'wipe':
        # 왼쪽→오른쪽 경계선이 이동하며 curr를 드러냄
        boundary = int(S * p)
        out = prev_arr.copy()
        if boundary > 0:
            out[:, :boundary] = curr_arr[:, :boundary]
        return out

    return curr_arr


# ── 효과 팔레트 선택 ──────────────────────────────────────────────────

def _pick_effects(n_segs: int, seed: int) -> list:
    """
    각 세그먼트에 적용할 (kb_mode, trans_mode) 튜플 리스트 반환.
    - KB 팔레트:  zoom_in / pan_r / zoom_pan 중 2~3개 선택 → 순환 적용
    - 전환 팔레트: slide / push / wipe 중 2~3개 선택 → 순환 적용
    - 첫 번째 세그먼트의 trans_mode 는 None (이전 세그먼트 없음)
    """
    rng = random.Random(seed)

    kb_pool    = ['zoom_in', 'pan_r', 'zoom_pan']
    trans_pool = ['slide', 'push', 'wipe']

    n_kb    = rng.randint(2, 3)
    n_trans = rng.randint(2, 3)

    kb_palette    = rng.sample(kb_pool,    n_kb)
    trans_palette = rng.sample(trans_pool, n_trans)

    result = []
    for i in range(n_segs):
        kb    = kb_palette[i % len(kb_palette)]
        trans = None if i == 0 else trans_palette[(i - 1) % len(trans_palette)]
        result.append((kb, trans))

    return result


# ── 베이스 프레임 ─────────────────────────────────────────────────────

def _make_base_bg(title: str, narration: str = '') -> tuple:
    """
    이미지 없이 제목 + 검정 배경만 렌더링.
    반환: (PIL Image, img_y, sub_font, line_h, sub_top, sub_bottom, pad)
    """
    pad   = 50
    frame = Image.new('RGB', (W, H), C_BLACK)
    draw  = ImageDraw.Draw(frame)

    title_font = _fit_title_font(draw, title, W - pad * 2, max_height=230)
    title_h    = _measure_text_height(draw, title, title_font, W - pad * 2)
    _draw_centered_text(draw, title, TITLE_TOP, title_font, C_YELLOW, W - pad * 2, line_gap=16)

    img_y = max(IMG_Y, TITLE_TOP + title_h + 40)
    img_y = min(img_y, H - IMG_SIZE - 360)

    sub_font = _auto_sub_font(narration) if narration else _get_font(62, bold=True)
    _test_bb = sub_font.getbbox('Ag가')
    line_h   = (_test_bb[3] - _test_bb[1]) + 14

    sub_top    = img_y + IMG_SIZE + 20
    sub_bottom = H - 80 - line_h

    return frame, img_y, sub_font, line_h, sub_top, sub_bottom, pad


def _make_base(title: str, image_path: str, narration: str = '') -> tuple:
    """
    자막 없이 제목 + 이미지만 렌더링 (make_frame 하위 호환용).
    반환: (PIL Image, sub_font, line_h, sub_y, sub_bottom, pad)
    """
    pad   = 50
    frame = Image.new('RGB', (W, H), C_BLACK)
    draw  = ImageDraw.Draw(frame)

    title_font = _fit_title_font(draw, title, W - pad * 2, max_height=230)
    title_h    = _measure_text_height(draw, title, title_font, W - pad * 2)
    _draw_centered_text(draw, title, TITLE_TOP, title_font, C_YELLOW, W - pad * 2, line_gap=16)

    img_y = max(IMG_Y, TITLE_TOP + title_h + 40)
    img_y = min(img_y, H - IMG_SIZE - 360)

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

    sub_font = _auto_sub_font(narration) if narration else _get_font(62, bold=True)
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
                        narration: str, audio_path: str,
                        img_sq: np.ndarray = None,
                        prev_img_arr: np.ndarray = None,
                        kb_mode: str = 'zoom_in',
                        trans_mode: str = None):
    """
    자막 타이핑 + Ken Burns + 전환 효과가 적용된 VideoClip 반환.

    img_sq       : 정사각형 크롭된 현재 세그먼트 이미지 numpy 배열 (없으면 image_path로 로드)
    prev_img_arr : 이전 세그먼트 최종 KB 상태 이미지 (전환 효과용, None이면 전환 없음)
    kb_mode      : 'zoom_in' | 'pan_r' | 'zoom_pan'
    trans_mode   : 'slide' | 'push' | 'wipe' | None

    개선점:
    - _auto_sub_font: 나레이션 길이에 맞는 폰트 자동 선택 (문장 끊김 방지)
    - _line_char_ranges: 각 줄의 원문 위치를 미리 계산 → 2번째 줄 갑작스러운 등장 방지
    - 유효 타이핑 속도 보정: 오디오 85% 시점까지 모든 글자 완성 (속도 불일치·점프 방지)
    - 자막 캐시(sub_cache)는 이미지 영역 제외 → 이미지는 per-frame KB/전환 효과 후 붙여넣기
    """
    # img_sq 없으면 image_path에서 로드 (fallback)
    if img_sq is None and image_path:
        img_sq = _load_img_sq(image_path)

    # ── 베이스 프레임 (이미지 없음: 제목 + 검정 배경만) ─────────────
    base_img, img_y, sub_font, line_h, sub_top, sub_bottom, pad = _make_base_bg(
        title, narration
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

    # ── 자막 배경 박스 1회 합성 ──────────────────────────────────────
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
    natural_end = total_chars / TYPING_SPEED
    typing_end  = min(natural_end, duration * 0.85)
    eff_speed   = total_chars / typing_end if typing_end > 0 else float('inf')

    # ── 자막 상태별 numpy 배열 캐시 (이미지 영역 제외) ───────────────
    # 이미지 영역(img_y ~ img_y+IMG_SIZE)은 검정으로 남겨두고,
    # 프레임 생성 시 KB/전환 처리된 이미지를 덮어씀.
    _sub_cache: dict = {}

    def get_sub_arr(n: int) -> np.ndarray:
        if n not in _sub_cache:
            img  = base_with_box.copy()
            draw = ImageDraw.Draw(img)
            if n:
                y = y_fixed
                for line_text, (c_start, c_end) in zip(full_lines, char_ranges):
                    if n < c_start:
                        break
                    visible = line_text[:n - c_start] if n < c_end else line_text
                    if visible:
                        lw = draw.textlength(visible, font=sub_font)
                        draw.text(((W - lw) // 2, y), visible,
                                  font=sub_font, fill=C_WHITE)
                    y += line_h
            _sub_cache[n] = np.array(img)
        return _sub_cache[n]

    # ── 프레임 생성 ──────────────────────────────────────────────────
    frames = []
    for i in range(total_frames):
        t = i / FPS

        # 1. 자막 상태 (이미지 없는 배경+텍스트 캐시에서 복사)
        n = total_chars if t >= typing_end else min(int(t * eff_speed) + 1, total_chars)
        frame_arr = get_sub_arr(n).copy()

        # 2. 이미지 영역: KB 효과 + 전환 효과 적용
        if img_sq is not None:
            prog     = min(t / max(duration, 0.001), 1.0)
            curr_img = _kb(img_sq, prog, kb_mode)

            if i < TRANS_F and trans_mode is not None and prev_img_arr is not None:
                # 전환 효과: 첫 TRANS_F 프레임에만 적용 (이전→현재 이미지 블렌딩)
                p_raw    = (i + 1) / TRANS_F
                p_eased  = _ease_in_out(p_raw)
                img_area = _trans_frame(prev_img_arr, curr_img, p_eased, trans_mode)
            else:
                img_area = curr_img

            # 이미지 붙여넣기 (자막 영역 y>img_y+IMG_SIZE 와 겹치지 않음)
            frame_arr[img_y:img_y + IMG_SIZE, 0:IMG_SIZE] = img_area

        frames.append(frame_arr)

    clip = ImageSequenceClip(frames, fps=FPS)
    if MOVIEPY_V2:
        clip = clip.with_audio(audio)
    else:
        clip = clip.set_audio(audio)

    font_size = sub_font.size if hasattr(sub_font, 'size') else '?'
    print(f'   [타이핑] "{narration[:25]}..." '
          f'| {total_chars}자 | 폰트 {font_size}px | {full_n_lines}줄 '
          f'| {typing_end:.1f}s 내 완성 (속도 {eff_speed:.1f}cps) | 총 {duration:.1f}s'
          f' | KB={kb_mode} TRANS={trans_mode or "없음"}')
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
    줄 단위 타이핑 자막 + Ken Burns + 전환 효과로 영상 합성.
    """
    n_segs = len(segments_data)

    # ── 타이틀 해시 시드로 효과 팔레트 결정 (같은 제목 → 항상 같은 효과) ──
    seed    = sum(ord(c) for c in title) if title else 42
    effects = _pick_effects(n_segs, seed)
    kb_set    = list(dict.fromkeys(e[0] for e in effects))
    trans_set = list(dict.fromkeys(e[1] for e in effects if e[1]))
    print(f'   [효과] KB={kb_set} / TRANS={trans_set} (시드={seed})')

    # ── 이미지 사전 로드 (각 세그먼트의 img_sq) ──────────────────────
    img_sqs = [_load_img_sq(seg.get('image_path', '')) for seg in segments_data]

    clips        = []
    prev_img_arr = None   # 이전 세그먼트 최종 KB 상태 이미지

    for i, seg in enumerate(segments_data):
        kb_mode, trans_mode = effects[i]

        clip = _make_subtitle_clip(
            title        = title,
            image_path   = seg.get('image_path', ''),
            narration    = seg['narration'],
            audio_path   = seg['audio_path'],
            img_sq       = img_sqs[i],
            prev_img_arr = prev_img_arr,
            kb_mode      = kb_mode,
            trans_mode   = trans_mode,
        )
        clips.append(clip)

        # 다음 세그먼트의 prev_img_arr = 현재 세그먼트 KB 최종 프레임 (prog=1.0)
        if img_sqs[i] is not None:
            prev_img_arr = _kb(img_sqs[i], 1.0, kb_mode)
        else:
            prev_img_arr = None

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
