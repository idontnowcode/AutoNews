import os

# moviepy v1 / v2 호환 임포트
try:
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
    MOVIEPY_V2 = False
except ModuleNotFoundError:
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
    MOVIEPY_V2 = True

VIDEO_SIZE = (1080, 1920)  # Shorts 세로형
FPS = 30


def compose_video(image_paths: list, audio_path: str, output_path: str) -> str:
    """슬라이드 PNG 리스트 + 오디오 → MP4 영상"""
    if not image_paths:
        raise ValueError('슬라이드 이미지가 없음')

    audio     = AudioFileClip(audio_path)
    duration  = audio.duration
    per_slide = duration / len(image_paths)

    clips = []
    for img_path in image_paths:
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
