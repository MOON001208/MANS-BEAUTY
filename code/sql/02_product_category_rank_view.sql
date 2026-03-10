-- ============================================================================
-- 02. 카테고리별 속성 백분위 랭킹 뷰 (product_category_rank)
-- ============================================================================
-- 목적:
--   사용자가 '커버력', '지속력', '가벼움' 등의 세부 속성에 가중치를 입력했을 때,
--   카테고리 내에서 해당 제품이 상대적으로 어떤 위치에 있는지를 0~1 사이의
--   백분위 순위로 수치화한다.
--
-- 핵심 SQL 기법:
--   - PERCENT_RANK() OVER (PARTITION BY ... ORDER BY ...):
--     카테고리 단위로 각 속성의 상대적 위치를 0~1 정규화
--   - COALESCE: 속성 점수가 NULL인 제품은 중간값(3.0)으로 대체
--
-- 추천 엔진 활용:
--   사용자가 (커버력=5, 지속력=3, 가벼움=1) 입력 시,
--   각 백분위 랭크에 가중치를 곱하여 최종 추천 점수를 산출할 수 있다.
--
-- 사용 예시:
--   SELECT * FROM product_category_rank
--   WHERE category ILIKE '%쿠션%'
--   ORDER BY coverage_pct_rank DESC;
-- ============================================================================

CREATE OR REPLACE VIEW public.product_category_rank AS
SELECT
    p.id                                                AS product_id,
    p.name                                              AS product_name,
    p.brand,
    p.category,
    p.price,
    p.review_count,
    p.star_rating,

    -- 원본 속성 점수 (1~5 스케일)
    COALESCE(p.coverage_score, 3.0)                     AS coverage_score,
    COALESCE(p.longevity_score, 3.0)                    AS longevity_score,
    COALESCE(p.lightweight_score, 3.0)                  AS lightweight_score,

    -- ✅ 카테고리 내 상대적 백분위 순위 (0 = 최하위, 1 = 최상위)
    PERCENT_RANK() OVER (
        PARTITION BY p.category
        ORDER BY COALESCE(p.coverage_score, 3.0) ASC
    )                                                   AS coverage_pct_rank,

    PERCENT_RANK() OVER (
        PARTITION BY p.category
        ORDER BY COALESCE(p.longevity_score, 3.0) ASC
    )                                                   AS longevity_pct_rank,

    PERCENT_RANK() OVER (
        PARTITION BY p.category
        ORDER BY COALESCE(p.lightweight_score, 3.0) ASC
    )                                                   AS lightweight_pct_rank,

    -- ✅ 리뷰 수 기반 인기도 순위 (대중성 가중치에 활용)
    PERCENT_RANK() OVER (
        PARTITION BY p.category
        ORDER BY COALESCE(p.review_count, 0) ASC
    )                                                   AS popularity_pct_rank

FROM public.products p
WHERE p.review_count >= 10;  -- 최소 리뷰 수 필터 (노이즈 제거)


-- ============================================================================
-- 추천 점수 산출 쿼리 (사용자 가중치 입력 기반)
-- ============================================================================
-- 사용자 입력 예시: 커버력=5, 지속력=3, 가벼움=1 (1~5 스케일)
-- 각 가중치를 백분위 랭크에 곱한 뒤 합산하여 최종 추천 점수 산출
--
-- SELECT
--     product_id,
--     product_name,
--     brand,
--     category,
--     price,
--     coverage_score,
--     longevity_score,
--     lightweight_score,
--     ROUND((
--         coverage_pct_rank   * 5 +   -- 사용자 커버력 가중치 = 5
--         longevity_pct_rank  * 3 +   -- 사용자 지속력 가중치 = 3
--         lightweight_pct_rank * 1    -- 사용자 가벼움 가중치 = 1
--     )::numeric, 4) AS weighted_recommendation_score
-- FROM product_category_rank
-- WHERE category ILIKE '%쿠션%'
-- ORDER BY weighted_recommendation_score DESC
-- LIMIT 10;
