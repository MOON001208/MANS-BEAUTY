-- ============================================================================
-- 03. Semantic Layer: 비즈니스 용어 사전 및 표준 지표 매핑
-- ============================================================================
-- 목적:
--   비정형 리뷰 텍스트에서 등장하는 파편화된 표현들을 분석 가능한 표준 지표로
--   통합함으로써, 사람과 AI(LLM)가 동일한 의미 기준으로 데이터를 해석할 수 있도록 한다.
--
-- 배경:
--   "촉촉한", "수분감 좋은", "건조하지 않은" → 모두 '보습력'이라는 하나의 지표로 매핑
--   "안 지워짐", "하루종일 유지", "저녁까지 OK" → '지속력'
--   "가벼운", "무겁지 않은", "바른 듯 안 바른 듯" → '가벼움'
--
-- 활용:
--   1. 리뷰 텍스트 NLP 분석 시 표준 지표 분류 기준으로 사용
--   2. LLM Data Agent가 쿼리 생성 시 참조하는 메타데이터
--   3. 데이터 카탈로그에서 컬럼 설명 및 비즈니스 정의 제공
-- ============================================================================


-- 1) 표준 지표(Metric) 정의 테이블
CREATE TABLE IF NOT EXISTS public.business_metrics (
    metric_id       TEXT PRIMARY KEY,          -- 표준 지표 식별자 (예: 'coverage')
    metric_name_ko  TEXT NOT NULL,             -- 한국어 지표명 (예: '커버력')
    metric_name_en  TEXT NOT NULL,             -- 영문 지표명 (예: 'Coverage')
    description     TEXT,                      -- 지표 설명
    score_column    TEXT,                      -- products 테이블에서 대응하는 컬럼명
    scale_min       NUMERIC DEFAULT 1.0,       -- 점수 최소값
    scale_max       NUMERIC DEFAULT 5.0,       -- 점수 최대값
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 표준 지표 데이터 삽입
INSERT INTO public.business_metrics (metric_id, metric_name_ko, metric_name_en, description, score_column)
VALUES
    ('coverage',    '커버력',   'Coverage',
     '잡티, 트러블, 모공 등 피부 결점을 가려주는 정도. 점수가 높을수록 고커버.',
     'coverage_score'),
    ('longevity',   '지속력',   'Longevity',
     '메이크업이 무너지지 않고 유지되는 시간. 점수가 높을수록 오래 지속.',
     'longevity_score'),
    ('lightweight', '가벼움',   'Lightweight Feel',
     '착용 시 무겁거나 답답하지 않은 정도. 점수가 높을수록 자연스러운 착용감.',
     'lightweight_score')
ON CONFLICT (metric_id) DO NOTHING;


-- 2) 리뷰 용어 → 표준 지표 매핑 테이블 (Synonym Dictionary)
CREATE TABLE IF NOT EXISTS public.review_term_mappings (
    id              SERIAL PRIMARY KEY,
    raw_term        TEXT NOT NULL,             -- 리뷰에서 등장하는 원본 표현
    metric_id       TEXT NOT NULL REFERENCES public.business_metrics(metric_id),
    sentiment       TEXT DEFAULT 'positive',   -- 'positive' 또는 'negative'
    confidence      NUMERIC DEFAULT 1.0,       -- 매핑 신뢰도 (0~1)
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 커버력 관련 동의어 매핑
INSERT INTO public.review_term_mappings (raw_term, metric_id, sentiment) VALUES
    ('커버력 좋아요',        'coverage', 'positive'),
    ('잡티가 가려져요',      'coverage', 'positive'),
    ('트러블 커버',          'coverage', 'positive'),
    ('결점 커버',            'coverage', 'positive'),
    ('모공이 안보여요',      'coverage', 'positive'),
    ('커버 안돼요',          'coverage', 'negative'),
    ('잡티가 그대로',        'coverage', 'negative'),
    ('다크서클 커버',        'coverage', 'positive'),
    ('흉터 가림',            'coverage', 'positive'),
    ('붉은기 커버',          'coverage', 'positive')
ON CONFLICT DO NOTHING;

-- 지속력 관련 동의어 매핑
INSERT INTO public.review_term_mappings (raw_term, metric_id, sentiment) VALUES
    ('하루종일 유지',        'longevity', 'positive'),
    ('안 지워져요',          'longevity', 'positive'),
    ('저녁까지 OK',          'longevity', 'positive'),
    ('오래 가요',            'longevity', 'positive'),
    ('지속력 좋아요',        'longevity', 'positive'),
    ('밀림 없음',            'longevity', 'positive'),
    ('금방 지워져요',        'longevity', 'negative'),
    ('몇시간 못가요',        'longevity', 'negative'),
    ('무너짐',               'longevity', 'negative'),
    ('점심때 이미 밀려요',   'longevity', 'negative')
ON CONFLICT DO NOTHING;

-- 가벼움 관련 동의어 매핑
INSERT INTO public.review_term_mappings (raw_term, metric_id, sentiment) VALUES
    ('가벼운 느낌',          'lightweight', 'positive'),
    ('바른 듯 안 바른 듯',   'lightweight', 'positive'),
    ('자연스러워요',         'lightweight', 'positive'),
    ('무겁지 않아요',        'lightweight', 'positive'),
    ('피부에 착 달라붙어요', 'lightweight', 'positive'),
    ('답답하지 않아요',      'lightweight', 'positive'),
    ('두껍게 발려요',        'lightweight', 'negative'),
    ('무거운 느낌',          'lightweight', 'negative'),
    ('답답해요',             'lightweight', 'negative'),
    ('떡칠 느낌',            'lightweight', 'negative')
ON CONFLICT DO NOTHING;


-- 3) 데이터 카탈로그: 테이블/컬럼 메타데이터 (LLM 참조용)
CREATE TABLE IF NOT EXISTS public.data_catalog (
    id              SERIAL PRIMARY KEY,
    table_name      TEXT NOT NULL,              -- 테이블명
    column_name     TEXT,                       -- 컬럼명 (NULL이면 테이블 레벨 설명)
    description_ko  TEXT NOT NULL,              -- 한국어 설명
    description_en  TEXT,                       -- 영문 설명
    data_type       TEXT,                       -- 데이터 타입
    example_value   TEXT,                       -- 예시 값
    business_rule   TEXT,                       -- 비즈니스 규칙/주의사항
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- products 테이블 카탈로그
INSERT INTO public.data_catalog (table_name, column_name, description_ko, description_en, data_type, example_value, business_rule) VALUES
    ('products', NULL,
     '올리브영에서 수집한 남성 화장품 제품 마스터 테이블',
     'Master table for men''s cosmetic products from Olive Young',
     NULL, NULL,
     'merge_variants.py 실행 후 기획세트/리필 변형이 본품으로 병합된 상태'),
    ('products', 'coverage_score',
     'AI가 리뷰를 분석하여 산출한 커버력 점수 (1~5)',
     'Coverage score from AI review analysis',
     'numeric', '3.62',
     '1=매우 낮음, 3=보통, 5=매우 높음. NULL이면 3.0으로 대체하여 계산'),
    ('products', 'longevity_score',
     'AI가 리뷰를 분석하여 산출한 지속력 점수 (1~5)',
     'Longevity score from AI review analysis',
     'numeric', '3.12',
     '1=금방 지워짐, 3=보통, 5=하루종일 유지'),
    ('products', 'lightweight_score',
     'AI가 리뷰를 분석하여 산출한 착용감/가벼움 점수 (1~5)',
     'Lightweight feel score from AI review analysis',
     'numeric', '4.0',
     '1=무겁고 답답, 3=보통, 5=바른 듯 안 바른 듯 자연스러움'),
    ('products', 'compat_oily',
     '지성 피부 호환성 점수 (0~1)',
     'Compatibility score for oily skin type',
     'numeric', '0.72',
     '0=비추천, 0.5=보통, 1=매우적합. 성분 분석 기반'),
    ('products', 'suitable_concerns',
     '해당 제품이 적합한 피부 고민 목록',
     'List of skin concerns this product addresses',
     'text[]', '{acne,pore,redness}',
     '가능한 값: acne, pore, redness, spots, wrinkle')
ON CONFLICT DO NOTHING;

-- reviews 테이블 카탈로그
INSERT INTO public.data_catalog (table_name, column_name, description_ko, description_en, data_type, example_value, business_rule) VALUES
    ('reviews', NULL,
     '올리브영 제품 리뷰 팩트 테이블',
     'Fact table for Olive Young product reviews',
     NULL, NULL,
     'product_id로 products 테이블과 1:N 관계. is_best=true는 베스트 리뷰'),
    ('reviews', 'skin_type',
     '리뷰 작성자의 피부 타입',
     'Reviewer''s self-reported skin type',
     'text', '지성',
     '올리브영에서 사용자가 직접 입력한 값. 한국어 원본 그대로 저장')
ON CONFLICT DO NOTHING;


-- ============================================================================
-- Semantic Layer 활용 예시: 리뷰에서 특정 지표 관련 표현 검색
-- ============================================================================
-- SELECT
--     r.content,
--     t.raw_term,
--     t.metric_id,
--     m.metric_name_ko,
--     t.sentiment
-- FROM public.reviews r
-- JOIN public.review_term_mappings t
--     ON r.content ILIKE '%' || t.raw_term || '%'
-- JOIN public.business_metrics m
--     ON t.metric_id = m.metric_id
-- WHERE m.metric_id = 'coverage'
-- LIMIT 20;
