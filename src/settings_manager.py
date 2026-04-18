"""
업로드 설정 관리
Supabase settings 테이블에서 설정 읽기 + 예약 발행 실행 여부 판단

실행 조건 (모두 통과해야 실행):
  1. FORCE_RUN=true  → 즉시 실행 (수동 dispatch)
  2. upload_schedule_enabled == 'true'
  3. 오늘 요일이 upload_schedule_days에 포함
  4. 현재 UTC 시각이 upload_schedule_slots의 해당 카테고리 슬롯과 일치
"""
import json
import os
from datetime import datetime, timezone
from src.db_client import get_client

_DAY_MAP = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
_DAY_KO  = ['월', '화', '수', '목', '금', '토', '일']


def get_settings() -> dict:
    db = get_client()
    res = db.table('settings').select('key,value').execute()
    return {r['key']: r['value'] for r in (res.data or [])}


def _is_in_schedule_window(settings: dict, category: str) -> bool:
    """현재 UTC 시각이 설정된 요일·슬롯과 일치하는지 확인"""
    days_str  = settings.get('upload_schedule_days',  'everyday').strip().lower()
    slots_raw = settings.get('upload_schedule_slots', '[]')

    # ── 요일 파싱 ────────────────────────────────────────────
    if days_str == 'everyday':
        target_days = set(range(7))
    else:
        target_days = {_DAY_MAP[d.strip()] for d in days_str.split(',')
                       if d.strip() in _DAY_MAP}
    if not target_days:
        target_days = set(range(7))

    # ── 슬롯 파싱 (해당 카테고리의 KST 시간만 추출) ──────────
    try:
        slots = json.loads(slots_raw) if slots_raw else []
    except Exception:
        slots = []

    hours_kst = [s['hour'] for s in slots if s.get('category') == category]

    now = datetime.now(timezone.utc)
    day_name = _DAY_KO[now.weekday()]
    kst_hour = (now.hour + 9) % 24

    # 요일 체크
    if now.weekday() not in target_days:
        print(f'   📅 오늘({day_name}요일)은 업로드 요일이 아님 — 건너뜁니다')
        return False

    # 슬롯 미설정 → 요일만 통과하면 실행
    if not hours_kst:
        print(f'   ✅ 요일 조건 통과 (슬롯 미설정, 시간 무제한)')
        return True

    # 시간 체크: GitHub Actions cron 지연 대비 90분 윈도우 허용
    # 예: 2시 슬롯 → 2:00~3:29 KST 사이에 실행된 cron 모두 허용
    WINDOW_MIN = 90
    now_kst_min = (now.hour * 60 + now.minute + 9 * 60) % (24 * 60)  # 현재 KST 분 환산

    matched_hour = None
    for h in hours_kst:
        slot_min = h * 60
        diff = (now_kst_min - slot_min) % (24 * 60)  # 슬롯 이후 경과 분
        if diff <= WINDOW_MIN:
            matched_hour = h
            break

    if matched_hour is None:
        slots_kst_str = ', '.join(f'{h}시' for h in sorted(hours_kst))
        print(f'   ⏰ 현재 {kst_hour}시(KST)는 업로드 시간 아님'
              f' (설정: {slots_kst_str}) — 건너뜁니다')
        return False

    delay = (now_kst_min - matched_hour * 60) % (24 * 60)
    if delay == 0:
        print(f'   ✅ 스케줄 조건 통과 ({day_name}요일 {matched_hour}시 KST)')
    else:
        print(f'   ✅ 스케줄 조건 통과 ({day_name}요일 {matched_hour}시 KST, {delay}분 지연 허용)')
    return True


def _check_schedule_enabled(pipeline: str = '', category: str = '') -> bool:
    """
    공통 실행 여부 판단:
      - FORCE_RUN=true            → 즉시 실행
      - upload_schedule_enabled   → on/off 체크
      - 요일·시간 슬롯             → 현재 시각 체크
    """
    if os.environ.get('FORCE_RUN', '').lower() == 'true':
        print('⚡ 즉시 실행 모드 — 설정 체크 건너뜁니다.')
        return True

    try:
        settings = get_settings()
    except Exception as e:
        print(f'⚠️  설정 조회 실패 ({e}) — 기본값으로 진행')
        return True

    label = f'{pipeline} ' if pipeline else ''

    if settings.get('upload_schedule_enabled', 'false').lower() != 'true':
        print(f'⏸️  {label}예약 발행 비활성화 — 건너뜁니다.')
        return False

    # 요일·시간 슬롯 체크 (category 있을 때만)
    if category and not _is_in_schedule_window(settings, category):
        return False

    return True


def check_should_run() -> bool:
    """커리큘럼 파이프라인 실행 여부"""
    return _check_schedule_enabled('커리큘럼', 'curriculum')


def check_news_should_run() -> bool:
    """뉴스 파이프라인 실행 여부"""
    return _check_schedule_enabled('뉴스', 'news')


def get_content_language() -> str:
    """콘텐츠 생성 언어 설정 ('ko' 또는 'en', 기본값 'ko')"""
    try:
        settings = get_settings()
        lang = settings.get('content_language', 'ko').lower().strip()
        return lang if lang in ('ko', 'en') else 'ko'
    except Exception:
        return 'ko'
