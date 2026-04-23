"""
업로드 설정 관리
Supabase settings 테이블에서 설정 읽기 + 예약 발행 실행 여부 판단

실행 조건 (모두 통과해야 실행):
  1. FORCE_RUN=true  → 즉시 실행 (수동 dispatch)
  2. upload_schedule_enabled == 'true'
  3. 오늘 요일이 upload_schedule_days에 포함
  4. 현재 UTC 시각이 upload_schedule_slots의 해당 카테고리 슬롯과 일치
  5. 같은 슬롯에서 이미 실행된 적 없음 (슬롯 중복 실행 방지)
"""
import json
import os
from datetime import datetime, timezone, timedelta
from src.db_client import get_client

# ── 슬롯 실행 기록 (process-level) ───────────────────────────────────
# _is_in_schedule_window()에서 설정 → record_slot_run()에서 DB에 기록
_slot_key: str | None = None       # 예) '2025-04-19_14' (KST date + matched hour)
_slot_lock_key: str | None = None  # 예) 'last_news_slot_run'

_DAY_MAP = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
_DAY_KO  = ['월', '화', '수', '목', '금', '토', '일']


def get_settings() -> dict:
    db = get_client()
    res = db.table('settings').select('key,value').execute()
    return {r['key']: r['value'] for r in (res.data or [])}


def save_setting(key: str, value: str):
    """settings 테이블에 key=value upsert 저장"""
    db = get_client()
    db.table('settings').upsert({'key': key, 'value': value},
                                 on_conflict='key').execute()


def record_slot_run():
    """
    현재 파이프라인이 매칭한 슬롯을 '이미 실행됨'으로 DB에 기록.
    다음 cron 실행이 같은 슬롯 내에 도달해도 중복 실행을 차단한다.
    업로드 성공 직후에 호출해야 한다.
    """
    global _slot_key, _slot_lock_key
    if _slot_key and _slot_lock_key:
        save_setting(_slot_lock_key, _slot_key)
        print(f'   🔒 슬롯 실행 기록 저장: {_slot_lock_key} = {_slot_key}')


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

    # 시간 체크: 슬롯 90분 이전~정시 구간에서만 해당 슬롯 예약으로 실행
    # 예) 2시 슬롯 → 0:30~2:00 KST 진입 시 "2시 예약"으로 실행
    #     2:01~3:29 KST는 가까운 슬롯 없음 → 스킵
    #     3:30~5:00 KST → "5시 예약"으로 실행
    WINDOW_MIN = 90
    now_kst_min = (now.hour * 60 + now.minute + 9 * 60) % (24 * 60)

    matched_hour = None
    for h in sorted(hours_kst):
        # 현재 시각에서 해당 슬롯까지 남은 분 (0 = 정시, 양수 = 슬롯 이전)
        minutes_to_slot = (h * 60 - now_kst_min) % (24 * 60)
        if minutes_to_slot <= WINDOW_MIN:
            matched_hour = h
            break

    if matched_hour is None:
        slots_kst_str = ', '.join(f'{h}시' for h in sorted(hours_kst))
        print(f'   ⏰ 현재 {kst_hour}시(KST)는 업로드 시간 아님'
              f' (설정: {slots_kst_str}) — 건너뜁니다')
        return False

    # ── 슬롯 중복 실행 방지 ───────────────────────────────────────────
    # 같은 KST 날짜+슬롯 시간에 이미 실행됐으면 건너뜀
    # 이전 실행이 record_slot_run()으로 DB에 기록해 두었을 때만 차단
    now_kst = datetime.now(timezone(timedelta(hours=9)))
    today_kst = now_kst.strftime('%Y-%m-%d')
    slot_key = f'{today_kst}_{matched_hour:02d}'
    lock_key = f'last_{category}_slot_run'
    if settings.get(lock_key, '') == slot_key:
        print(f'   🔒 슬롯 중복 방지 — {matched_hour}시 슬롯은 이미 실행됨 ({today_kst})')
        return False

    # process-level 변수에 저장 → 업로드 성공 후 record_slot_run()이 DB에 기록
    global _slot_key, _slot_lock_key
    _slot_key = slot_key
    _slot_lock_key = lock_key

    minutes_to = (matched_hour * 60 - now_kst_min) % (24 * 60)
    if minutes_to == 0:
        print(f'   ✅ 스케줄 조건 통과 ({day_name}요일 {matched_hour}시 KST 정시)')
    else:
        print(f'   ✅ 스케줄 조건 통과 ({day_name}요일 {matched_hour}시 KST 예약, {minutes_to}분 전 실행)')
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


def get_scheduled_language(category: str = 'news') -> str:
    """
    예약 실행 시 사용할 언어 결정:
      현재 시각에 매칭되는 슬롯의 lang 필드 반환.
      슬롯에 lang 없으면 전역 content_language 설정 사용.
    """
    try:
        settings = get_settings()
    except Exception:
        return 'ko'

    slots_raw = settings.get('upload_schedule_slots', '[]')
    try:
        slots = json.loads(slots_raw) if slots_raw else []
    except Exception:
        slots = []

    WINDOW_MIN = 90
    now = datetime.now(timezone.utc)
    now_kst_min = (now.hour * 60 + now.minute + 9 * 60) % (24 * 60)

    cat_slots = [s for s in slots if s.get('category') == category]
    for s in sorted(cat_slots, key=lambda x: x.get('hour', 0)):
        h = s.get('hour')
        if h is None:
            continue
        minutes_to_slot = (h * 60 - now_kst_min) % (24 * 60)
        if minutes_to_slot <= WINDOW_MIN:
            slot_lang = s.get('lang', '').lower().strip()
            if slot_lang in ('ko', 'en'):
                print(f'   🌐 슬롯 언어 사용: {slot_lang.upper()} (슬롯 {h}시)')
                return slot_lang
            break  # 매칭됐지만 lang 없음 → 전역 설정 사용

    # 매칭 슬롯 lang 없음 → 전역 content_language
    lang = settings.get('content_language', 'ko').lower().strip()
    return lang if lang in ('ko', 'en') else 'ko'
