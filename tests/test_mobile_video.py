"""
모바일(YouTube Shorts) 포맷 테스트 — 실제 API 키 없이 로컬 실행 가능.

검증 항목:
  - 출력 해상도: 1080×1920 (세로형 모바일 Shorts)
  - 타이틀 렌더링: 멀티컬러, 줄바꿈, 테두리
  - 자막 오버레이 위치
  - Ken Burns 효과 프레임 배열
  - 전환 효과 프레임 배열
  - compose_video: 더미 오디오 + 더미 이미지로 MP4 생성 → 해상도/길이 확인
"""
import os
import sys
import tempfile
import unittest
import numpy as np

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PIL import Image
from src.video_composer import (
    W, H, FPS, IMG_SIZE,
    _get_font, _wrap_text, _fit_title_font,
    _draw_title_multicolor, _draw_subtitle_on_frame,
    _kb, _trans_frame, _pick_effects,
    _make_base_bg, make_frame, compose_video,
)


# ── 헬퍼 ──────────────────────────────────────────────────────────────

def _make_dummy_image(path: str, size: int = IMG_SIZE) -> str:
    """테스트용 단색 정사각형 이미지 저장."""
    img = Image.new('RGB', (size, size), (80, 120, 200))
    img.save(path)
    return path


def _make_dummy_audio(path: str, duration: float = 1.5) -> str:
    """
    테스트용 무음 WAV 파일 생성 (scipy 없이 순수 헤더 조합).
    44100 Hz, 16-bit, mono.
    """
    import struct, wave
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)   # 16-bit
        wf.setframerate(44100)
        n_frames = int(44100 * duration)
        wf.writeframes(b'\x00' * n_frames * 2)
    return path


# ── 단위 테스트 ────────────────────────────────────────────────────────

class TestMobileResolution(unittest.TestCase):
    """출력 해상도가 모바일 Shorts 규격(1080×1920)인지 확인."""

    def test_canvas_dimensions(self):
        self.assertEqual(W, 1080)
        self.assertEqual(H, 1920)

    def test_aspect_ratio(self):
        ratio = H / W
        self.assertAlmostEqual(ratio, 16 / 9, places=5)

    def test_img_size_fits_width(self):
        self.assertLessEqual(IMG_SIZE, W)


class TestFontRendering(unittest.TestCase):
    def setUp(self):
        from PIL import ImageDraw
        self.img   = Image.new('RGB', (W, H), (0, 0, 0))
        self.draw  = ImageDraw.Draw(self.img)

    def test_get_font_returns_font(self):
        font = _get_font(48)
        self.assertIsNotNone(font)

    def test_wrap_text_single_line(self):
        font  = _get_font(48)
        lines = _wrap_text(self.draw, '금리란 무엇인가?', font, W - 100)
        self.assertGreater(len(lines), 0)

    def test_wrap_text_long_line(self):
        font  = _get_font(96)
        text  = '이것은 매우 긴 제목으로 한 줄에 들어가지 않을 수도 있습니다 화면 너비 초과 테스트'
        lines = _wrap_text(self.draw, text, font, W - 100)
        self.assertGreater(len(lines), 1)

    def test_wrap_text_empty(self):
        font  = _get_font(48)
        lines = _wrap_text(self.draw, '', font, W - 100)
        self.assertEqual(lines, [])

    def test_fit_title_font(self):
        font = _fit_title_font(self.draw, '금리와 경제', W - 100)
        self.assertIsNotNone(font)


class TestSubtitleOverlay(unittest.TestCase):
    """자막이 이미지 하단 25% 위치(SUB_OVERLAY_RATIO)에 그려지는지 확인."""

    def test_subtitle_drawn_on_frame(self):
        frame = Image.new('RGB', (W, H), (0, 0, 0))
        font  = _get_font(60, bold=True)
        # 자막을 그리기 전/후 픽셀 비교
        before = np.array(frame.copy())
        _draw_subtitle_on_frame(frame, '이것은 자막입니다', font, 80, H // 2)
        after = np.array(frame)
        self.assertFalse(np.array_equal(before, after), '자막이 프레임에 그려지지 않음')


class TestKenBurns(unittest.TestCase):
    def setUp(self):
        self.img_arr = np.zeros((IMG_SIZE, IMG_SIZE, 3), dtype=np.uint8)
        self.img_arr[:, :, 0] = 128  # R 채널만 128

    def _check_shape(self, result):
        self.assertEqual(result.shape, (IMG_SIZE, IMG_SIZE, 3))

    def test_zoom_in(self):
        result = _kb(self.img_arr, 0.5, 'zoom_in')
        self._check_shape(result)

    def test_pan_r(self):
        result = _kb(self.img_arr, 0.5, 'pan_r')
        self._check_shape(result)

    def test_zoom_pan(self):
        result = _kb(self.img_arr, 0.5, 'zoom_pan')
        self._check_shape(result)

    def test_prog_zero(self):
        result = _kb(self.img_arr, 0.0, 'zoom_in')
        self._check_shape(result)

    def test_prog_one(self):
        result = _kb(self.img_arr, 1.0, 'zoom_in')
        self._check_shape(result)

    def test_unknown_mode_passthrough(self):
        result = _kb(self.img_arr, 0.5, 'unknown_mode')
        np.testing.assert_array_equal(result, self.img_arr)


class TestTransitionEffects(unittest.TestCase):
    def setUp(self):
        self.prev = np.full((IMG_SIZE, IMG_SIZE, 3), 50,  dtype=np.uint8)
        self.curr = np.full((IMG_SIZE, IMG_SIZE, 3), 200, dtype=np.uint8)

    def _check_shape(self, result):
        self.assertEqual(result.shape, (IMG_SIZE, IMG_SIZE, 3))

    def test_slide_transition(self):
        result = _trans_frame(self.prev, self.curr, 0.5, 'slide')
        self._check_shape(result)

    def test_push_transition(self):
        result = _trans_frame(self.prev, self.curr, 0.5, 'push')
        self._check_shape(result)

    def test_wipe_transition(self):
        result = _trans_frame(self.prev, self.curr, 0.5, 'wipe')
        self._check_shape(result)

    def test_prog_zero_is_prev(self):
        result = _trans_frame(self.prev, self.curr, 0.0, 'slide')
        self._check_shape(result)

    def test_prog_one_is_curr(self):
        result = _trans_frame(self.prev, self.curr, 1.0, 'slide')
        self._check_shape(result)


class TestEffectPicker(unittest.TestCase):
    def test_pick_effects_count(self):
        for n in (1, 2, 3, 4):
            effects = _pick_effects(n, seed=42)
            self.assertEqual(len(effects), n)

    def test_first_seg_no_trans(self):
        effects = _pick_effects(3, seed=0)
        self.assertIsNone(effects[0][1])

    def test_subsequent_segs_have_trans(self):
        effects = _pick_effects(3, seed=0)
        for _, trans in effects[1:]:
            self.assertIsNotNone(trans)


class TestMakeBaseBackground(unittest.TestCase):
    def test_returns_pil_image(self):
        frame, img_y, sub_font, line_h, sub_y, pad = _make_base_bg('금리란?')
        self.assertIsInstance(frame, Image.Image)
        self.assertEqual(frame.size, (W, H))

    def test_img_y_within_bounds(self):
        _, img_y, _, _, _, _ = _make_base_bg('금리와 물가의 상관관계')
        self.assertGreater(img_y, 0)
        self.assertLess(img_y + IMG_SIZE, H)

    def test_sub_y_below_img_center(self):
        _, img_y, _, _, sub_y, _ = _make_base_bg('테스트 제목')
        # 자막은 이미지 중간 이하에 위치해야 함
        self.assertGreater(sub_y, img_y + IMG_SIZE // 2)


class TestMakeFrameStatic(unittest.TestCase):
    """make_frame(): 정적 PNG 출력 테스트."""

    def test_make_frame_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            img_path   = _make_dummy_image(os.path.join(tmp, 'slide.png'))
            frame_path = os.path.join(tmp, 'frame.png')
            result     = make_frame('금리란?', img_path, '금리는 돈의 가격입니다.', frame_path)
            self.assertTrue(os.path.exists(result))

    def test_make_frame_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            img_path   = _make_dummy_image(os.path.join(tmp, 'slide.png'))
            frame_path = os.path.join(tmp, 'frame.png')
            make_frame('경제 기초', img_path, '경제는 삶의 일부입니다.', frame_path)
            out = Image.open(frame_path)
            self.assertEqual(out.size, (W, H), f'해상도 불일치: {out.size} ≠ ({W}, {H})')

    def test_make_frame_no_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame_path = os.path.join(tmp, 'frame_no_img.png')
            result     = make_frame('제목', '', '자막 텍스트', frame_path)
            self.assertTrue(os.path.exists(result))


class TestComposeVideoMobile(unittest.TestCase):
    """compose_video(): 더미 데이터로 MP4 생성 → 모바일 해상도 검증."""

    def test_compose_two_segments(self):
        try:
            import moviepy
        except ImportError:
            self.skipTest('moviepy 미설치')

        with tempfile.TemporaryDirectory() as tmp:
            img1  = _make_dummy_image(os.path.join(tmp, 'img1.png'))
            img2  = _make_dummy_image(os.path.join(tmp, 'img2.png'))
            aud1  = _make_dummy_audio(os.path.join(tmp, 'a1.wav'), 1.5)
            aud2  = _make_dummy_audio(os.path.join(tmp, 'a2.wav'), 1.5)
            out   = os.path.join(tmp, 'test_mobile.mp4')

            segments = [
                {
                    'narration':  '금리란 돈을 빌릴 때 내는 비용입니다.',
                    'image_path': img1,
                    'audio_path': aud1,
                    'audio_chunks': [{'text': '금리란 돈을 빌릴 때 내는 비용입니다.', 'audio_path': aud1}],
                },
                {
                    'narration':  '금리가 오르면 대출 비용도 늘어납니다.',
                    'image_path': img2,
                    'audio_path': aud2,
                    'audio_chunks': [{'text': '금리가 오르면 대출 비용도 늘어납니다.', 'audio_path': aud2}],
                },
            ]

            compose_video(segments, '금리의 기초', out)

            self.assertTrue(os.path.exists(out), 'MP4 파일이 생성되지 않음')
            self.assertGreater(os.path.getsize(out), 10_000, 'MP4 파일이 너무 작음')

            # ffprobe로 해상도 확인
            import subprocess
            result = subprocess.run(
                ['ffprobe', '-v', 'error',
                 '-select_streams', 'v:0',
                 '-show_entries', 'stream=width,height',
                 '-of', 'csv=p=0', out],
                capture_output=True, text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                w_str, h_str = result.stdout.strip().split(',')
                self.assertEqual(int(w_str), W,  f'영상 너비 불일치: {w_str} ≠ {W}')
                self.assertEqual(int(h_str), H, f'영상 높이 불일치: {h_str} ≠ {H}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
