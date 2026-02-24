/**
 * 남성 화장품 추천 시스템 - 메인 앱 로직 (v2 - Gemini 리뷰 반영)
 * - 별점 렌더링 통일 (renderStars from constants.js)
 * - 인라인 이벤트 핸들러 제거 → addEventListener 사용
 * - 필터 초기화 기능 추가
 * - 추천 결과에서도 네비 필터 동작
 * - 모달 이전/다음 탐색 기능
 */

// 추천 결과를 전역 저장 (모달 탐색용)
let currentResults = [];     // 원본 추천 목록
let displayedResults = [];   // 현재 화면에 표시된 목록 (필터 적용)
let currentResultIndex = -1;

document.addEventListener('DOMContentLoaded', () => {
  initApp();
});

// ===== 앱 초기화 =====
function initApp() {
  setupNavigation();
  setupSliders();
  setupRecommendButton();
  setupResetButton();
  setupModalEvents();
  showAllProducts();
  updateProductCounts();
}

// ===== 네비게이션 =====
function setupNavigation() {
  const navItems = document.querySelectorAll('.nav-item a');
  navItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
      item.parentElement.classList.add('active');

      const filter = item.dataset.filter;
      const contentArea = document.getElementById('content-area');

      // 추천 결과 모드에서도 필터 동작 (Gemini 피드백 반영)
      if (contentArea.dataset.mode === 'recommendation' && currentResults.length > 0) {
        filterRecommendationsByType(filter);
      } else {
        showAllProducts(filter);
      }
    });
  });
}

// 추천 결과 내 타입 필터링
function filterRecommendationsByType(type) {
  let filtered = currentResults;
  if (type !== 'all') {
    filtered = currentResults.filter(r => r.product.product_type.toLowerCase() === type);
  }
  displayedResults = filtered; // 표시용 목록 업데이트
  if (filtered.length === 0) {
    const contentArea = document.getElementById('content-area');
    contentArea.innerHTML = `
      <div class="result-header">
        <h2>🎯 맞춤 추천 결과</h2>
        <span class="result-count">0개</span>
      </div>
      <div class="welcome-section" style="padding: 60px 40px;">
        <div style="font-size: 48px; margin-bottom: 16px;">🔍</div>
        <h3>해당 유형의 추천 제품이 없습니다</h3>
        <p style="color: var(--color-text-muted); margin-top: 8px;">다른 카테고리를 선택하거나 필터를 변경해주세요</p>
      </div>`;
    return;
  }
  renderRecommendationCards(filtered);
}

// ===== 제품 수 업데이트 =====
function updateProductCounts() {
  const types = { all: 0, cushion: 0, liquid: 0, stick: 0 };
  PRODUCTS.forEach(p => {
    types.all++;
    const t = p.product_type.toLowerCase();
    if (types[t] !== undefined) types[t]++;
  });

  document.querySelectorAll('.nav-count').forEach(el => {
    const type = el.dataset.type;
    if (types[type] !== undefined) {
      el.textContent = types[type];
    }
  });
}

// ===== 슬라이더 =====
function setupSliders() {
  const sliders = document.querySelectorAll('.slider-input');
  sliders.forEach(slider => {
    updateSliderDisplay(slider);
    slider.addEventListener('input', () => updateSliderDisplay(slider));
  });
}

function updateSliderDisplay(slider) {
  const value = slider.value;
  const max = slider.max || 5;
  const percentage = ((value - 1) / (max - 1)) * 100;
  slider.style.setProperty('--val', `${percentage}%`);

  const valueDisplay = slider.parentElement.querySelector('.value');
  if (valueDisplay) {
    valueDisplay.textContent = `${value}/5`;
  }
}

// ===== 필터 초기화 버튼 (Gemini 피드백 반영) =====
function setupResetButton() {
  const btn = document.getElementById('reset-btn');
  if (btn) {
    btn.addEventListener('click', resetFilters);
  }
}

function resetFilters() {
  // 피부 밝기
  document.getElementById('shade-23').checked = true;
  // 피부타입
  document.getElementById('skin-combination').checked = true;
  // 피부고민 해제
  document.querySelectorAll('input[name="concern"]').forEach(el => el.checked = false);
  // 슬라이더 초기화
  document.getElementById('slider-coverage').value = 3;
  document.getElementById('slider-longevity').value = 3;
  document.getElementById('slider-lightweight').value = 4;
  // 제품유형
  document.getElementById('type-any').checked = true;
  // 슬라이더 디스플레이 업데이트
  document.querySelectorAll('.slider-input').forEach(updateSliderDisplay);

  // 전체보기로 복귀
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.querySelector('.nav-item').classList.add('active');
  showAllProducts();
}

// ===== 추천 버튼 =====
function setupRecommendButton() {
  const btn = document.getElementById('recommend-btn');
  btn.addEventListener('click', handleRecommend);
}

function handleRecommend() {
  const btn = document.getElementById('recommend-btn');
  btn.classList.add('loading');
  btn.innerHTML = '<span class="spinner"></span> AI 분석 중...';

  const userProfile = collectUserProfile();

  setTimeout(() => {
    const results = recommend(userProfile, PRODUCTS, 5);
    currentResults = results; // 원본 저장
    displayedResults = results; // 표시용 목록도 동기화

    renderRecommendations(results, userProfile);

    btn.classList.remove('loading');
    btn.innerHTML = '🔍 맞춤 추천받기';

    document.getElementById('content-area').dataset.mode = 'recommendation';
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  }, 800);
}

// ===== 사용자 프로필 수집 =====
function collectUserProfile() {
  const skinBrightness = document.querySelector('input[name="shade"]:checked')?.value || '23';
  const skinType = document.querySelector('input[name="skin-type"]:checked')?.value || 'combination';

  const skinConcerns = [];
  document.querySelectorAll('input[name="concern"]:checked').forEach(el => {
    skinConcerns.push(el.value);
  });

  const coveragePref = parseInt(document.getElementById('slider-coverage').value);
  const longevityPref = parseInt(document.getElementById('slider-longevity').value);
  const lightweightPref = parseInt(document.getElementById('slider-lightweight').value);
  const productTypePref = document.querySelector('input[name="product-type"]:checked')?.value || 'any';

  return {
    skin_brightness: skinBrightness,
    skin_type: skinType,
    skin_concerns: skinConcerns,
    coverage_pref: coveragePref,
    longevity_pref: longevityPref,
    lightweight_pref: lightweightPref,
    product_type_pref: productTypePref,
  };
}

// ===== 추천 결과 렌더링 =====
function renderRecommendations(results, userProfile) {
  // 프로필 태그 생성
  const profileTags = [];
  profileTags.push(`🎨 ${SHADE_LABELS[userProfile.skin_brightness] || userProfile.skin_brightness + '호'}`);
  profileTags.push(`💧 ${SKIN_TYPE_LABELS[userProfile.skin_type] || userProfile.skin_type}`);
  if (userProfile.skin_concerns.length > 0) {
    profileTags.push(`🩹 ${userProfile.skin_concerns.map(c => CONCERN_LABELS[c] || c).join(', ')}`);
  }
  profileTags.push(`💪 커버력 ${userProfile.coverage_pref}/5`);
  profileTags.push(`⏰ 지속력 ${userProfile.longevity_pref}/5`);
  profileTags.push(`🪶 착용감 ${userProfile.lightweight_pref}/5`);

  const contentArea = document.getElementById('content-area');
  contentArea.innerHTML = `
    <div class="result-header">
      <h2>🎯 맞춤 추천 결과</h2>
      <span class="result-count">${results.length}개 추천</span>
    </div>
    <div class="profile-summary">
      ${profileTags.map(tag => `<span class="profile-tag">${tag}</span>`).join('')}
    </div>
    <div id="product-cards-area" class="product-grid"></div>
  `;

  renderRecommendationCards(results);
}

// 카드만 다시 렌더링 (필터 변경 시 재사용)
function renderRecommendationCards(results) {
  const cardsArea = document.getElementById('product-cards-area') || document.getElementById('content-area');

  let html = '';
  results.forEach((result, index) => {
    html += renderProductCard(result, index + 1);
  });

  if (cardsArea.id === 'product-cards-area') {
    cardsArea.innerHTML = html;
  }

  // 이벤트 위임으로 상세보기 버튼 처리 (인라인 이벤트 제거 - Gemini 피드백)
  setupCardEventDelegation(results);
}

// ===== 이벤트 위임 (Gemini 피드백 반영) =====
function setupCardEventDelegation(results) {
  const contentArea = document.getElementById('content-area');

  // 기존 리스너 제거 후 새로 등록
  contentArea.removeEventListener('click', handleContentClick);
  contentArea._results = results; // 데이터 바인딩
  contentArea.addEventListener('click', handleContentClick);
}

function handleContentClick(e) {
  const detailBtn = e.target.closest('.btn-detail');
  if (detailBtn) {
    const productId = parseInt(detailBtn.dataset.productId);
    const index = displayedResults.findIndex(r => r.product.id === productId);
    if (index !== -1) {
      currentResultIndex = index;
      showDetailModal(displayedResults[index]);
    }
    return;
  }

  const gridCard = e.target.closest('.product-grid-card');
  if (gridCard) {
    scrollToFilterAndHighlight();
    return;
  }
}

// ===== 단일 제품 카드 렌더링 =====
function renderProductCard(result, rank) {
  const product = result.product;
  const matchPct = Math.round(result.match_score * 100);

  let scoreClass, matchLabel;
  if (matchPct >= 80) {
    scoreClass = 'score-high';
    matchLabel = '최적';
  } else if (matchPct >= 60) {
    scoreClass = 'score-mid';
    matchLabel = '추천';
  } else {
    scoreClass = 'score-low';
    matchLabel = '참고';
  }

  const typeInfo = PRODUCT_TYPE_MAP[product.product_type] || PRODUCT_TYPE_MAP.cushion;
  const starsHtml = renderStars(product.avg_rating); // 통일된 함수 사용 (Gemini 피드백)
  const priceFormatted = formatPrice(product.price);

  return `
    <div class="product-card ${scoreClass}" style="animation-delay: ${rank * 0.05}s">
      <div class="product-score-panel">
        <span class="rank-badge rank-${rank}">${rank}</span>
        <div class="match-score">${matchPct}%</div>
        <span class="match-label">${matchLabel}</span>
        <span class="match-sub">매칭률</span>
      </div>
      <div class="product-info">
        <div>
          <span class="product-brand">${product.brand}</span>
          <span class="product-type-badge ${typeInfo.class}">${typeInfo.emoji} ${typeInfo.label}</span>
        </div>
        <div class="product-name">${product.product_name}</div>
        <div class="product-meta">
          <div class="meta-item">
            <span class="meta-label">커버력</span>
            <span class="meta-value">${product.coverage_score.toFixed(1)}/5</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">지속력</span>
            <span class="meta-value">${product.longevity_score.toFixed(1)}/5</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">착용감</span>
            <span class="meta-value">${product.lightweight_score.toFixed(1)}/5</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">리뷰</span>
            <span class="meta-value">${product.review_count.toLocaleString()}개</span>
          </div>
        </div>
        <div class="product-rating">
          <span class="stars">${starsHtml}</span>
          <span class="rating-num">${product.avg_rating}</span>
          <span class="review-count">(${product.review_count.toLocaleString()})</span>
        </div>
        <div class="product-price">${priceFormatted}<span class="won">원</span></div>
        <div class="match-reasons">
          ${result.match_reasons.map(r => `<span class="reason-tag">${r}</span>`).join('')}
        </div>
        <div class="product-actions">
          <a href="${product.product_link}" target="_blank" rel="noopener" class="btn-oliveyoung">
            🛒 올리브영에서 보기
          </a>
          <button class="btn-detail" data-product-id="${product.id}">
            📊 상세 분석
          </button>
        </div>
      </div>
    </div>
  `;
}

// ===== 전체 제품 보기 =====
function showAllProducts(typeFilter = 'all') {
  const contentArea = document.getElementById('content-area');
  contentArea.dataset.mode = 'browse';
  currentResults = []; // 추천 결과 초기화

  let filtered = PRODUCTS;
  if (typeFilter !== 'all') {
    filtered = PRODUCTS.filter(p => p.product_type.toLowerCase() === typeFilter);
  }

  filtered = [...filtered].sort((a, b) => b.review_count - a.review_count);

  let html = `
    <div class="welcome-section" style="padding: 40px; margin-bottom: 24px;">
      <div style="font-size: 42px; margin-bottom: 12px;">🎨 ✨ 💄</div>
      <h2 class="welcome-title">남성 화장품 맞춤 추천 시스템</h2>
      <p class="welcome-subtitle">
        17,845개 리뷰를 분석하여 나에게 맞는 제품을 찾아드립니다<br>
        왼쪽 필터에서 피부 정보를 입력하고 <strong>맞춤 추천받기</strong> 버튼을 클릭하세요
      </p>
      <div class="welcome-features">
        <div class="welcome-feature">
          <div class="icon">🧬</div>
          <span class="text">피부타입 분석</span>
        </div>
        <div class="welcome-feature">
          <div class="icon">🎯</div>
          <span class="text">AI 매칭</span>
        </div>
        <div class="welcome-feature">
          <div class="icon">📊</div>
          <span class="text">리뷰 기반</span>
        </div>
        <div class="welcome-feature">
          <div class="icon">🛒</div>
          <span class="text">바로 구매</span>
        </div>
      </div>
    </div>
    <div class="all-products-header">
      <h2>${TYPE_FILTER_LABELS[typeFilter] || '전체'} 제품 (${filtered.length}개)</h2>
    </div>
    <div class="product-grid-view">
  `;

  filtered.forEach(product => {
    const info = PRODUCT_TYPE_MAP[product.product_type] || PRODUCT_TYPE_MAP.cushion;
    const priceFormatted = formatPrice(product.price);
    const starsHtml = renderStars(product.avg_rating); // 통일된 별점 (Gemini 피드백)

    html += `
      <div class="product-grid-card">
        <div class="grid-card-image" style="background: ${info.bg}">
          <span>${info.emoji}</span>
          <span class="grid-card-type">
            <span class="product-type-badge ${info.class}">${info.label}</span>
          </span>
        </div>
        <div class="grid-card-body">
          <div class="grid-card-brand">${product.brand}</div>
          <div class="grid-card-name">${product.product_name}</div>
          <div class="grid-card-footer">
            <span class="grid-card-price">${priceFormatted}원</span>
            <span class="grid-card-rating">
              <span class="stars">${starsHtml}</span>
              <span>${product.avg_rating}</span>
              <span style="color: var(--color-text-muted);">(${product.review_count.toLocaleString()})</span>
            </span>
          </div>
        </div>
      </div>
    `;
  });

  html += '</div>';
  contentArea.innerHTML = html;

  // 이벤트 위임 설정
  setupCardEventDelegation([]);
}

// ===== 필터로 스크롤 =====
function scrollToFilterAndHighlight() {
  const filterPanel = document.querySelector('.filter-panel');
  const btn = document.getElementById('recommend-btn');

  filterPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });

  btn.style.transform = 'scale(1.05)';
  btn.style.boxShadow = '0 8px 30px rgba(155, 206, 38, 0.5)';
  setTimeout(() => {
    btn.style.transform = '';
    btn.style.boxShadow = '';
  }, 1000);
}

// ===== 모달 이벤트 설정 (Gemini 피드백 - 인라인 제거 + 이전/다음) =====
function setupModalEvents() {
  // 닫기 버튼
  const closeBtn = document.getElementById('modal-close-btn');
  if (closeBtn) {
    closeBtn.addEventListener('click', closeDetailModal);
  }

  // 이전/다음 버튼
  const prevBtn = document.getElementById('modal-prev-btn');
  const nextBtn = document.getElementById('modal-next-btn');
  if (prevBtn) prevBtn.addEventListener('click', showPrevProduct);
  if (nextBtn) nextBtn.addEventListener('click', showNextProduct);

  // 모달 외부 클릭 시 닫기
  const modal = document.getElementById('detail-modal');
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeDetailModal();
  });

  // ESC 키로 닫기
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDetailModal();
    // 좌우 화살표로 탐색
    if (e.key === 'ArrowLeft') showPrevProduct();
    if (e.key === 'ArrowRight') showNextProduct();
  });
}

// ===== 상세 분석 모달 =====
function showDetailModal(result) {
  const modal = document.getElementById('detail-modal');
  const product = result.product;
  const details = result.match_details;

  const detailItems = [
    { label: '커버력', value: product.coverage_score.toFixed(1), unit: '/5' },
    { label: '지속력', value: product.longevity_score.toFixed(1), unit: '/5' },
    { label: '착용감', value: product.lightweight_score.toFixed(1), unit: '/5' },
    { label: '평점', value: product.avg_rating.toString(), unit: '/5' },
    { label: '리뷰수', value: product.review_count.toLocaleString(), unit: '개' },
    { label: '가격', value: formatPrice(product.price), unit: '원' },
  ];

  const matchItems = [
    { label: '피부톤 매칭', value: details.shade },
    { label: '피부고민 매칭', value: details.concerns },
    { label: '피부타입 매칭', value: details.skin_type },
    { label: '커버력 매칭', value: details.coverage },
    { label: '지속력 매칭', value: details.longevity },
    { label: '착용감 매칭', value: details.lightweight },
  ];

  document.getElementById('modal-product-name').textContent = product.product_name;
  document.getElementById('modal-scores').innerHTML = detailItems.map(item => `
    <div class="detail-score-item">
      <div class="label">${item.label}</div>
      <div class="value">${item.value}<span class="unit">${item.unit}</span></div>
    </div>
  `).join('');

  document.getElementById('modal-match-bars').innerHTML = matchItems.map(item => `
    <div class="detail-bar">
      <div class="detail-bar-header">
        <span class="detail-bar-label">${item.label}</span>
        <span class="detail-bar-value">${Math.round(item.value * 100)}%</span>
      </div>
      <div class="detail-bar-track">
        <div class="detail-bar-fill" style="width: ${Math.round(item.value * 100)}%"></div>
      </div>
    </div>
  `).join('');

  document.getElementById('modal-reasons').innerHTML = result.match_reasons
    .map(r => `<span class="reason-tag">${r}</span>`).join('');

  // 올리브영 링크
  const linkBtn = document.getElementById('modal-oliveyoung-link');
  if (product.product_link) {
    linkBtn.href = product.product_link;
    linkBtn.style.display = 'inline-flex';
  } else {
    linkBtn.style.display = 'none';
  }

  // 이전/다음 버튼 표시 (Gemini 피드백)
  updateModalNavButtons();

  // 현재 순위 표시
  const navInfo = document.getElementById('modal-nav-info');
  if (navInfo && displayedResults.length > 0) {
    navInfo.textContent = `${currentResultIndex + 1} / ${displayedResults.length}`;
  }

  modal.classList.add('active');
}

function updateModalNavButtons() {
  const prevBtn = document.getElementById('modal-prev-btn');
  const nextBtn = document.getElementById('modal-next-btn');
  const navInfo = document.getElementById('modal-nav-info');

  if (!prevBtn || !nextBtn) return;

  if (displayedResults.length <= 1) {
    prevBtn.style.display = 'none';
    nextBtn.style.display = 'none';
    if (navInfo) navInfo.style.display = 'none';
    return;
  }

  prevBtn.style.display = currentResultIndex > 0 ? 'inline-flex' : 'none';
  nextBtn.style.display = currentResultIndex < displayedResults.length - 1 ? 'inline-flex' : 'none';
  if (navInfo) navInfo.style.display = 'inline';
}

function showPrevProduct() {
  if (currentResultIndex > 0 && displayedResults.length > 0) {
    currentResultIndex--;
    showDetailModal(displayedResults[currentResultIndex]);
  }
}

function showNextProduct() {
  if (currentResultIndex < displayedResults.length - 1 && displayedResults.length > 0) {
    currentResultIndex++;
    showDetailModal(displayedResults[currentResultIndex]);
  }
}

function closeDetailModal() {
  document.getElementById('detail-modal').classList.remove('active');
}
