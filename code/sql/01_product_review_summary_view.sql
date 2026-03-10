-- ============================================================================
-- 01. 제품-리뷰 통합 통계 뷰 (product_review_summary)
-- ============================================================================
-- 목적:
--   기획 세트/리필 변형 병합 이후에도, products 테이블에 review_count가 0으로 남아 있는
--   데이터 정합성 이슈를 해결하기 위한 안전한 집계 뷰.
--   products 테이블의 캐시된 review_count에 의존하지 않고,
--   reviews 팩트 테이블로부터 직접 집계하여 항상 정확한 값을 보장한다.
--
-- 핵심 SQL 기법:
--   - LEFT JOIN: 리뷰가 0개인 제품도 누락 없이 출력
--   - COALESCE: NULL → 0 으로 안전하게 치환
--   - GROUP BY: 제품 단위 집계
--
-- 사용 예시:
--   SELECT * FROM product_review_summary WHERE actual_review_count > 0 ORDER BY avg_rating DESC;
-- ============================================================================

CREATE OR REPLACE VIEW public.product_review_summary AS
SELECT
    p.id                                        AS product_id,
    p.name                                      AS product_name,
    p.brand,
    p.category,
    p.price,
    p.star_rating                               AS cached_star_rating,
    p.review_count                              AS cached_review_count,

    -- ✅ 리뷰 테이블에서 직접 집계한 실제 통계 (결측치 안전 처리)
    COALESCE(COUNT(r.id), 0)                    AS actual_review_count,
    COALESCE(ROUND(AVG(r.rating)::numeric, 2), 0) AS avg_rating,
    COALESCE(MIN(r.rating), 0)                  AS min_rating,
    COALESCE(MAX(r.rating), 0)                  AS max_rating,

    -- ✅ 캐시 값과 실제 값의 차이 (데이터 품질 모니터링용)
    COALESCE(COUNT(r.id), 0) - COALESCE(p.review_count, 0)
                                                AS review_count_drift,

    -- ✅ 최근 리뷰 날짜 (데이터 갱신 주기 파악)
    MAX(r.created_at)                           AS latest_review_date

FROM public.products p
LEFT JOIN public.reviews r ON p.id = r.product_id
GROUP BY p.id, p.name, p.brand, p.category, p.price, p.star_rating, p.review_count;


-- ============================================================================
-- 데이터 품질 검증 쿼리: 캐시 값과 실제 값이 불일치하는 제품 목록
-- ============================================================================
-- 이 쿼리로 merge_variants.py 실행 후 정합성 검증 수행
-- review_count_drift ≠ 0 인 행이 발견되면 파이프라인 재검토 필요

-- SELECT
--     product_id,
--     product_name,
--     brand,
--     cached_review_count,
--     actual_review_count,
--     review_count_drift
-- FROM product_review_summary
-- WHERE review_count_drift != 0
-- ORDER BY ABS(review_count_drift) DESC;
