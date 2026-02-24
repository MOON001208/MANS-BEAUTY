/**
 * 콘텐츠 기반 추천 엔진 (Content-Based Recommender)
 * Python content_based_recommender.py를 JavaScript로 포팅
 * 
 * 매칭 알고리즘:
 * - 가중 점수 합계 방식
 * - 6가지 속성별 유사도 계산
 * - 최적 매칭 제품 추천
 */

// ===== 속성별 가중치 =====
const WEIGHTS = {
    skin_brightness: 0.25,  // 피부 밝기 (호수)
    skin_concerns: 0.15,    // 피부고민
    skin_type: 0.15,        // 피부타입
    coverage: 0.25,         // 커버력 (강화)
    longevity: 0.10,        // 지속력
    lightweight: 0.10,      // 착용감
};

/**
 * 호수 유사도 계산
 * 정확히 일치하면 1.0, 인접하면 0.5, 아니면 0.0
 */
function calculateShadeSimilarity(userShade, productShades) {
    if (!productShades || productShades.length === 0) {
        return 0.5; // 정보 없으면 중간 점수
    }

    // 호수 표준화 매핑
    const shadeMap = {
        '21': ['21', '21호', '1호', '01', '001'],
        '23': ['23', '23호', '2호', '02', '002'],
        '25': ['25', '25호', '3호', '03', '003', '27', '4호', '04', '5호', '05']
    };

    // 제품 호수를 표준화
    const normalizedProductShades = productShades.map(shade => {
        for (const [standard, variants] of Object.entries(shadeMap)) {
            if (variants.includes(shade)) return standard;
        }
        return shade;
    });

    // 정확히 일치
    if (normalizedProductShades.includes(userShade)) {
        return 1.0;
    }

    // 인접 호수
    const shadeOrder = ['21', '23', '25'];
    const userIdx = shadeOrder.indexOf(userShade);
    if (userIdx !== -1) {
        for (const shade of normalizedProductShades) {
            const prodIdx = shadeOrder.indexOf(shade);
            if (prodIdx !== -1 && Math.abs(userIdx - prodIdx) === 1) {
                return 0.5;
            }
        }
    }

    return 0.3; // 매칭 불가능한 경우에도 너무 낮은 점수 방지
}

/**
 * 피부고민 유사도 계산 (사용자 고민 중 몇개가 커버되는지)
 */
function calculateConcernsSimilarity(userConcerns, productConcerns) {
    if (!userConcerns || userConcerns.length === 0) {
        return 1.0; // 사용자가 고민을 선택하지 않으면 모든 제품 OK
    }
    if (!productConcerns || productConcerns.length === 0) {
        return 0.5; // 제품 정보 없으면 중간 점수
    }

    const userSet = new Set(userConcerns);
    const productSet = new Set(productConcerns);

    let intersection = 0;
    for (const concern of userSet) {
        if (productSet.has(concern)) {
            intersection++;
        }
    }

    return intersection / userSet.size;
}

/**
 * 피부타입 유사도 계산
 */
function calculateSkinTypeSimilarity(userType, productTypes, compatScores) {
    // 호환성 점수 사용 (성분 기반)
    let baseCompat;
    switch (userType) {
        case 'oily':
            baseCompat = compatScores.compat_oily || 0.5;
            break;
        case 'dry':
            baseCompat = compatScores.compat_dry || 0.5;
            break;
        case 'sensitive':
            baseCompat = compatScores.compat_sensitive || 0.5;
            break;
        default:
            baseCompat = compatScores.compat_combination || 0.5;
    }

    // 리뷰에서 추출된 피부타입과도 매칭
    if (productTypes && productTypes.includes(userType)) {
        return Math.min(1.0, baseCompat + 0.3);
    }

    return baseCompat;
}

/**
 * 수치형 속성 유사도 계산 (1-5 척도)
 * 차이가 적을수록 높은 점수
 */
function calculateNumericSimilarity(userPref, productScore) {
    if (productScore === null || productScore === undefined || isNaN(productScore)) {
        return 0.5; // 정보 없으면 중간 점수
    }

    const diff = Math.abs(userPref - productScore);
    return Math.max(0, 1 - diff / 4);
}

/**
 * 매칭 이유 설명 생성
 */
function generateMatchReasons(user, product, details) {
    const reasons = [];

    if ((details.skin_type || 0) >= 0.7) {
        reasons.push(`✓ ${SKIN_TYPE_LABELS[user.skin_type] || user.skin_type} 피부에 적합`);
    }

    if ((details.concerns || 0) >= 0.5 && user.skin_concerns && user.skin_concerns.length > 0) {
        const labels = user.skin_concerns.map(c => CONCERN_LABELS[c] || c).join(', ');
        reasons.push(`✓ ${labels} 고민에 효과적`);
    }

    if ((details.coverage || 0) >= 0.7) {
        const level = user.coverage_pref >= 4 ? '높은' : '자연스러운';
        reasons.push(`✓ ${level} 커버력 제공`);
    }

    if ((details.longevity || 0) >= 0.7) {
        reasons.push('✓ 지속력 우수');
    }

    if ((details.lightweight || 0) >= 0.7) {
        reasons.push('✓ 가벼운 착용감');
    }

    if (product.ingredient_level === '저자극' || product.ingredient_level === '자연유래') {
        reasons.push(`✓ ${product.ingredient_level} 성분`);
    }

    if ((details.shade || 0) >= 0.8) {
        reasons.push(`✓ ${SHADE_LABELS[user.skin_brightness] || user.skin_brightness + '호'} 적합`);
    }

    return reasons.length > 0 ? reasons : ['✓ 전반적으로 적합한 제품'];
}

/**
 * 메인 추천 함수
 * @param {Object} user - 사용자 프로필
 * @param {Array} products - 제품 배열
 * @param {number} topN - 추천 수
 * @returns {Array} 추천 결과 배열
 */
function recommend(user, products, topN = 5) {
    let filtered = products;

    // 제품 유형 필터링
    if (user.product_type_pref && user.product_type_pref !== 'any') {
        const typeFiltered = products.filter(
            p => p.product_type.toLowerCase() === user.product_type_pref.toLowerCase()
        );
        if (typeFiltered.length > 0) {
            filtered = typeFiltered;
        }
    }

    const results = filtered.map(product => {
        // 각 속성별 유사도 계산
        const shadeSim = calculateShadeSimilarity(
            user.skin_brightness,
            product.suitable_shades || []
        );

        const concernsSim = calculateConcernsSimilarity(
            user.skin_concerns,
            product.suitable_concerns || []
        );

        const skinTypeSim = calculateSkinTypeSimilarity(
            user.skin_type,
            product.suitable_skin_types || [],
            {
                compat_oily: product.compat_oily || 0.5,
                compat_dry: product.compat_dry || 0.5,
                compat_sensitive: product.compat_sensitive || 0.5,
                compat_combination: product.compat_combination || 0.5,
            }
        );

        const coverageSim = calculateNumericSimilarity(
            user.coverage_pref,
            product.coverage_score || 3.0
        );

        const longevitySim = calculateNumericSimilarity(
            user.longevity_pref,
            product.longevity_score || 3.0
        );

        const lightweightSim = calculateNumericSimilarity(
            user.lightweight_pref,
            product.lightweight_score || 3.0
        );

        // 가중 합계 계산
        const details = {
            shade: shadeSim,
            concerns: concernsSim,
            skin_type: skinTypeSim,
            coverage: coverageSim,
            longevity: longevitySim,
            lightweight: lightweightSim,
        };

        const totalScore =
            WEIGHTS.skin_brightness * shadeSim +
            WEIGHTS.skin_concerns * concernsSim +
            WEIGHTS.skin_type * skinTypeSim +
            WEIGHTS.coverage * coverageSim +
            WEIGHTS.longevity * longevitySim +
            WEIGHTS.lightweight * lightweightSim;

        // 매칭 이유 생성
        const reasons = generateMatchReasons(user, product, details);

        return {
            product,
            match_score: Math.round(totalScore * 1000) / 1000,
            match_details: details,
            match_reasons: reasons,
        };
    });

    // 점수 기준 정렬
    results.sort((a, b) => b.match_score - a.match_score);

    return results.slice(0, topN);
}
