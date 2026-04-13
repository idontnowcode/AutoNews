"""
자동 업로드 설정 관리
Supabase settings 테이블에서 설정 읽기 + 업로드 실행 여부 판단
"""
import os
from datetime import datetime, timezone, timedelta
from src.db_client import get_client


def get_settings() -> dict:
    db = get_client()
    res = db.table('settings').select('key,value').execute()
    return {r['key']: r['value'] for r in (res.data or [])}


def check_should_run() -> bool:
    """
    업로드 실행 여부 판단:
      - FORCE_RUN=true (workflow_dispatch) → 무조건 실행
      - auto_enabled = false → 건너뜀
      - 마지막 업로드 이후 interval 미경과 → 건너뜀
    """
    # 즉시 실행 (workflow_dispatch) 시 모든 체크 무시
    if os.environ.get('FORCE_RUN', '').lower() == 'true':
        print('⚡ 즉시 실행 모드 — 간격/설정 체크 건너뜁니다.')
        return True

    try:
        settings = get_settings()
    except Exception as e:
        print(f'⚠️  설정 조회 실패 ({e}) — 기본값으로 진행')
        return True

    # ── 자동 업로드 ON/OFF ────────────────────────────
    if settings.get('auto_enabled', 'true').lower() != 'true':
        print('⏸️  자동 업로드 비활성화 — 건너뜁니다.')
        return False

    # ── 간격 체크 ─────────────────────────────────────
    try:
        val  = int(settings.get('interval_value', '1'))
        unit = settings.get('interval_unit', 'days')
        delta = timedelta(hours=val) if unit == 'hours' else timedelta(days=val)
    except ValueError:
        delta = timedelta(days=1)

    db = get_client()
    res = db.table('videos').select('created_at') \
            .order('created_at', desc=True).limit(1).execute()

    if res.data:
        last_ts  = res.data[0]['created_at'].replace('Z', '+00:00')
        last_dt  = datetime.fromisoformat(last_ts)
        now      = datetime.now(timezone.utc)
        elapsed  = now - last_dt

        if elapsed < delta:
            remaining = delta - elapsed
            h = int(remaining.total_seconds() // 3600)
            m = int((remaining.total_seconds() % 3600) // 60)
            print(f'⏱️  간격 대기 중: 마지막 업로드 후 {int(elapsed.total_seconds()//3600)}h {int((elapsed.total_seconds()%3600)//60)}m 경과 '
                  f'/ 다음 업로드까지 {h}h {m}m 남음')
            return False

    return True
