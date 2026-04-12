"""
Pillow 기반 슬라이드 PNG 직접 생성
디자인: Breaking News 스타일 (빨강 타이틀 + 투카드 본문)
"""
import os
from datetime import date
from PIL import Image, ImageDraw, ImageFont

SLIDE_W, SLIDE_H = 1080, 1920

# 색상
C_RED       = (220,  40,  40)
C_RED_DARK  = (180,  20,  20)
C_YELLOW    = (255, 214,  10)
C_BLACK     = ( 20,  20,  20)
C_WHITE     = (255, 255, 255)
C_CARD_BG   = (245, 245, 245)
C_GRAY_BG   = (230, 230, 230)
C_DARK_PILL = ( 30,  30,  30)
C_RED_TEXT  = (210,  30,  30)


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf' if bold
            else '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
        '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
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
    lines, current = [], ''
    for word in words:
        test = f'{current} {word}'.strip()
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_multiline(draw, text: str, x: int, y: int,
                    max_width: int, font, fill, line_gap: int = 14) -> int:
    for line in _wrap_text(draw, text, font, max_width):
        draw.text((x, y), line, font=font, fill=fill)
        bbox = draw.textbbox((0, 0), line, font=font)
        y += (bbox[3] - bbox[1]) + line_gap
    return y


def _draw_pill(draw, x1, y1, x2, y2, fill, radius=30):
    draw.rounded_rectangle([(x1, y1), (x2, y2)], radius=radius, fill=fill)


def _make_title_slide(title: str) -> Image.Image:
    img  = Image.new('RGB', (SLIDE_W, SLIDE_H), C_RED)
    draw = ImageDraw.Draw(img)

    # 배경 미묘한 그라데이션 (아래로 살짝 어둡게)
    for i in range(SLIDE_H):
        ratio = i / SLIDE_H * 0.25
        r = max(0, C_RED[0] - int(40 * ratio))
        g = max(0, C_RED[1] - int(10 * ratio))
        b = max(0, C_RED[2] - int(10 * ratio))
        draw.line([(0, i), (SLIDE_W, i)], fill=(r, g, b))

    # BREAKING 뱃지
    badge_font = _get_font(44, bold=True)
    badge_text = '⚡ BREAKING'
    badge_w = int(draw.textlength(badge_text, font=badge_font)) + 60
    bx = (SLIDE_W - badge_w) // 2
    _draw_pill(draw, bx, 160, bx + badge_w, 240, C_YELLOW, radius=24)
    draw.text((bx + 30, 170), badge_text, font=badge_font, fill=C_BLACK)

    # 메인 제목 (큰 흰 텍스트, 마지막 줄 노란색)
    title_font = _get_font(100, bold=True)
    pad = 80
    lines = _wrap_text(draw, title, title_font, SLIDE_W - pad * 2)

    total_h = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        total_h += (bbox[3] - bbox[1]) + 20

    y = (SLIDE_H - total_h) // 2 - 100
    for idx, line in enumerate(lines):
        color = C_YELLOW if idx == len(lines) - 1 else C_WHITE
        draw.text((pad, y), line, font=title_font, fill=color)
        bbox = draw.textbbox((0, 0), line, font=title_font)
        y += (bbox[3] - bbox[1]) + 20

    # 날짜 pill (하단)
    date_font = _get_font(38, bold=True)
    date_str = f'● {date.today().strftime("%Y.%m.%d")}  핫뉴스'
    date_w = int(draw.textlength(date_str, font=date_font)) + 60
    dx = (SLIDE_W - date_w) // 2
    _draw_pill(draw, dx, SLIDE_H - 200, dx + date_w, SLIDE_H - 130,
               C_DARK_PILL, radius=30)
    draw.text((dx + 30, SLIDE_H - 190), date_str, font=date_font, fill=C_WHITE)

    return img


def _make_content_slide(slide_data: dict, body2: str, teaser: str) -> Image.Image:
    img  = Image.new('RGB', (SLIDE_W, SLIDE_H), C_WHITE)
    draw = ImageDraw.Draw(img)

    # 상단 검정 헤더
    header_h = 170
    draw.rectangle([(0, 0), (SLIDE_W, header_h)], fill=C_BLACK)

    emoji   = slide_data.get('emoji', '•')
    heading = slide_data.get('heading', '')
    head_font = _get_font(62, bold=True)
    head_text = f'{emoji}  {heading}'
    hw = draw.textlength(head_text, font=head_font)
    draw.text(((SLIDE_W - hw) // 2, 52), head_text, font=head_font, fill=C_WHITE)

    # 흰 카드 (본문 1)
    body_font  = _get_font(52, bold=False)
    bold_font  = _get_font(52, bold=True)
    card1_y1, card1_y2 = 220, 760
    draw.rounded_rectangle([(60, card1_y1), (SLIDE_W - 60, card1_y2)],
                            radius=28, fill=C_CARD_BG)

    body1 = slide_data.get('body', '')
    _draw_multiline(draw, body1, 100, card1_y1 + 60,
                    SLIDE_W - 260, body_font, C_BLACK, line_gap=22)

    # 카드 우측 이모지 (크게)
    em_font = _get_font(90)
    draw.text((SLIDE_W - 200, card1_y2 - 160), emoji, font=em_font, fill=C_BLACK)

    # 노란 카드 (본문 2 — 핵심 임팩트)
    card2_y1, card2_y2 = 820, 1440
    draw.rounded_rectangle([(60, card2_y1), (SLIDE_W - 60, card2_y2)],
                            radius=28, fill=C_YELLOW)

    _draw_multiline(draw, body2, 100, card2_y1 + 60,
                    SLIDE_W - 260, bold_font, C_BLACK, line_gap=22)

    # 하단 dark pill (티저 문구)
    teaser_font = _get_font(38, bold=True)
    teaser_w = int(draw.textlength(teaser, font=teaser_font)) + 60
    tx = (SLIDE_W - teaser_w) // 2
    _draw_pill(draw, tx, SLIDE_H - 200, tx + teaser_w, SLIDE_H - 120,
               C_DARK_PILL, radius=30)
    draw.text((tx + 30, SLIDE_H - 194), teaser, font=teaser_font, fill=C_WHITE)

    return img


def create_slides(script_data: dict, out_dir: str) -> list:
    """슬라이드 PNG 생성 → 파일 경로 리스트 반환"""
    os.makedirs(out_dir, exist_ok=True)
    slides = script_data.get('slides', [])[:3]
    paths  = []

    # 타이틀 슬라이드
    p = os.path.join(out_dir, 'slide_00.png')
    _make_title_slide(script_data['title']).save(p)
    paths.append(p)

    # 본문 슬라이드 — slides에 body2, teaser 필드 활용 (없으면 fallback)
    for i, s in enumerate(slides, 1):
        body2  = s.get('body2',  s.get('body', ''))
        teaser = s.get('teaser', '')
        p = os.path.join(out_dir, f'slide_{i:02d}.png')
        _make_content_slide(s, body2, teaser).save(p)
        paths.append(p)

    return paths
