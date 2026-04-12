"""
Pillow 기반 슬라이드 PNG 직접 생성 (python-pptx + LibreOffice 불필요)
"""
import os
from datetime import date
from PIL import Image, ImageDraw, ImageFont

SLIDE_W, SLIDE_H = 1080, 1920

# 색상
C_BG_DARK   = (13,  17,  23)
C_CARD      = (22,  33,  50)
C_ACCENT    = (56, 189, 248)   # sky-400
C_ACCENT2   = (99, 102, 241)   # indigo-500
C_WHITE     = (255, 255, 255)
C_GRAY      = (148, 163, 184)
C_BG_LIGHT  = (241, 245, 249)
C_DARK_TEXT = (15,  23,  42)
C_SUB_TEXT  = (71,  85, 105)


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        # Ubuntu / GitHub Actions
        '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf' if bold
            else '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
        '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
        # Windows 로컬
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
    """텍스트를 max_width에 맞게 줄 분리"""
    words = text.split()
    lines, current = [], ''
    for word in words:
        test = f'{current} {word}'.strip()
        w = draw.textlength(test, font=font)
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_text_block(draw, text: str, x: int, y: int,
                     max_width: int, font, fill, line_gap: int = 12) -> int:
    """여러 줄 텍스트 렌더링, 다음 y 반환"""
    lines = _wrap_text(draw, text, font, max_width)
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        bbox = draw.textbbox((0, 0), line, font=font)
        y += (bbox[3] - bbox[1]) + line_gap
    return y


def _make_title_slide(title: str) -> Image.Image:
    img  = Image.new('RGB', (SLIDE_W, SLIDE_H), C_BG_DARK)
    draw = ImageDraw.Draw(img)

    # 상단 그라데이션 느낌 밴드
    for i in range(300):
        ratio = i / 300
        r = int(13  + (22  - 13)  * ratio)
        g = int(17  + (33  - 17)  * ratio)
        b = int(23  + (50  - 23)  * ratio)
        draw.line([(0, i), (SLIDE_W, i)], fill=(r, g, b))

    # 상단 accent 라인
    draw.rectangle([(0, 0), (SLIDE_W, 6)], fill=C_ACCENT)

    # 중앙 카드
    card_x1, card_y1 = 60, 560
    card_x2, card_y2 = SLIDE_W - 60, 1360
    draw.rounded_rectangle([(card_x1, card_y1), (card_x2, card_y2)],
                            radius=32, fill=C_CARD)
    # 카드 좌측 accent 세로선
    draw.rectangle([(card_x1, card_y1 + 40), (card_x1 + 6, card_y2 - 40)],
                   fill=C_ACCENT)

    # SHORTS 뱃지
    badge_font = _get_font(30, bold=True)
    draw.rounded_rectangle([(card_x1 + 40, card_y1 + 50),
                             (card_x1 + 230, card_y1 + 100)],
                            radius=14, fill=C_ACCENT)
    draw.text((card_x1 + 55, card_y1 + 58), 'SHORTS NEWS',
              font=badge_font, fill=C_BG_DARK)

    # 제목
    title_font = _get_font(68, bold=True)
    _draw_text_block(draw, title,
                     card_x1 + 40, card_y1 + 130,
                     card_x2 - card_x1 - 80,
                     title_font, C_WHITE, line_gap=18)

    # 날짜
    date_font = _get_font(34)
    draw.text((card_x1 + 40, card_y2 - 80),
              date.today().strftime('%Y. %m. %d'),
              font=date_font, fill=C_GRAY)

    # 하단 accent 라인
    draw.rectangle([(0, SLIDE_H - 6), (SLIDE_W, SLIDE_H)], fill=C_ACCENT2)

    return img


def _make_content_slide(slide_data: dict, slide_num: int, total: int) -> Image.Image:
    img  = Image.new('RGB', (SLIDE_W, SLIDE_H), C_BG_LIGHT)
    draw = ImageDraw.Draw(img)

    # 상단 다크 헤더 영역
    header_h = 220
    draw.rectangle([(0, 0), (SLIDE_W, header_h)], fill=C_BG_DARK)
    draw.rectangle([(0, 0), (SLIDE_W, 6)], fill=C_ACCENT)

    # 슬라이드 번호 (헤더 우측)
    num_font = _get_font(34)
    num_text = f'{slide_num} / {total}'
    draw.text((SLIDE_W - 140, 80), num_text, font=num_font, fill=C_GRAY)

    # 이모지 + 소제목 (헤더 안)
    emoji = slide_data.get('emoji', '•')
    heading = slide_data.get('heading', '')
    head_font = _get_font(52, bold=True)
    draw.text((60, 80), f'{emoji}  {heading}',
              font=head_font, fill=C_WHITE)

    # 본문 카드
    card_y = header_h + 60
    draw.rounded_rectangle([(60, card_y), (SLIDE_W - 60, SLIDE_H - 180)],
                            radius=28, fill=C_WHITE)
    # 카드 좌측 컬러 세로선
    draw.rectangle([(60, card_y + 30), (66, card_y + 130)], fill=C_ACCENT2)

    # 본문 텍스트
    body_font = _get_font(46)
    _draw_text_block(draw, slide_data.get('body', ''),
                     110, card_y + 60,
                     SLIDE_W - 200,
                     body_font, C_DARK_TEXT, line_gap=22)

    # 하단 진행 바
    bar_y = SLIDE_H - 100
    bar_w = SLIDE_W - 120
    draw.rounded_rectangle([(60, bar_y), (60 + bar_w, bar_y + 16)],
                            radius=8, fill=(203, 213, 225))
    filled = int(bar_w * slide_num / total)
    draw.rounded_rectangle([(60, bar_y), (60 + filled, bar_y + 16)],
                            radius=8, fill=C_ACCENT)

    # 하단 accent 라인
    draw.rectangle([(0, SLIDE_H - 6), (SLIDE_W, SLIDE_H)], fill=C_ACCENT2)

    return img


def create_slides(script_data: dict, out_dir: str) -> list:
    """슬라이드 PNG 생성 → 파일 경로 리스트 반환"""
    os.makedirs(out_dir, exist_ok=True)
    slides_data = script_data.get('slides', [])[:3]
    total = len(slides_data)
    paths = []

    # 타이틀 슬라이드
    title_path = os.path.join(out_dir, 'slide_00.png')
    _make_title_slide(script_data['title']).save(title_path)
    paths.append(title_path)

    # 본문 슬라이드
    for i, s in enumerate(slides_data, 1):
        path = os.path.join(out_dir, f'slide_{i:02d}.png')
        _make_content_slide(s, i, total).save(path)
        paths.append(path)

    return paths
