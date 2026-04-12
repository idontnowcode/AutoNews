import os
import subprocess
import glob

# moviepy v1 / v2 호환 임포트
try:
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
    MOVIEPY_V2 = False
except ModuleNotFoundError:
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
    MOVIEPY_V2 = True

VIDEO_SIZE = (1080, 1920)  # Shorts 세로형
FPS = 30


def ppt_to_images(ppt_path: str, out_dir: str) -> list:
    """LibreOffice: PPT → PNG 이미지 변환"""
    os.makedirs(out_dir, exist_ok=True)
    env = {**os.environ, 'HOME': '/root', 'DISPLAY': ''}
    subprocess.run([
        'libreoffice', '--headless',
        '--convert-to', 'png',
        '--outdir', out_dir,
        ppt_path
    ], check=True, capture_output=True, env=env)
    images = sorted(glob.glob(os.path.join(out_dir, '*.png')))
    return images


def compose_video(ppt_path: str, audio_path: str, output_path: str) -> str:
    """슬라이드 + 오디오 → MP4 영상"""
    img_dir = output_path.replace('.mp4', '_slides')
    images  = ppt_to_images(ppt_path, img_dir)
    if not images:
        raise ValueError('슬라이드 이미지 변환 실패')

    audio     = AudioFileClip(audio_path)
    duration  = audio.duration
    per_slide = duration / len(images)

    clips = []
    for img_path in images:
        if MOVIEPY_V2:
            clip = ImageClip(img_path, duration=per_slide).resized(VIDEO_SIZE)
        else:
            clip = (ImageClip(img_path)
                    .set_duration(per_slide)
                    .resize(VIDEO_SIZE))
        clips.append(clip)

    if MOVIEPY_V2:
        final = concatenate_videoclips(clips, method='compose').with_audio(audio)
    else:
        final = concatenate_videoclips(clips, method='compose').set_audio(audio)

    final.write_videofile(
        output_path,
        fps=FPS,
        codec='libx264',
        audio_codec='aac',
        temp_audiofile='/tmp/temp_audio.m4a',
        remove_temp=True
    )
    return output_path
