"""
업로드 설정 관리
Supabase settings 테이블에서 설정 읽기 + 예약 발행 실행 여부 판단
"""
import os
from src.db_client import get_client


def get_settings() -> dict:
    db = get_client()
    res = db.table('settings').select('key,value').execute()
    return {r['key']: r['value'] for r in (res.data or [])}


def _check_schedule_enabled(pipeline: str = '') -> bool:
    """
    공통 실행 여부 판단:
      - FORCE_RUN=true → 무조건 실행
      - upload_schedule_enabled != true → 건너뜀
    """
    if os.environ.get('FORCE_RUN', '').lower() == 'true':
        print('⚡ 즉시 실행 모드 — 설정 체크 건너뜁니다.')
        return True

    try:
        settings = get_settings()
    except Exception as e:
        print(f'⚠️  설정 조회 실패 ({e}) — 기본값으로 진행')
        return True

    if settings.get('upload_schedule_enabled', 'false').lower() != 'true':
        label = f'{pipeline} ' if pipeline else ''
        print(f'⏸️  {label}예약 발행 비활성화 — 건너뜁니다.')
        return False

    return True


def check_should_run() -> bool:
    """커리큘럼 파이프라인 실행 여부"""
    return _check_schedule_enabled('커리큘럼')


def check_news_should_run() -> bool:
    """뉴스 파이프라인 실행 여부"""
    return _check_schedule_enabled('뉴스')
