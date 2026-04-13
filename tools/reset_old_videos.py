"""
구 채널에 업로드된 첫 N개 영상을 새 채널로 재생성하기 위한 초기화 스크립트
  - videos 테이블에서 가장 오래된 N개 조회
  - 해당 topic status → pending (재생성 대기)
  - videos 레코드 삭제 (새로 생성될 예정)
사용법:
  python tools/reset_old_videos.py        # 기본 2개
  python tools/reset_old_videos.py 3      # 3개
"""

import os, sys
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    sys.exit('❌ .env 파일에 SUPABASE_URL, SUPABASE_KEY를 설정하세요.')

try:
    from supabase import create_client
except ImportError:
    sys.exit('❌ supabase 미설치: pip install supabase')

db = create_client(SUPABASE_URL, SUPABASE_KEY)

count = int(sys.argv[1]) if len(sys.argv) > 1 else 2

# ── 가장 오래된 N개 영상 조회 ─────────────────────────
res = db.table('videos').select('id,title,youtube_id,topic_id,created_at') \
        .order('created_at', desc=False).limit(count).execute()

videos = res.data
if not videos:
    print('영상 데이터가 없습니다.')
    sys.exit(0)

print(f'\n📋 초기화할 영상 {len(videos)}개:')
print('-' * 60)
for v in videos:
    print(f"  제목: {v['title']}")
    print(f"  YouTube: https://youtube.com/shorts/{v['youtube_id']}")
    print(f"  생성일: {v['created_at'][:10]}")
    print()

ans = input('위 영상들을 초기화하고 새 채널로 재생성하시겠습니까? (y/N): ').strip().lower()
if ans != 'y':
    print('취소됐습니다.')
    sys.exit(0)

# ── topic → pending ───────────────────────────────────
topic_ids  = [v['topic_id'] for v in videos]
video_ids  = [v['id']       for v in videos]

for tid in topic_ids:
    db.table('topics').update({'status': 'pending'}).eq('id', tid).execute()

# ── videos 레코드 삭제 ────────────────────────────────
for vid in video_ids:
    db.table('videos').delete().eq('id', vid).execute()

print('✅ 완료!')
print(f'   - topic {len(topic_ids)}개 → pending 으로 초기화')
print(f'   - videos {len(video_ids)}개 삭제')
print()
print('👉 다음 단계: 대시보드에서 즉시 생성 버튼을 눌러 재생성하세요.')
