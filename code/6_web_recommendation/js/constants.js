/**
 * 상수 및 레이블 데이터 (constants.js)
 * DRY 원칙에 따라 중복되는 레이블을 한곳에서 관리
 */

const SKIN_TYPE_LABELS = {
    oily: '지성',
    dry: '건성',
    combination: '복합성',
    sensitive: '민감성'
};

const CONCERN_LABELS = {
    acne: '여드름',
    pore: '모공',
    spots: '잡티',
    redness: '홍조',
    wrinkle: '주름'
};

const SHADE_LABELS = {
    '21': '밝은톤(21호)',
    '23': '중간톤(23호)',
    '25': '어두운톤(25호)'
};

const PRODUCT_TYPE_MAP = {
    cushion: { label: '쿠션', class: 'type-cushion', emoji: '💄', bg: 'linear-gradient(135deg, #ede7f6 0%, #d1c4e9 100%)' },
    liquid: { label: '리퀴드', class: 'type-liquid', emoji: '🧴', bg: 'linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%)' },
    stick: { label: '스틱', class: 'type-stick', emoji: '📍', bg: 'linear-gradient(135deg, #fbe9e7 0%, #ffccbc 100%)' },
};

const TYPE_FILTER_LABELS = {
    all: '전체',
    cushion: '쿠션',
    liquid: '리퀴드',
    stick: '스틱'
};

/**
 * 별점 HTML 렌더링 (통일된 함수)
 * @param {number} rating - 평점 (0-5)
 * @returns {string} HTML 문자열
 */
function renderStars(rating) {
    const fullStars = Math.floor(rating);
    const halfStar = rating % 1 >= 0.5;
    let html = '★'.repeat(fullStars);
    if (halfStar) html += '½';
    html += '☆'.repeat(5 - fullStars - (halfStar ? 1 : 0));
    return html;
}

/**
 * 가격 포맷팅
 * @param {number} price
 * @returns {string}
 */
function formatPrice(price) {
    return price ? price.toLocaleString() : '-';
}
