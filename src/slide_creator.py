"""
Pillow 기반 슬라이드 PNG 생성 — Gamma 스타일
다크 네이비 배경, 카드 2개, 숫자 강조 슬라이드
"""
import os
import math
from datetime import date
from PIL import Image, ImageDraw, ImageFont

SLIDE_W, SLIDE_H = 1080, 1920

# Gamma 색상 팔레트
C_BG        = ( 13,  27,  62)   # 메인 네이비
C_BG_LIGHT  = ( 22,  42,  90)   # 살짝 밝은 네이비
C_CARD      = ( 28,  48, 100)   # 카드 배경
C_CARD2     = ( 35,  58, 115)   # 카드 호버
C_WHITE     = (255, 255, 255)
C_GRAY      = (160, 180, 220)
C_ACCENT    = ( 99, 179, 237)   # 연한 파랑 강조
C_BADGE_BG  = ( 40,  60, 120)
C_NUM       = (255, 255, 255)   # 숫자 색


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
                    max_width: int, font, fill, line_gap: int = 16) -> int:
    for line in _wrap_text(draw, text, font, max_width):
        draw.text((x, y), line, font=font, fill=fill)
        bbox = draw.textbbox((0, 0), line, font=font)
        y += (bbox[3] - bbox[1]) + line_gap
    return y


def _draw_bg(img: Image.Image):
    """다크 네이비 그라데이션 배경"""
    draw = ImageDraw.Draw(img)
    for i in range(SLIDE_H):
        t = i / SLIDE_H
        r = int(C_BG[0] + (C_BG_LIGHT[0] - C_BG[0]) * t * 0.4)
        g = int(C_BG[1] + (C_BG_LIGHT[1] - C_BG[1]) * t * 0.4)
        b = int(C_BG[2] + (C_BG_LIGHT[2] - C_BG[2]) * t * 0.4)
        draw.line([(0, i), (SLIDE_W, i)], fill=(r, g, b))


def _draw_geo_deco(draw, area_h: int = 600):
    """상단 기하학 장식 (X 패턴 + 원)"""
    # 큰 원 두 개 (반투명 느낌)
    circle_color = (30, 55, 115)
    draw.ellipse([(-100, -200), (500, 700)],  fill=circle_color)
    draw.ellipse([(650, -300), (1250, 550)], fill=circle_color)

    # X 대각선
    line_color = (40, 70, 140)
    lw = 18
    # 좌상→우하
    draw.line([(80, 0), (580, area_h)],  fill=line_color, width=lw)
    draw.line([(200, 0), (700, area_h)], fill=line_color, width=lw)
    # 우상→좌하
    draw.line([(SLIDE_W - 80,  0), (SLIDE_W - 580, area_h)], fill=line_color, width=lw)
    draw.line([(SLIDE_W - 200, 0), (SLIDE_W - 700, area_h)], fill=line_color, width=lw)

    # 상단 오버레이 (텍스트 가독성)
    for i in range(area_h):
        alpha = int(180 * (i / area_h) ** 1.5)
        r = int(C_BG[0] + (C_BG_LIGHT[0] - C_BG[0]) * (i / area_h))
        g = int(C_BG[1] + (C_BG_LIGHT[1] - C_BG[1]) * (i / area_h))
        b = int(C_BG[2] + (C_BG_LIGHT[2] - C_BG[2]) * (i / area_h))
        draw.line([(0, i), (SLIDE_W, i)],
                  fill=(r, g, b, alpha) if False else (r, g, b))


def _draw_badge(draw, x: int, y: int, emoji: str, text: str) -> int:
    """작은 pill 뱃지, 바텀 y 반환"""
    font = _get_font(34, bold=True)
    label = f'{emoji} {text}'
    w = int(draw.textlength(label, font=font)) + 44
    h = 60
    draw.rounded_rectangle([(x, y), (x + w, y + h)], radius=16, fill=C_BADGE_BG)
    draw.text((x + 22, y + 12), label, font=font, fill=C_GRAY)
    return y + h + 30


def _draw_card(draw, x1: int, y1: int, x2: int,
               title: str, body: str) -> int:
    """어두운 카드, 바텀 y 반환"""
    title_font = _get_font(46, bold=True)
    body_font  = _get_font(40)
    pad = 44

    # 제목 높이 측정
    title_lines = _wrap_text(draw, title, title_font, x2 - x1 - pad * 2)
    title_h = sum(
        draw.textbbox((0, 0), l, font=title_font)[3] + 10
        for l in title_lines
    )
    body_lines = _wrap_text(draw, body, body_font, x2 - x1 - pad * 2)
    body_h = sum(
        draw.textbbox((0, 0), l, font=body_font)[3] + 12
        for l in body_lines
    )
    card_h = pad + title_h + 20 + body_h + pad

    draw.rounded_rectangle([(x1, y1), (x2, y1 + card_h)],
                            radius=24, fill=C_CARD)

    y = y1 + pad
    for line in title_lines:
        draw.text((x1 + pad, y), line, font=title_font, fill=C_WHITE)
        bbox = draw.textbbox((0, 0), line, font=title_font)
        y += bbox[3] + 10
    y += 8
    for line in body_lines:
        draw.text((x1 + pad, y), line, font=body_font, fill=C_GRAY)
        bbox = draw.textbbox((0, 0), line, font=body_font)
        y += bbox[3] + 12

    return y1 + card_h


def _make_title_slide(title: str, subtitle: str) -> Image.Image:
    img  = Image.new('RGB', (SLIDE_W, SLIDE_H), C_BG)
    _draw_bg(img)
    draw = ImageDraw.Draw(img)

    # 상단 기하학 장식
    _draw_geo_deco(draw, area_h=680)

    # 뱃지
    badge_y = _draw_badge(draw, 60, 730, '🔥', '속보')

    # 메인 제목
    title_font = _get_font(88, bold=True)
    y = _draw_multiline(draw, title, 60, badge_y + 10,
                        SLIDE_W - 120, title_font, C_WHITE, line_gap=20)

    # 서브타이틀
    sub_font = _get_font(42)
    y += 30
    _draw_multiline(draw, subtitle, 60, y,
                    SLIDE_W - 120, sub_font, C_GRAY, line_gap=16)

    # 하단 스크롤 힌트
    hint_font = _get_font(36)
    draw.text((60, SLIDE_H - 120),
              '👇 스크롤해서 확인하세요', font=hint_font, fill=C_GRAY)

    return img


def _make_card_slide(slide_data: dict) -> Image.Image:
    """카드 2개 슬라이드"""
    img  = Image.new('RGB', (SLIDE_W, SLIDE_H), C_BG)
    _draw_bg(img)
    draw = ImageDraw.Draw(img)

    _draw_geo_deco(draw, area_h=560)

    # 뱃지
    emoji   = slide_data.get('emoji', '•')
    heading = slide_data.get('heading', '')
    badge_y = _draw_badge(draw, 60, 600, emoji, heading)

    # 큰 제목
    title_font = _get_font(78, bold=True)
    y = _draw_multiline(draw, slide_data.get('title_big', heading),
                        60, badge_y,
                        SLIDE_W - 120, title_font, C_WHITE, line_gap=16)

    y += 50
    # 카드 1
    c1 = slide_data.get('card1', {})
    y = _draw_card(draw, 60, y, SLIDE_W - 60,
                   c1.get('title', ''), c1.get('body', ''))
    y += 30
    # 카드 2
    c2 = slide_data.get('card2', {})
    _draw_card(draw, 60, y, SLIDE_W - 60,
               c2.get('title', ''), c2.get('body', ''))

    return img


def _make_stat_slide(slide_data: dict) -> Image.Image:
    """숫자 강조 슬라이드"""
    img  = Image.new('RGB', (SLIDE_W, SLIDE_H), C_BG)
    _draw_bg(img)
    draw = ImageDraw.Draw(img)

    # 뱃지 + 제목
    emoji   = slide_data.get('emoji', '•')
    heading = slide_data.get('heading', '')
    badge_y = _draw_badge(draw, 60, 160, emoji, heading)

    title_font = _get_font(78, bold=True)
    y = _draw_multiline(draw, slide_data.get('title_big', heading),
                        60, badge_y,
                        SLIDE_W - 120, title_font, C_WHITE, line_gap=16)

    y += 80
    # 통계 2개
    for stat in slide_data.get('stats', [])[:2]:
        # 큰 숫자
        num_font = _get_font(160, bold=True)
        num = stat.get('number', '')
        nw  = draw.textlength(num, font=num_font)
        draw.text(((SLIDE_W - nw) // 2, y), num, font=num_font, fill=C_WHITE)
        bbox = draw.textbbox((0, 0), num, font=num_font)
        y += bbox[3] + 10

        # 레이블 (굵음)
        label_font = _get_font(46, bold=True)
        lw = draw.textlength(stat.get('label', ''), font=label_font)
        draw.text(((SLIDE_W - lw) // 2, y),
                  stat.get('label', ''), font=label_font, fill=C_ACCENT)
        y += 56

        # 설명
        desc_font = _get_font(38)
        dw = draw.textlength(stat.get('desc', ''), font=desc_font)
        draw.text(((SLIDE_W - dw) // 2, y),
                  stat.get('desc', ''), font=desc_font, fill=C_GRAY)
        y += 100

    return img


def create_slides(script_data: dict, out_dir: str) -> list:
    os.makedirs(out_dir, exist_ok=True)
    slides = script_data.get('slides', [])
    paths  = []

    # 타이틀
    p = os.path.join(out_dir, 'slide_00.png')
    _make_title_slide(
        script_data['title'],
        script_data.get('subtitle', script_data.get('description', ''))
    ).save(p)
    paths.append(p)

    # 본문
    for i, s in enumerate(slides[:3], 1):
        p = os.path.join(out_dir, f'slide_{i:02d}.png')
        if s.get('type') == 'stat':
            _make_stat_slide(s).save(p)
        else:
            _make_card_slide(s).save(p)
        paths.append(p)

    return paths
