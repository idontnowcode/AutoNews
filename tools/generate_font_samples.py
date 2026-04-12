"""
폰트 샘플 10종 생성 — 각 폰트 조합으로 sample_font_N.png 저장
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
C_BLACK  = (0,   0,   0)
C_YELLOW = (255, 214,  10)
C_WHITE  = (255, 255, 255)
C_GRAY   = (80,  80,  80)

TITLE_TOP = 120
IMG_Y     = 360
IMG_SIZE  = 1080
SUB_Y     = H - 340

TITLE_TEXT = "'금리'란 무엇인가?"
SUB_TEXT   = "금리가 오르면 대출 이자도 함께 올라갑니다"

FONT_DIR = "C:/Windows/Fonts"

FONT_COMBOS = [
    ("01_malgun_bold",        "malgunbd.ttf",        "malgunbd.ttf",        "Malgun Gothic Bold × Bold (현재)"),
    ("02_malgun_regular_bold","malgun.ttf",           "malgunbd.ttf",        "Malgun 제목 Regular / 자막 Bold"),
    ("03_noto_sans",          "NotoSansKR-VF.ttf",   "NotoSansKR-VF.ttf",   "Noto Sans KR × (Variable)"),
    ("04_noto_serif_title",   "NotoSerifKR-VF.ttf",  "NotoSansKR-VF.ttf",   "Noto Serif 제목 / Noto Sans 자막"),
    ("05_batang_title",       "batang.ttc",           "malgunbd.ttf",        "Batang 제목(명조) / Malgun 자막"),
    ("06_gothic_bold",        "GOTHICB.TTF",          "GOTHICB.TTF",         "Gothic Bold × Bold"),
    ("07_gothic_regular",     "GOTHIC.TTF",           "GOTHICB.TTF",         "Gothic 제목 / Gothic Bold 자막"),
    ("08_gulim",              "gulim.ttc",             "malgunbd.ttf",        "Gulim 제목 / Malgun Bold 자막"),
    ("09_ngulim",             "NGULIM.TTF",            "malgunbd.ttf",        "New Gulim 제목 / Malgun Bold 자막"),
    ("10_malgun_semilight",   "malgunsl.ttf",          "malgunbd.ttf",        "Malgun Semilight 제목 / Bold 자막"),
]

DUMMY_IMG = os.path.join(os.path.dirname(__file__), '..', 'output', 'sample_dummy_img.png')

def make_dummy_image():
    """더미 경제 이미지 (그라데이션 + 중앙 텍스트)"""
    img = Image.new('RGB', (IMG_SIZE, IMG_SIZE), (20, 20, 40))
    draw = ImageDraw.Draw(img)
    # 간단한 도형으로 경제 아이콘 흉내
    draw.ellipse([340, 340, 740, 740], fill=(255, 214, 10), outline=(255, 255, 255), width=8)
    draw.polygon([(540, 250), (600, 450), (480, 450)], fill=(0, 200, 100))  # 상승 화살표
    img.save(DUMMY_IMG)

def load_font(filename, size):
    path = os.path.join(FONT_DIR, filename)
    if not os.path.exists(path):
        print(f"  ⚠️  폰트 없음: {filename}, 기본 폰트 사용")
        return ImageFont.load_default()
    try:
        return ImageFont.truetype(path, size)
    except Exception as e:
        print(f"  ⚠️  로드 실패 {filename}: {e}")
        return ImageFont.load_default()

def draw_centered(draw, text, y, font, fill, max_w, gap=12):
    lw = draw.textlength(text, font=font)
    if lw > max_w:
        # 너무 길면 두 줄
        mid = len(text) // 2
        for c in range(mid, 0, -1):
            if text[c] in (' ', '·'):
                lines = [text[:c], text[c+1:]]
                break
        else:
            lines = [text]
    else:
        lines = [text]

    for line in lines:
        lw = draw.textlength(line, font=font)
        draw.text(((W - lw) // 2, y), line, font=font, fill=fill)
        bbox = draw.textbbox((0, 0), line, font=font)
        y += (bbox[3] - bbox[1]) + gap
    return y

def make_sample(out_path, title_font_file, sub_font_file, label):
    frame = Image.new('RGB', (W, H), C_BLACK)
    draw  = ImageDraw.Draw(frame)
    pad   = 50

    # 제목
    tf = load_font(title_font_file, 96)
    draw_centered(draw, TITLE_TEXT, TITLE_TOP, tf, C_YELLOW, W - pad * 2, gap=16)

    # 더미 이미지
    if os.path.exists(DUMMY_IMG):
        img = Image.open(DUMMY_IMG).convert('RGB')
        img = img.resize((IMG_SIZE, IMG_SIZE), Image.LANCZOS)
        frame.paste(img, (0, IMG_Y))

    # 자막
    sf = load_font(sub_font_file, 72)
    lw = draw.textlength(SUB_TEXT, font=sf)
    if lw > W - pad * 2:
        # 한 줄 넘치면 크기 줄임
        sf = load_font(sub_font_file, 56)
        lw = draw.textlength(SUB_TEXT, font=sf)
    draw.text(((W - lw) // 2, SUB_Y), SUB_TEXT, font=sf, fill=C_WHITE)

    # 폰트 이름 라벨 (우하단 작은 글씨)
    lf = load_font("malgun.ttf", 32)
    label_w = draw.textlength(label, font=lf)
    draw.text(((W - label_w) // 2, H - 80), label, font=lf, fill=C_GRAY)

    frame.save(out_path)
    print(f"  ✅ {os.path.basename(out_path)}")

if __name__ == '__main__':
    out_dir = os.path.join(os.path.dirname(__file__), '..', 'output', 'font_samples')
    os.makedirs(out_dir, exist_ok=True)
    make_dummy_image()

    print(f"\n🎨 폰트 샘플 {len(FONT_COMBOS)}종 생성 중...\n")
    for slug, title_f, sub_f, label in FONT_COMBOS:
        out = os.path.join(out_dir, f"sample_{slug}.png")
        print(f"  → {label}")
        make_sample(out, title_f, sub_f, label)

    print(f"\n✅ 완료: output/font_samples/")
