-- 자동 업로드 설정 테이블
-- Supabase SQL Editor에서 1회 실행

CREATE TABLE IF NOT EXISTS settings (
  key        text PRIMARY KEY,
  value      text NOT NULL,
  updated_at timestamptz DEFAULT now()
);

INSERT INTO settings (key, value) VALUES
  ('auto_enabled',   'true'),
  ('interval_value', '1'),
  ('interval_unit',  'days')
ON CONFLICT (key) DO NOTHING;

-- RLS: anon key로 읽기/쓰기 허용
ALTER TABLE settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon read settings"  ON settings FOR SELECT USING (true);
CREATE POLICY "anon write settings" ON settings FOR ALL    USING (true) WITH CHECK (true);
