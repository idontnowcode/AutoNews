"""
영상 통계 수집 + 분석 리포트 생성 메인 진입점
GitHub Actions stats_report.yml (6시간마다) 또는 수동 실행
"""
import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from src.youtube_stats import collect_all_stats
from src.stats_analyzer import run_analysis

load_dotenv()

_MIN_INTERVAL_HOURS = 6   # 자동 실행 최소 간격


def _check_should_run() -> bool:
    """
    수동 실행(FORCE_RUN=true): 항상 실행 + last_report_at 갱신
    자동 실행: last_report_at 이후 6시간 이상 지난 경우만 실행
    """
    force = os.environ.get('FORCE_RUN', '').lower() == 'true'
    if force:
        print('⚡ 수동 실행 — 즉시 리포트 생성')
        return True

    # 자동 실행: 마지막 리포트 생성 시각 체크
    try:
        from src.db_client import get_client
        db = get_client()
        res = db.table('settings').select('value').eq('key', 'stats_last_report_at').execute()
        if res.data:
            last_str = res.data[0]['value']
            last_dt  = datetime.fromisoformat(last_str.replace('Z', '+00:00'))
            elapsed  = datetime.now(timezone.utc) - last_dt
            remaining = timedelta(hours=_MIN_INTERVAL_HOURS) - elapsed
            if remaining.total_seconds() > 0:
                mins = int(remaining.total_seconds() / 60)
                print(f'⏸️  마지막 리포트 생성 후 {int(elapsed.total_seconds()/3600)}h {int((elapsed.total_seconds()%3600)/60)}m 경과 '
                      f'— 다음 실행까지 {mins}분 남음. 건너뜁니다.')
                return False
    except Exception as e:
        print(f'⚠️  마지막 실행 시각 조회 실패 ({e}) — 진행합니다')

    return True


def _save_last_run_time():
    """Supabase settings 테이블에 stats_last_report_at 저장"""
    try:
        from src.db_client import get_client
        db  = get_client()
        now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        db.table('settings').upsert(
            {'key': 'stats_last_report_at', 'value': now},
            on_conflict='key'
        ).execute()
        print(f'   🕐 마지막 리포트 시각 저장: {now}')
    except Exception as e:
        print(f'⚠️  마지막 실행 시각 저장 실패: {e}')


def main():
    print('=' * 60)
    print('📈 YouTube Shorts 통계 분석 리포트')
    print('=' * 60)

    if not _check_should_run():
        sys.exit(0)

    # 1. 통계 수집
    records = collect_all_stats()
    if not records:
        print('⚠️  분석할 영상 데이터가 없습니다.')
        sys.exit(0)

    # 2. 분석 리포트 생성 + DB 저장
    run_analysis(records)

    # 3. 마지막 실행 시각 기록 (자동 스케줄 간격 초기화)
    _save_last_run_time()
    print('✅ 완료')


if __name__ == '__main__':
    main()
