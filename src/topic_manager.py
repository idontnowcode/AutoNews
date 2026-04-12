"""
주제 관리 — Supabase에서 다음 주제 선택 + Claude로 연관 주제 자동 확장
"""
import os
import json
import anthropic
from src.db_client import get_client

_anthropic = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])


def get_next_topic() -> dict:
    """
    다음 제작할 주제 선택:
    1. status=pending이고 prerequisites가 모두 done인 주제 중 order_index 최소값
    2. 없으면 prerequisites 무시하고 pending 중 첫 번째
    """
    db = get_client()

    # done 주제 ID 목록
    done = db.table('topics').select('id').eq('status', 'done').execute()
    done_ids = {r['id'] for r in done.data}

    # pending 전체
    pending = (db.table('topics')
               .select('*')
               .eq('status', 'pending')
               .order('order_index', desc=False)
               .execute())

    if not pending.data:
        # 모두 완료 → 주제 확장 후 재시도
        expand_topics()
        pending = (db.table('topics')
                   .select('*')
                   .eq('status', 'pending')
                   .order('order_index', desc=False)
                   .execute())

    # prerequisites 충족 주제 우선
    for topic in pending.data:
        prereqs = topic.get('prerequisites') or []
        if all(p in done_ids for p in prereqs):
            return topic

    # 없으면 첫 번째 pending
    return pending.data[0]


def mark_in_progress(topic_id: str):
    db = get_client()
    db.table('topics').update({'status': 'in_progress'}).eq('id', topic_id).execute()


def mark_done(topic_id: str):
    db = get_client()
    db.table('topics').update({'status': 'done'}).eq('id', topic_id).execute()


def save_video(topic_id: str, youtube_id: str, script: dict, slide_prompts: list):
    db = get_client()
    db.table('videos').insert({
        'topic_id':     topic_id,
        'youtube_id':   youtube_id,
        'title':        script.get('title', ''),
        'subtitle':     script.get('subtitle', ''),
        'narration':    script.get('narration', ''),
        'script_json':  script,
        'slide_prompts': slide_prompts,
        'published_at': 'NOW()',
    }).execute()


def expand_topics():
    """
    Claude로 새 주제 10개 생성 후 DB에 추가.
    기존 주제 목록을 참고해 유기적으로 연결된 주제를 생성.
    """
    db = get_client()
    existing = db.table('topics').select('title, level, category').execute()
    existing_titles = [r['title'] for r in existing.data]

    prompt = f"""
현재 경제 교육 YouTube Shorts 채널의 주제 목록:
{json.dumps(existing_titles, ensure_ascii=False)}

위 주제들과 유기적으로 연결되는 새 경제 교육 주제 10개를 추가로 생성해주세요.
- 기존 주제의 심화 내용이거나 연관 개념이어야 함
- basic / intermediate / advanced 균형 있게
- 카테고리: 거시경제, 투자, 금융시장, 재정, 국제경제, 행동경제학 중 선택

반드시 아래 JSON 배열만 반환:
[
  {{
    "title": "한국어 주제명",
    "title_en": "English title",
    "level": "basic|intermediate|advanced",
    "category": "카테고리",
    "description": "한 줄 설명"
  }}
]
"""
    msg = _anthropic.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=1024,
        messages=[{'role': 'user', 'content': prompt}]
    )
    raw = msg.content[0].text.strip()
    import re
    match = re.search(r'\[.*\]', raw, re.DOTALL)
    if not match:
        return

    new_topics = json.loads(match.group())

    # 현재 최대 order_index
    max_order = db.table('topics').select('order_index').order('order_index', desc=True).limit(1).execute()
    start_idx = (max_order.data[0]['order_index'] or 0) + 1 if max_order.data else 100

    for i, t in enumerate(new_topics):
        t['order_index'] = start_idx + i
        t['status'] = 'pending'

    db.table('topics').insert(new_topics).execute()
    print(f'   주제 {len(new_topics)}개 추가됨')
