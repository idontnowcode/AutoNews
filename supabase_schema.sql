-- ============================================================
-- YouTube Shorts 경제 교육 채널 — Supabase 스키마
-- Supabase SQL Editor에서 실행하세요
-- ============================================================

-- 주제 테이블
CREATE TABLE IF NOT EXISTS topics (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title         TEXT NOT NULL,                          -- 한국어 제목
  title_en      TEXT,                                   -- 영어 제목 (DALL-E 프롬프트용)
  level         TEXT NOT NULL CHECK (level IN ('basic', 'intermediate', 'advanced')),
  category      TEXT NOT NULL,                          -- 예: 거시경제, 투자, 금융시장
  description   TEXT,                                   -- 주제 설명
  prerequisites UUID[] DEFAULT '{}',                   -- 선행 주제 ID 배열
  related_topics UUID[] DEFAULT '{}',                  -- 연관 주제 ID 배열
  status        TEXT DEFAULT 'pending'
                CHECK (status IN ('pending', 'in_progress', 'done')),
  order_index   INTEGER,                               -- 커리큘럼 순서
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 영상 테이블
CREATE TABLE IF NOT EXISTS videos (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  topic_id      UUID REFERENCES topics(id) ON DELETE SET NULL,
  youtube_id    TEXT,                                  -- 업로드 후 채워짐
  title         TEXT,
  subtitle      TEXT,
  narration     TEXT,
  script_json   JSONB,                                 -- 전체 스크립트 JSON
  slide_prompts JSONB,                                 -- DALL-E 프롬프트 배열
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  published_at  TIMESTAMPTZ
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_topics_status    ON topics(status);
CREATE INDEX IF NOT EXISTS idx_topics_level     ON topics(level);
CREATE INDEX IF NOT EXISTS idx_topics_category  ON topics(category);
CREATE INDEX IF NOT EXISTS idx_videos_topic_id  ON videos(topic_id);

-- ============================================================
-- 초기 시드 데이터 — 기초 경제 주제 20개
-- Claude가 매 실행 시 자동으로 확장합니다
-- ============================================================
INSERT INTO topics (title, title_en, level, category, description, order_index) VALUES
-- 거시경제 기초
('금리란 무엇인가',        'What is Interest Rate',        'basic',        '거시경제', '돈을 빌리는 비용, 금리의 기본 개념',  1),
('인플레이션이란',         'What is Inflation',            'basic',        '거시경제', '물가 상승의 의미와 원인',             2),
('GDP란 무엇인가',         'What is GDP',                  'basic',        '거시경제', '국내총생산의 의미와 측정 방법',       3),
('중앙은행의 역할',        'Role of Central Bank',         'basic',        '거시경제', '한국은행과 Fed의 역할',              4),
('경기 사이클이란',        'What is Business Cycle',       'basic',        '거시경제', '경기 확장과 수축의 반복',             5),

-- 투자 기초
('주식이란 무엇인가',      'What is a Stock',              'basic',        '투자',     '주식의 기본 개념과 주주의 권리',      6),
('채권이란 무엇인가',      'What is a Bond',               'basic',        '투자',     '채권의 구조와 이자 지급 방식',        7),
('펀드와 ETF의 차이',      'Fund vs ETF',                  'basic',        '투자',     '집합투자의 두 가지 방식 비교',        8),
('복리의 마법',            'Power of Compound Interest',   'basic',        '투자',     '시간이 만드는 복리 효과',             9),
('분산 투자란',            'What is Diversification',      'basic',        '투자',     '리스크를 줄이는 포트폴리오 구성',    10),

-- 금융시장 기초
('환율이란 무엇인가',      'What is Exchange Rate',        'basic',        '금융시장', '두 나라 통화의 교환 비율',           11),
('주식시장은 어떻게 작동하나', 'How Stock Market Works',   'basic',        '금융시장', '코스피·나스닥 시장의 작동 원리',     12),
('공급과 수요의 원리',     'Supply and Demand',            'basic',        '거시경제', '가격을 결정하는 기본 원리',          13),
('세금의 종류와 역할',     'Types of Taxes',               'basic',        '재정',     '소득세·부가세 등 세금의 기초',       14),
('가계부채란 무엇인가',    'What is Household Debt',       'basic',        '거시경제', '가계 대출의 구조와 위험성',          15),

-- 중급 주제
('통화정책이란',           'Monetary Policy',              'intermediate', '거시경제', '중앙은행이 금리로 경제를 조절하는 방법', 16),
('재정정책이란',           'Fiscal Policy',                'intermediate', '거시경제', '정부 지출과 세금으로 경제를 조절',      17),
('양적완화란',             'Quantitative Easing',          'intermediate', '거시경제', '돈을 푸는 비전통적 통화정책',           18),
('PER과 PBR 읽는 법',      'How to Read PER and PBR',      'intermediate', '투자',     '주식 가치 평가 지표 해석',              19),
('금리와 채권 가격의 관계', 'Interest Rate and Bond Price', 'intermediate', '투자',     '금리 상승 시 채권 가격이 떨어지는 이유', 20)
ON CONFLICT DO NOTHING;

-- prerequisites 연결 (중급 → 기초 선행)
UPDATE topics SET prerequisites = ARRAY(
  SELECT id FROM topics WHERE title = '금리란 무엇인가'
) WHERE title = '통화정책이란';

UPDATE topics SET prerequisites = ARRAY(
  SELECT id FROM topics WHERE title IN ('금리란 무엇인가', '채권이란 무엇인가')
) WHERE title = '금리와 채권 가격의 관계';

UPDATE topics SET prerequisites = ARRAY(
  SELECT id FROM topics WHERE title = '통화정책이란'
) WHERE title = '양적완화란';

UPDATE topics SET prerequisites = ARRAY(
  SELECT id FROM topics WHERE title = '주식이란 무엇인가'
) WHERE title = 'PER과 PBR 읽는 법';

-- ============================================================
-- 뉴스 아이템 테이블
-- ============================================================
CREATE TABLE IF NOT EXISTS news_items (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title          TEXT NOT NULL,
  url            TEXT UNIQUE NOT NULL,                    -- 중복 방지용 유니크 키
  source         TEXT,                                    -- RSS 피드 출처명
  summary        TEXT,                                    -- 기사 요약 (500자 이내)
  status         TEXT DEFAULT 'pending'
                 CHECK (status IN ('pending', 'queued', 'in_progress', 'done', 'failed')),
  published_at   TIMESTAMPTZ,                             -- 기사 발행 시각
  category       TEXT DEFAULT '경제',                    -- 분야 (경제/스포츠/IT 등)
  interest_score INTEGER DEFAULT 0,                       -- 관심도 점수
  interest_level TEXT DEFAULT 'medium'
                 CHECK (interest_level IN ('low', 'medium', 'high')),
  youtube_id     TEXT,                                    -- 업로드 완료 시 채워짐 (NULL = 미업로드)
  created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_news_status    ON news_items(status);
CREATE INDEX IF NOT EXISTS idx_news_category  ON news_items(category);
CREATE INDEX IF NOT EXISTS idx_news_published ON news_items(published_at DESC);

-- ============================================================
-- 뉴스 관심도 컬럼 추가 (기존 DB에 실행 — 이미 테이블 있을 경우)
-- ============================================================
ALTER TABLE news_items
  ADD COLUMN IF NOT EXISTS interest_score  INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS interest_level  TEXT    DEFAULT 'medium'
    CHECK (interest_level IN ('low', 'medium', 'high'));

-- ============================================================
-- 뉴스 YouTube 업로드 완료 기록 컬럼 (비용 통계 카운팅용)
-- ============================================================
ALTER TABLE news_items
  ADD COLUMN IF NOT EXISTS youtube_id TEXT;    -- 업로드 완료 시 채워짐 (NULL = 미업로드)

CREATE INDEX IF NOT EXISTS idx_news_youtube_id ON news_items(youtube_id)
  WHERE youtube_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_news_interest ON news_items(interest_score DESC, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_level    ON news_items(interest_level);

-- ============================================================
-- 뉴스 실행 대기 큐 (queued status)
-- news_items.status 허용값:
--   pending    — RSS 수집 후 자동 대기
--   queued     — 사용자가 수동으로 실행 대기열에 추가 (자동화 최우선 처리)
--   in_progress — 파이프라인 처리 중
--   done       — YouTube 업로드 완료
--   failed     — 처리 실패
-- status 컬럼은 TEXT 타입이므로 별도 ALTER 불필요
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_news_queued ON news_items(status, created_at)
  WHERE status = 'queued';

-- ============================================================
-- 영상 통계 분석 (stats-report)
-- ============================================================

-- 영상별 최신 통계 스냅샷 (youtube_id 기준 upsert)
CREATE TABLE IF NOT EXISTS video_stats (
  youtube_id    TEXT PRIMARY KEY,
  title         TEXT,
  video_type    TEXT CHECK (video_type IN ('curriculum', 'news', 'unknown')),
  category      TEXT,
  view_count    INTEGER DEFAULT 0,
  like_count    INTEGER DEFAULT 0,
  comment_count INTEGER DEFAULT 0,
  duration_sec  INTEGER DEFAULT 0,
  published_at  TIMESTAMPTZ,
  fetched_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 분석 리포트 히스토리
CREATE TABLE IF NOT EXISTS analysis_reports (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  report_md   TEXT,
  stats_json  JSONB
);

-- 기존 DB에 이미 video_stats 테이블이 있는 경우 제약 조건 수정
ALTER TABLE video_stats DROP CONSTRAINT IF EXISTS video_stats_video_type_check;
ALTER TABLE video_stats ADD CONSTRAINT video_stats_video_type_check
  CHECK (video_type IN ('curriculum', 'news', 'unknown'));

CREATE INDEX IF NOT EXISTS idx_video_stats_type     ON video_stats(video_type);
CREATE INDEX IF NOT EXISTS idx_video_stats_category ON video_stats(category);
CREATE INDEX IF NOT EXISTS idx_reports_created      ON analysis_reports(created_at DESC);
