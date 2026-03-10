-- ============================================================================
-- 04. 통합 추천 쿼리 (Integrated Recommendation Query)
-- ============================================================================
-- 목적:
--   01, 02, 03에서 구축한 뷰와 Semantic Layer를 조합하여
--   사용자의 입력(피부타입, 선호 가중치, 호수)을 받아
--   최적의 제품을 추천하는 최종 쿼리.
--
-- 이 쿼리는 프론트엔드(page.tsx)의 calcRecommendScore() 로직을
--   순수 SQL로 구현한 버전이다.
--
-- 파라미터 (PostgreSQL 변수로 설정):
--   :user_skin_type   - 사용자 피부 타입 ('oily', 'dry', 'combination', 'sensitive')
--   :coverage_weight  - 커버력 선호도 (1~5)
--   :longevity_weight - 지속력 선호도 (1~5)
--   :lightweight_weight - 가벼움 선호도 (1~5)
--   :user_shade       - 선호 호수 ('21', '23', '25', 'any')
--   :category_filter  - 카테고리 필터 ('%쿠션%', '%톤 로션%', '%')
-- ============================================================================

-- 예시 실행 (Supabase SQL Editor에서):
-- 지성 피부, 커버력 5 / 지속력 3 / 가벼움 1, 23호, 쿠션 카테고리

WITH user_input AS (
    SELECT
        'oily'::TEXT           AS skin_type,
        5                      AS coverage_w,
        3                      AS longevity_w,
        1                      AS lightweight_w,
        '23'::TEXT             AS shade,
        '%쿠션%'::TEXT         AS category_filter
),

-- Step 1: 기본 필터링 (리뷰 200개 이상, 카테고리 매칭)
filtered_products AS (
    SELECT p.*
    FROM public.products p, user_input u
    WHERE p.review_count >= 200
      AND p.category ILIKE u.category_filter
),

-- Step 2: 카테고리 내 백분위 순위 계산 (PERCENT_RANK 윈도우 함수)
ranked AS (
    SELECT
        fp.*,
        PERCENT_RANK() OVER (ORDER BY COALESCE(fp.coverage_score, 3.0) ASC)    AS cov_rank,
        PERCENT_RANK() OVER (ORDER BY COALESCE(fp.longevity_score, 3.0) ASC)   AS lon_rank,
        PERCENT_RANK() OVER (ORDER BY COALESCE(fp.lightweight_score, 3.0) ASC) AS lwt_rank,
        PERCENT_RANK() OVER (ORDER BY COALESCE(fp.review_count, 0) ASC)        AS pop_rank
    FROM filtered_products fp
),

-- Step 3: 피부 호환성 + 속성 가중치 + 인기도 → 최종 점수 계산
scored AS (
    SELECT
        r.id,
        r.name,
        r.brand,
        r.category,
        r.price,
        r.star_rating,
        r.review_count,
        r.coverage_score,
        r.longevity_score,
        r.lightweight_score,
        r.thumbnail_url,
        r.product_url,
        r.suitable_shades,

        -- 피부 호환성 점수 (50점 만점)
        CASE u.skin_type
            WHEN 'oily'        THEN COALESCE(r.compat_oily, 0.5)
            WHEN 'dry'         THEN COALESCE(r.compat_dry, 0.5)
            WHEN 'sensitive'   THEN COALESCE(r.compat_sensitive, 0.5)
            WHEN 'combination' THEN COALESCE(r.compat_combination, 0.5)
            ELSE 0.5
        END * 50 AS skin_compat_score,

        -- 속성 가중치 기반 점수 (백분위 × 가중치, 10점 만점)
        ROUND((
            r.cov_rank * u.coverage_w +
            r.lon_rank * u.longevity_w +
            r.lwt_rank * u.lightweight_w
        )::numeric / (u.coverage_w + u.longevity_w + u.lightweight_w) * 10, 2)
            AS attr_weighted_score,

        -- 인기도 보정 (최대 2점)
        ROUND((r.pop_rank * 2)::numeric, 2) AS popularity_score

    FROM ranked r
    CROSS JOIN user_input u
)

-- Step 4: 최종 추천 순위 출력
SELECT
    s.id,
    s.name,
    s.brand,
    s.category,
    s.price,
    s.star_rating,
    s.review_count,
    s.coverage_score,
    s.longevity_score,
    s.lightweight_score,
    ROUND(s.skin_compat_score::numeric, 2)              AS skin_score,
    s.attr_weighted_score,
    s.popularity_score,
    ROUND((
        s.skin_compat_score +
        s.attr_weighted_score +
        s.popularity_score
    )::numeric, 2)                                       AS total_recommendation_score,
    s.suitable_shades,
    s.product_url
FROM scored s
ORDER BY total_recommendation_score DESC
LIMIT 12;
