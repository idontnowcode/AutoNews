"""
영상 통계 수집 + 분석 리포트 생성 메인 진입점
GitHub Actions stats_report.yml (6시간마다) 또는 수동 실행
"""
import sys
from dotenv import load_dotenv
from src.youtube_stats import collect_all_stats
from src.stats_analyzer import run_analysis

load_dotenv()


def main():
    print('=' * 60)
    print('📈 YouTube Shorts 통계 분석 리포트')
    print('=' * 60)

    # 1. 통계 수집
    records = collect_all_stats()
    if not records:
        print('⚠️  분석할 영상 데이터가 없습니다.')
        sys.exit(0)

    # 2. 분석 리포트 생성 + DB 저장
    run_analysis(records)
    print('✅ 완료')


if __name__ == '__main__':
    main()
