-- 뉴스 아이템 테이블
-- Supabase SQL Editor에서 1회 실행

CREATE TABLE IF NOT EXISTS news_items (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title        text NOT NULL,
  url          text UNIQUE,
  source       text,
  summary      text,
  status       text DEFAULT 'pending',   -- pending / in_progress / done / skipped
  youtube_id   text,
  created_at   timestamptz DEFAULT now(),
  published_at timestamptz
);

ALTER TABLE news_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon read news"  ON news_items FOR SELECT USING (true);
CREATE POLICY "anon write news" ON news_items FOR ALL    USING (true) WITH CHECK (true);
