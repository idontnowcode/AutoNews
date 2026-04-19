"""
파이프라인 실행 로그 — Supabase pipeline_logs 테이블에 기록
오류 자동 분류 및 대응 방안 표준화
"""
import traceback
from src.db_client import get_client

# 오류 유형 분류 키워드 매핑 (순서 중요 — 앞 패턴이 우선)
_ERROR_PATTERNS = [
    ('upload_limit', ['uploadlimitexceeded']),
    ('youtube_auth', ['invalid_grant', 'token has been expired', 'token_expired',
                      'invalid_client', 'unauthorized_client', '401']),
    ('api_limit',    ['usage', 'ratelimit', 'rate_limit', 'too many requests',
                      'overloaded', '429', '529']),
    ('image_gen',    ['openai', 'dall-e', 'dall_e', 'image generation', 'dalle']),
    ('tts',          ['elevenlabs', 'voice', 'audio generation', 'eleven labs']),
    ('script',       ['anthropic', 'claude', 'completions', 'content_policy']),
    ('rss',          ['feedparser', 'urlopen', 'connection', 'timeout',
                      'remotedisconnected', 'ssl', 'gaierror']),
    ('video',        ['moviepy', 'ffmpeg', 'imageio', 'compose_video']),
]


def classify_error(err_str: str) -> str:
    lower = err_str.lower()
    for error_type, keywords in _ERROR_PATTERNS:
        if any(k in lower for k in keywords):
            return error_type
    return 'unknown'


def log_event(
    pipeline: str,
    level: str,
    message: str,
    error_type: str = '',
    news_id: str | None = None,
    topic_id: str | None = None,
    context: dict | None = None,
) -> None:
    """
    pipeline_logs 테이블에 이벤트 기록.
    실패해도 파이프라인에 영향 없음 (silent).
    """
    try:
        row: dict = {
            'pipeline':   pipeline,
            'level':      level,
            'message':    message[:2000],
            'error_type': error_type or '',
            'context':    context or {},
        }
        if news_id:
            row['news_id'] = news_id
        if topic_id:
            row['topic_id'] = topic_id
        get_client().table('pipeline_logs').insert(row).execute()
    except Exception:
        pass  # 로그 실패는 무시


def log_error(
    pipeline: str,
    exc: Exception,
    news_id: str | None = None,
    topic_id: str | None = None,
    context: dict | None = None,
) -> str:
    """
    예외를 자동 분류하고 로그 기록.
    반환값: 분류된 error_type 문자열
    """
    err_str    = str(exc)
    error_type = classify_error(err_str)
    tb_tail    = traceback.format_exc()[-800:]
    log_event(
        pipeline   = pipeline,
        level      = 'error',
        message    = err_str[:1000],
        error_type = error_type,
        news_id    = news_id,
        topic_id   = topic_id,
        context    = {**(context or {}), 'traceback': tb_tail},
    )
    return error_type


def log_warning(
    pipeline: str,
    message: str,
    error_type: str = '',
    news_id: str | None = None,
    topic_id: str | None = None,
) -> None:
    log_event(pipeline=pipeline, level='warning', message=message,
              error_type=error_type, news_id=news_id, topic_id=topic_id)


def log_success(
    pipeline: str,
    message: str,
    news_id: str | None = None,
    topic_id: str | None = None,
) -> None:
    log_event(pipeline=pipeline, level='success', message=message,
              news_id=news_id, topic_id=topic_id)
