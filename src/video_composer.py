"""
영상 합성:
- Pillow로 각 세그먼트 프레임 합성 (검정 배경 + 노란 제목 + 이미지 + 흰 자막)
- MoviePy로 프레임 + 오디오 → MP4
- 나레이션 자막: 타이핑 효과 (줄 단위로 한 글자씩 나타남)
- 자막 스타일: 흰 글씨 + 검정 테두리, 이미지 하단 25% 위치에 오버레이
- 애니메이션 효과: Ken Burns (zoom_in, pan_r, zoom_pan) + 전환 (slide, push, wipe)
"""
import os
import random
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:
    from moviepy.editor import (ImageSequenceClip, AudioFileClip,
                                  concatenate_videoclips, concatenate_audioclips)
    MOVIEPY_V2 = False
except ModuleNotFoundError:
    from moviepy import (ImageSequenceClip, AudioFileClip,
                          concatenate_videoclips, concatenate_audioclips)
    MOVIEPY_V2 = True

W, H     = 1080, 1920
FPS      = 30
C_BLACK  = (0,   0,   0)
C_YELLOW = (255, 214,  10)
C_WHITE  = (255, 255, 255)

TITLE_TOP = 120
IMG_Y     = 360
IMG_SIZE  = 1080

# 자막: 이미지 하단 25% 지점에 오버레이 (이미지 위에 직접 렌더링)
SUB_OVERLAY_RATIO = 0.75   # IMG_SIZE 기준 이 비율 위치에 자막 상단 배치
SUB_STROKE        = 8      # 자막 검정 테두리 두께 (px)
SUB_MAX_WIDTH     = W - 240   # 840px (YouTube Shorts 우측 버튼 여백 고려)

MAX_SUB_LINES  = 1    # 최대 자막 줄 수 (1줄 고정)
TYPING_SPEED   = 12   # chars/sec 기준 (실제 속도는 오디오 길이에 맞게 보정됨)

# 타이틀 검정 테두리 두께
TITLE_STROKE = 4

# 애니메이션 효과 상수
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
    """균형 잡힌 줄바꿈: 각 줄 너비가 고르도록 분할 (한국어 최적화).
    greedy 방식(첫 줄 꽉 채우기) 대신 목표 너비(total/n_lines)에 맞게 균등 배분.
    """
    words = text.split()
    if not words:
        return [text] if text else []

    space_w     = draw.textlength(' ', font=font)
    word_widths = [draw.textlength(w, font=font) for w in words]
    total_w     = sum(word_widths) + space_w * max(0, len(words) - 1)

    # 한 줄에 들어가면 그대로 반환
    if total_w <= max_width:
        return [' '.join(words)]

    # 예상 줄 수 → 줄당 목표 너비
    n_lines  = max(2, int(total_w / max_width) + 1)
    target_w = total_w / n_lines

    lines, cur_words, cur_w = [], [], 0.0

    for w, ww in zip(words, word_widths):
        gap   = space_w if cur_words else 0.0
        new_w = cur_w + gap + ww

        if cur_words and new_w > max_width:
            # max_width 초과 → 강제 줄바꿈
            lines.append(' '.join(cur_words))
            cur_words, cur_w = [w], ww
        elif cur_words and cur_w >= target_w and len(lines) < n_lines - 1:
            # 목표 너비 도달 + 줄 여유 있음 → 균형 줄바꿈
            lines.append(' '.join(cur_words))
            cur_words, cur_w = [w], ww
        else:
            cur_words.append(w)
            cur_w = new_w

    if cur_words:
        lines.append(' '.join(cur_words))

    return lines


def _draw_centered_text(draw, text: str, y: int, font, fill,
                        max_width: int, line_gap: int = 12,
                        stroke_width: int = 0,
                        stroke_fill=None) -> int:
    for line in _wrap_text(draw, text, font, max_width):
        lw = draw.textlength(line, font=font)
        draw.text(
            ((W - lw) // 2, y), line, font=font, fill=fill,
            stroke_width=stroke_width, stroke_fill=stroke_fill,
        )
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


def _draw_title_multicolor(draw, title: str, y: int, font,
                            max_width: int, line_gap: int = 16,
                            stroke_width: int = 4) -> int:
    """타이틀을 줄 수에 따라 색상을 달리하여 그림.
    - 1줄: YELLOW
    - 2줄 이상: 마지막 줄만 YELLOW, 나머지는 WHITE
    """
    lines = _wrap_text(draw, title, font, max_width)
    total = len(lines)
    for idx, line in enumerate(lines):
        color = C_YELLOW if (total == 1 or idx == total - 1) else C_WHITE
        lw = draw.textlength(line, font=font)
        draw.text(
            ((W - lw) // 2, y), line, font=font, fill=color,
            stroke_width=stroke_width, stroke_fill=C_BLACK,
        )
        bbox = draw.textbbox((0, 0), line, font=font)
        y += (bbox[3] - bbox[1]) + line_gap
    return y


def _get_sub_font(title_font_size: int) -> ImageFont.FreeTypeFont:
    """자막 폰트: 타이틀 폰트 크기의 75% (가독성 확보)."""
    size = max(32, int(title_font_size * 0.75))
    return _get_font(size, bold=True)


def _line_char_ranges(narration: str, lines: list) -> list:
    """각 줄의 (start_char, end_char) 위치를 narration 원문 기준으로 반환."""
    result = []
    pos = 0
    for line in lines:
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
        scale  = 1.0 + 0.08 * prog
        crop_s = max(1, int(S / scale))
        x0     = (S - crop_s) // 2
        y0     = (S - crop_s) // 2
        region = img_arr[y0:y0 + crop_s, x0:x0 + crop_s]

    elif mode == 'pan_r':
        scale  = 1.1
        crop_s = max(1, int(S / scale))
        max_x  = S - crop_s
        y0     = (S - crop_s) // 2
        x0     = int(max_x * prog)
        region = img_arr[y0:y0 + crop_s, x0:x0 + crop_s]

    elif mode == 'zoom_pan':
        scale  = 1.0 + 0.10 * prog
        crop_s = max(1, int(S / scale))
        max_x  = max(0, S - crop_s)
        x0     = min(int(max_x * prog * 0.6), max_x)
        y0     = max(0, S - crop_s) // 2
        region = img_arr[y0:y0 + crop_s, x0:x0 + crop_s]

    else:
        return img_arr

    return np.array(
        Image.fromarray(region).resize((S, S), Image.BILINEAR)
    )


# ── 전환 효과 ─────────────────────────────────────────────────────────

def _trans_frame(prev_arr: np.ndarray, curr_arr: np.ndarray,
                 p: float, mode: str) -> np.ndarray:
    """두 이미지 사이 전환 효과."""
    S = IMG_SIZE
    p = max(0.0, min(1.0, p))

    if mode == 'slide':
        b_left = int(S * (1.0 - p))
        out = prev_arr.copy()
        if b_left < S:
            out[:, b_left:] = curr_arr[:, :S - b_left]
        return out

    elif mode == 'push':
        offset = int(S * p)
        out    = np.zeros_like(prev_arr)
        rem    = S - offset
        if rem > 0:
            out[:, :rem] = prev_arr[:, offset:]
        if offset > 0:
            out[:, rem:] = curr_arr[:, :offset]
        return out

    elif mode == 'wipe':
        boundary = int(S * p)
        out = prev_arr.copy()
        if boundary > 0:
            out[:, :boundary] = curr_arr[:, :boundary]
        return out

    return curr_arr


# ── 효과 팔레트 선택 ──────────────────────────────────────────────────

def _pick_effects(n_segs: int, seed: int) -> list:
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
    """제목 + 검정 배경만 렌더링 (이미지/자막 없음).
    반환: (PIL Image, img_y, sub_font, line_h, sub_y, pad)
    """
    pad   = 50
    frame = Image.new('RGB', (W, H), C_BLACK)
    draw  = ImageDraw.Draw(frame)

    title_font = _fit_title_font(draw, title, W - pad * 2, max_height=230)
    title_h    = _measure_text_height(draw, title, title_font, W - pad * 2)
    _draw_title_multicolor(
        draw, title, TITLE_TOP, title_font, W - pad * 2,
        line_gap=16, stroke_width=TITLE_STROKE,
    )

    img_y = max(IMG_Y, TITLE_TOP + title_h + 40)
    img_y = min(img_y, H - IMG_SIZE - 360)

    title_font_size = title_font.size if hasattr(title_font, 'size') else 96
    sub_font = _get_sub_font(title_font_size)
    _test_bb = sub_font.getbbox('Ag가')
    line_h   = (_test_bb[3] - _test_bb[1]) + 14

    # 자막 상단 y: 이미지 하단 25% 위치
    sub_y = img_y + int(IMG_SIZE * SUB_OVERLAY_RATIO) - line_h

    return frame, img_y, sub_font, line_h, sub_y, pad


def _make_base(title: str, image_path: str, narration: str = '') -> tuple:
    """자막 없이 제목 + 이미지만 렌더링 (make_frame 하위 호환용).
    반환: (PIL Image, img_y, sub_font, line_h, sub_y, pad)
    """
    pad   = 50
    frame = Image.new('RGB', (W, H), C_BLACK)
    draw  = ImageDraw.Draw(frame)

    title_font = _fit_title_font(draw, title, W - pad * 2, max_height=230)
    title_h    = _measure_text_height(draw, title, title_font, W - pad * 2)
    _draw_title_multicolor(
        draw, title, TITLE_TOP, title_font, W - pad * 2,
        line_gap=16, stroke_width=TITLE_STROKE,
    )

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

    title_font_size = title_font.size if hasattr(title_font, 'size') else 96
    sub_font = _get_sub_font(title_font_size)
    _test_bb = sub_font.getbbox('Ag가')
    line_h   = (_test_bb[3] - _test_bb[1]) + 14

    sub_y = img_y + int(IMG_SIZE * SUB_OVERLAY_RATIO) - line_h

    return frame, img_y, sub_font, line_h, sub_y, pad


def _draw_subtitle_on_frame(frame_pil: Image.Image, text: str,
                             sub_font, line_h: int, sub_y: int) -> None:
    """프레임(PIL Image)에 자막을 흰 글씨 + 검정 테두리로 직접 그림 (in-place)."""
    if not text:
        return
    draw  = ImageDraw.Draw(frame_pil)
    lines = _wrap_text(draw, text, sub_font, SUB_MAX_WIDTH)[:MAX_SUB_LINES]
    y     = sub_y
    for line in lines:
        lw = draw.textlength(line, font=sub_font)
        draw.text(
            ((W - lw) // 2, y), line,
            font=sub_font, fill=C_WHITE,
            stroke_width=SUB_STROKE, stroke_fill=C_BLACK,
        )
        y += line_h


def _draw_subtitle(base_img: Image.Image, text: str,
                   sub_font, line_h: int, sub_y: int, pad: int) -> np.ndarray:
    """베이스 이미지에 자막 text를 그린 numpy 배열 반환 (정적 프레임 용)."""
    img = base_img.copy()
    _draw_subtitle_on_frame(img, text, sub_font, line_h, sub_y)
    return np.array(img)


# ── 오디오 합치기 (ffmpeg) ────────────────────────────────────────────

def _concat_audio_ffmpeg(audio_paths: list, out_path: str) -> str:
    """ffmpeg로 여러 MP3를 순서대로 이어붙여 out_path에 저장."""
    if len(audio_paths) == 1:
        return audio_paths[0]
    input_args = []
    for p in audio_paths:
        input_args += ['-i', p]
    n = len(audio_paths)
    subprocess.run(
        ['ffmpeg', '-y'] + input_args +
        ['-filter_complex', f'concat=n={n}:v=0:a=1[out]',
         '-map', '[out]', out_path],
        check=True, capture_output=True,
    )
    return out_path


# ── 세그먼트 클립 생성 (세그먼트 = 1개 클립) ─────────────────────────

def _make_segment_clip(title: str, image_path: str,
                       timed_chunks: list,
                       combined_audio,
                       img_sq: np.ndarray = None,
                       prev_img_arr: np.ndarray = None,
                       kb_mode: str = 'zoom_in',
                       trans_mode: str = None):
    """
    세그먼트 전체를 하나의 VideoClip으로 생성.

    timed_chunks : [{'text', 't_start', 't_end'}, ...]
      t_start/t_end 는 combined_audio 의 타임라인과 1:1로 일치한다.
      (같은 AudioFileClip 객체로 duration을 재고 합쳤기 때문)
    combined_audio : concatenate_audioclips() 로 만든 AudioClip 객체
      → 파일 경로 아님 (파일 재로드 없이 동일 타임라인 보장)
    """
    if img_sq is None and image_path:
        img_sq = _load_img_sq(image_path)

    first_text = timed_chunks[0]['text'] if timed_chunks else ''
    base_img, img_y, sub_font, line_h, sub_y, pad = _make_base_bg(title, first_text)
    base_arr = np.array(base_img)

    # combined_audio.duration 을 기준으로 프레임 수 결정 (재로드 없음)
    duration     = combined_audio.duration
    total_frames = max(1, int(duration * FPS))

    # 청크별 줄 분할 사전 계산
    _ref_draw = ImageDraw.Draw(base_img.copy())
    chunk_lines = [
        _wrap_text(_ref_draw, c['text'], sub_font, SUB_MAX_WIDTH)[:MAX_SUB_LINES]
        for c in timed_chunks
    ]

    frames = []
    for i in range(total_frames):
        t    = i / FPS
        prog = min(t / max(duration, 0.001), 1.0)

        # 1. 베이스 복사
        frame_arr = base_arr.copy()

        # 2. 이미지 + KB(세그먼트 전체 기준) + 전환(첫 프레임만)
        if img_sq is not None:
            curr_img = _kb(img_sq, prog, kb_mode)
            if i < TRANS_F and trans_mode is not None and prev_img_arr is not None:
                p_eased  = _ease_in_out((i + 1) / TRANS_F)
                img_area = _trans_frame(prev_img_arr, curr_img, p_eased, trans_mode)
            else:
                img_area = curr_img
            frame_arr[img_y:img_y + IMG_SIZE, 0:IMG_SIZE] = img_area

        # 3. 현재 t에 해당하는 청크 자막 즉시 표시
        active_idx = len(timed_chunks) - 1
        for ci, c in enumerate(timed_chunks):
            if t < c['t_end']:
                active_idx = ci
                break

        lines = chunk_lines[active_idx]
        if lines:
            frame_pil = Image.fromarray(frame_arr)
            draw      = ImageDraw.Draw(frame_pil)
            y = sub_y
            for line in lines:
                lw = draw.textlength(line, font=sub_font)
                draw.text(
                    ((W - lw) // 2, y), line,
                    font=sub_font, fill=C_WHITE,
                    stroke_width=SUB_STROKE, stroke_fill=C_BLACK,
                )
                y += line_h
            frame_arr = np.array(frame_pil)

        frames.append(frame_arr)

    clip = ImageSequenceClip(frames, fps=FPS)
    if MOVIEPY_V2:
        clip = clip.with_audio(combined_audio)
    else:
        clip = clip.set_audio(combined_audio)

    font_size = getattr(sub_font, 'size', '?')
    chunk_summary = ' / '.join(c['text'][:12] for c in timed_chunks)
    print(f'   [세그먼트] {len(timed_chunks)}청크 | 폰트 {font_size}px'
          f' | {duration:.1f}s | KB={kb_mode} TRANS={trans_mode or "없음"}'
          f'\n             자막: {chunk_summary}')
    return clip


# ── 공개 API ──────────────────────────────────────────────────────────

def make_frame(title: str, image_path: str, narration: str,
               frame_path: str) -> str:
    """단일 정적 프레임 PNG 저장 (하위 호환용)"""
    base_img, img_y, sub_font, line_h, sub_y, pad = _make_base(
        title, image_path, narration
    )
    arr = _draw_subtitle(base_img, narration, sub_font, line_h, sub_y, pad)
    Image.fromarray(arr).save(frame_path)
    return frame_path


def compose_video(segments_data: list, title: str, output_path: str) -> str:
    """
    segments_data: [{'audio_path': ..., 'narration': ..., 'image_path': ..., 'index': ...}]
    줄 단위 타이핑 자막 + Ken Burns + 전환 효과로 영상 합성.
    """
    n_segs = len(segments_data)

    seed    = sum(ord(c) for c in title) if title else 42
    effects = _pick_effects(n_segs, seed)
    kb_set    = list(dict.fromkeys(e[0] for e in effects))
    trans_set = list(dict.fromkeys(e[1] for e in effects if e[1]))
    print(f'   [효과] KB={kb_set} / TRANS={trans_set} (시드={seed})')

    img_sqs = [_load_img_sq(seg.get('image_path', '')) for seg in segments_data]

    clips        = []
    prev_img_arr = None

    for i, seg in enumerate(segments_data):
        kb_mode, trans_mode = effects[i]

        # audio_chunks 우선 사용, 없으면 단일 audio_path/narration fallback
        raw_chunks = seg.get('audio_chunks') or [
            {'text': seg['narration'], 'audio_path': seg['audio_path']}
        ]

        # ── 핵심: 같은 AudioFileClip 객체로 duration 측정 + concat 동시 처리 ──
        # 파일 재로드 없이 동일 타임라인 보장 → 자막-오디오 싱크 오차 제거
        audio_clips = [AudioFileClip(c['audio_path']) for c in raw_chunks]

        timed_chunks = []
        elapsed = 0.0
        for c, aclip in zip(raw_chunks, audio_clips):
            timed_chunks.append({
                'text':    c['text'],
                't_start': elapsed,
                't_end':   elapsed + aclip.duration,
            })
            elapsed += aclip.duration

        combined_audio = (audio_clips[0] if len(audio_clips) == 1
                          else concatenate_audioclips(audio_clips))

        clip = _make_segment_clip(
            title          = title,
            image_path     = seg.get('image_path', ''),
            timed_chunks   = timed_chunks,
            combined_audio = combined_audio,
            img_sq         = img_sqs[i],
            prev_img_arr   = prev_img_arr,
            kb_mode        = kb_mode,
            trans_mode     = trans_mode,
        )
        clips.append(clip)

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
