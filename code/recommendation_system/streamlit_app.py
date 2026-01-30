"""
남성 화장품 맞춤형 추천 시스템 - Streamlit 웹 인터페이스 (Gemini 버전)
콘텐츠 기반 필터링으로 사용자 맞춤 제품을 추천합니다.

실행: streamlit run streamlit_app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path
import sys

# 로컬 모듈 import
sys.path.append(str(Path(__file__).parent))
from content_based_recommender import UserProfile, recommend, RecommendationResult

# ===== 페이지 설정 =====
st.set_page_config(
    page_title="남성 화장품 맞춤 추천",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== 스타일 =====
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stat-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 15px;
        padding: 1.5rem;
        text-align: center;
    }
    .product-card {
        background: white;
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border-left: 5px solid #667eea;
    }
    .match-badge {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 50px;
        padding: 0.5rem 1.5rem;
        font-weight: bold;
        font-size: 1.2rem;
    }
    .reason-tag {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 20px;
        padding: 0.3rem 0.8rem;
        margin: 0.2rem;
        display: inline-block;
        font-size: 0.85rem;
    }
    .sentiment-positive { color: #00c853; }
    .sentiment-neutral { color: #ffc107; }
    .sentiment-negative { color: #ff5252; }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_products():
    """제품 프로필 로드 (상세 경로 디버깅 추가)"""
    # 1. 파일 위치 기준 (프로젝트 루트/data)
    try:
        current_file = Path(__file__).resolve()
        path1 = current_file.parent.parent.parent / "data" / "product_profiles.plk"
        
        # 2. 현재 작업 디렉토리 기준
        path2 = Path("data/product_profiles.plk").resolve()
        
        # 3. 상위 디렉토리 기준 (code 폴더 밖에서 실행할 경우)
        path3 = Path("../data/product_profiles.plk").resolve()
        
        for p in [path1, path2, path3]:
            if p.exists():
                return pd.read_pickle(p)
                
        # 모두 실패 시 상세 에러 발생
        tried_paths = "\n".join([str(p) for p in [path1, path2, path3]])
        raise FileNotFoundError(f"제품 데이터를 찾을 수 없습니다.\n시도한 경로들:\n{tried_paths}")
        
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        raise e


@st.cache_data
def load_reviews():
    """리뷰 데이터 로드 (감정 분석 통계용)"""
    current_file = Path(__file__).resolve()
    base_path = current_file.parent.parent.parent / "data"
    
    review_file = base_path / "review_attributes_gemini.plk"
    if not review_file.exists():
        review_file = Path("data/review_attributes_gemini.plk").resolve()
        
    if review_file.exists():
        return pd.read_pickle(review_file)
    return None


def display_product_card(rec, rank, user_shade="23"):
    """제품 카드 표시"""
    match_pct = int(rec.match_score * 100)
    
    # 매칭률에 따른 색상
    if match_pct >= 80:
        color = "#00c853"
        label = "최적"
    elif match_pct >= 60:
        color = "#ffc107"
        label = "추천"
    else:
        color = "#ff9800"
        label = "참고"
    
    col1, col2 = st.columns([1, 4])
    
    with col1:
        st.markdown(f"""
        <div style="text-align: center; padding: 1rem;">
            <div style="font-size: 0.9rem; color: #666;">매칭률</div>
            <div style="font-size: 2.8rem; font-weight: bold; color: {color};">
                {match_pct}%
            </div>
            <div style="background: {color}; color: white; border-radius: 20px; 
                        padding: 0.2rem 0.8rem; font-size: 0.9rem; display: inline-block;">
                {label}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # 제품명 및 브랜드
        st.markdown(f"### 🏆 {rank}위. {rec.product_name}")
        st.markdown(f"**브랜드:** {rec.brand}")
        
        # 제품 정보 메트릭
        info = rec.product_info
        col_a, col_b, col_c, col_d = st.columns(4)
        
        type_emoji = {"cushion": "💄", "liquid": "🧴", "stick": "📍"}.get(info['product_type'], "💄")
        col_a.metric(f"{type_emoji} 제품유형", info['product_type'] or "쿠션")
        col_b.metric("💪 커버력", f"{info['coverage_score']:.1f}/5")
        col_c.metric("⏰ 지속력", f"{info['longevity_score']:.1f}/5")
        col_d.metric("📝 리뷰수", f"{info['review_count']:,}개")
        
        # 🆕 피부톤에 맞는 옵션 추천
        shade_options = info.get('shade_options', {})
        if shade_options:
            shade_label = {"21": "밝은톤", "23": "중간톤", "25": "어두운톤"}.get(user_shade, "중간톤")
            recommended_option = shade_options.get(user_shade)
            
            if recommended_option:
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                            color: white; border-radius: 10px; padding: 0.8rem; margin: 0.5rem 0;">
                    <strong>🎨 {shade_label} 추천 옵션:</strong> {recommended_option}
                </div>
                """, unsafe_allow_html=True)
            else:
                # 가장 가까운 옵션 표시
                available_options = list(shade_options.values())
                if available_options:
                    st.info(f"🎨 사용 가능 옵션: {', '.join(available_options[:2])}")
        
        # 추천 이유 태그
        st.markdown("**추천 이유:**")
        reason_html = " ".join([
            f'<span class="reason-tag">{r}</span>' 
            for r in rec.match_reasons
        ])
        st.markdown(reason_html, unsafe_allow_html=True)
        
        # 추가 정보
        ingredient_emoji = {"자연유래": "🌿", "저자극": "💧", "일반": "⚪"}.get(
            info.get('ingredient_level', '일반'), "⚪"
        )
        st.caption(f"{ingredient_emoji} 성분: {info.get('ingredient_level', '일반')} | ⭐ 평점: {info.get('avg_rating', 'N/A')}")
        
        # 🆕 제품 링크
        product_link = info.get('product_link', '')
        if product_link:
            st.markdown(f"[🛒 **올리브영에서 보기**]({product_link})")
    
    st.divider()


def show_data_insights(df_products, df_reviews):
    """데이터 인사이트 탭"""
    st.markdown("### 📊 데이터 분석 현황")

    # 통계 카드
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("🛍️ 분석 제품 수", f"{len(df_products)}개")
    with col2:
        review_count = len(df_reviews) if df_reviews is not None else 0
        st.metric("📝 분석 리뷰 수", f"{review_count:,}개")
    with col3:
        avg_reviews = df_products['review_count'].mean()
        st.metric("📊 제품당 평균 리뷰", f"{avg_reviews:.0f}개")
    with col4:
        if df_reviews is not None and 'attr_sentiment' in df_reviews.columns:
            positive_rate = (df_reviews['attr_sentiment'] == 'positive').mean() * 100
            st.metric("😊 긍정 리뷰 비율", f"{positive_rate:.1f}%")

    st.divider()

    # ===== 브랜드 포지셔닝 맵 =====
    st.markdown("### 🎯 브랜드 포지셔닝 맵")
    st.caption("X축: 평균 커버력 | Y축: 평균 지속력 | 버블 크기: 리뷰 수 | 색상: 긍정 리뷰 비율")

    if df_reviews is not None and 'attr_coverage' in df_reviews.columns:
        # 브랜드별 통계 계산
        brand_stats = df_reviews.groupby('브랜드').agg({
            'attr_coverage': 'mean',
            'attr_longevity': 'mean',
            '별점': 'mean',
            '작성자': 'count',
            'attr_sentiment': lambda x: (x == 'positive').mean() * 100
        }).reset_index()
        brand_stats.columns = ['브랜드', '커버력', '지속력', '평균별점', '리뷰수', '긍정비율']

        # 결측치 제거 및 최소 리뷰 수 필터
        brand_stats = brand_stats.dropna()
        brand_stats = brand_stats[brand_stats['리뷰수'] >= 100]

        if len(brand_stats) > 0:
            # Plotly 버블 차트
            fig = px.scatter(
                brand_stats,
                x='커버력',
                y='지속력',
                size='리뷰수',
                color='긍정비율',
                hover_name='브랜드',
                hover_data={
                    '커버력': ':.2f',
                    '지속력': ':.2f',
                    '리뷰수': ':,',
                    '긍정비율': ':.1f'
                },
                color_continuous_scale='RdYlGn',
                size_max=60,
                text='브랜드'
            )

            # 평균선 추가
            avg_coverage = brand_stats['커버력'].mean()
            avg_longevity = brand_stats['지속력'].mean()

            fig.add_hline(y=avg_longevity, line_dash="dash", line_color="gray", opacity=0.5)
            fig.add_vline(x=avg_coverage, line_dash="dash", line_color="gray", opacity=0.5)

            # 레이아웃 설정
            fig.update_traces(textposition='top center', textfont_size=10)
            fig.update_layout(
                xaxis_title="평균 커버력 점수",
                yaxis_title="평균 지속력 점수",
                coloraxis_colorbar_title="긍정비율(%)",
                height=500,
                showlegend=False
            )

            st.plotly_chart(fig, use_container_width=True)

            # 사분면 해석
            col1, col2 = st.columns(2)
            with col1:
                high_both = brand_stats[(brand_stats['커버력'] > avg_coverage) & (brand_stats['지속력'] > avg_longevity)]
                if len(high_both) > 0:
                    st.success(f"**🏆 고커버+고지속:** {', '.join(high_both['브랜드'].tolist())}")
            with col2:
                low_both = brand_stats[(brand_stats['커버력'] <= avg_coverage) & (brand_stats['지속력'] <= avg_longevity)]
                if len(low_both) > 0:
                    st.info(f"**🌿 자연스러운 연출:** {', '.join(low_both['브랜드'].tolist())}")
        else:
            st.warning("분석 가능한 브랜드 데이터가 부족합니다. (최소 100개 리뷰 필요)")
    else:
        st.warning("리뷰 속성 데이터가 없습니다.")

    st.divider()

    # 인기 제품 순위
    st.markdown("### 🏆 리뷰 많은 인기 제품 TOP 10")
    top_products = df_products.nlargest(10, 'review_count')[
        ['product_name', 'brand', 'product_type', 'coverage_score', 'longevity_score', 'review_count', 'avg_rating']
    ].copy()
    top_products.columns = ['제품명', '브랜드', '종류', '커버력', '지속력', '리뷰수', '평점']
    top_products['종류'] = top_products['종류'].map({'cushion': '쿠션', 'liquid': '리퀴드', 'stick': '스틱'})
    st.dataframe(top_products, use_container_width=True, hide_index=True)


def show_recommendation_tab(df_products):
    """추천 시스템 탭"""
    col_main, col_side = st.columns([3, 1])
    
    with col_side:
        st.markdown("### 📋 내 피부 정보")
        
        # 1. 피부 밝기 (호수)
        st.markdown("**1. 피부 밝기**")
        skin_brightness = st.radio(
            "선호하는 호수",
            options=["21", "23", "25"],
            format_func=lambda x: f"{x}호 ({'밝은톤' if x=='21' else '중간톤' if x=='23' else '어두운톤'})",
            index=1,
            horizontal=True,
            key="brightness"
        )
        
        # 2. 피부타입
        st.markdown("**2. 피부타입**")
        skin_type = st.selectbox(
            "나의 피부타입",
            options=["oily", "dry", "combination", "sensitive"],
            format_func=lambda x: {"oily": "🛢️ 지성", "dry": "🏜️ 건성", 
                                   "combination": "🔀 복합성", "sensitive": "🌸 민감성"}[x],
            key="skin_type"
        )
        
        # 3. 피부고민
        st.markdown("**3. 피부고민**")
        concern_acne = st.checkbox("여드름/트러블", key="acne")
        concern_pore = st.checkbox("모공", key="pore")
        concern_spots = st.checkbox("잡티", key="spots")
        concern_redness = st.checkbox("홍조/붉은기", key="redness")
        concern_wrinkle = st.checkbox("주름", key="wrinkle")
        
        skin_concerns = []
        if concern_acne: skin_concerns.append("acne")
        if concern_pore: skin_concerns.append("pore")
        if concern_spots: skin_concerns.append("spots")
        if concern_redness: skin_concerns.append("redness")
        if concern_wrinkle: skin_concerns.append("wrinkle")
        
        st.divider()
        
        # 4-6. 슬라이더 선호도
        st.markdown("**4. 커버력 선호도**")
        coverage_pref = st.slider("커버력", 1, 5, 3, key="coverage",
                                 help="1: 쌩얼, 5: 풀커버")
        
        st.markdown("**5. 지속력 선호도**")
        longevity_pref = st.slider("지속력", 1, 5, 3, key="longevity",
                                  help="1: 몇 시간, 5: 하루종일")
        
        st.markdown("**6. 착용감 선호도**")
        lightweight_pref = st.slider("가벼움", 1, 5, 4, key="lightweight",
                                    help="1: 밀착, 5: 가벼움")
        
        st.divider()
        
        # 7. 제품유형
        st.markdown("**7. 제품 유형**")
        product_type_pref = st.radio(
            "선호 유형",
            options=["any", "cushion", "liquid", "stick"],
            format_func=lambda x: {"any": "상관없음", "cushion": "💄 쿠션", 
                                   "liquid": "🧴 리퀴드", "stick": "📍 스틱"}[x],
            key="product_type"
        )

        
        # 추천받기 버튼
        recommend_btn = st.button("🔍 맞춤 추천받기", use_container_width=True, type="primary")
    
    with col_main:
        if recommend_btn:
            # 사용자 프로필 생성
            user = UserProfile(
                skin_brightness=skin_brightness,
                skin_concerns=skin_concerns,
                skin_type=skin_type,
                coverage_pref=coverage_pref,
                longevity_pref=longevity_pref,
                lightweight_pref=lightweight_pref,
                product_type_pref=product_type_pref
            )
            
            # 추천 실행
            with st.spinner("🔮 AI가 맞춤 제품을 분석중입니다..."):
                recommendations = recommend(user, df_products, top_n=5)
            
            st.success(f"✅ {len(recommendations)}개의 맞춤 제품을 찾았습니다!")
            
            # 선택한 조건 요약
            with st.expander("📋 선택한 조건 보기"):
                st.write(f"**피부톤:** {skin_brightness}호 | **피부타입:** {skin_type}")
                st.write(f"**피부고민:** {skin_concerns if skin_concerns else '없음'}")
                st.write(f"**커버력:** {coverage_pref}/5 | **지속력:** {longevity_pref}/5 | **착용감:** {lightweight_pref}/5")
                st.write(f"**제품유형:** {product_type_pref}")
            
            st.divider()
            
            # 결과 표시
            for i, rec in enumerate(recommendations, 1):
                display_product_card(rec, i, user_shade=skin_brightness)
        else:
            # 초기 상태
            st.markdown("""
            <div style="text-align: center; padding: 3rem; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); border-radius: 15px;">
                <h2>👋 환영합니다!</h2>
                <p style="font-size: 1.2rem; color: #666;">
                    오른쪽에서 피부 정보를 입력하고<br>
                    <strong>맞춤 추천받기</strong> 버튼을 클릭하세요
                </p>
                <p style="font-size: 3rem;">🎨 💄 ✨</p>
            </div>
            """, unsafe_allow_html=True)


def main():
    # 헤더
    st.markdown('<div class="main-header">🎨 남성 화장품 맞춤 추천 시스템</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Gemini AI 기반 콘텐츠 필터링 추천 | 17,845개 리뷰 분석</div>', unsafe_allow_html=True)
    
    # 제품 로드
    try:
        df_products = load_products()
        df_reviews = load_reviews()
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        st.info("먼저 build_product_profiles.py를 실행해주세요.")
        return
    
    # 탭 구성
    tab1, tab2 = st.tabs(["🔍 맞춤 추천", "📊 데이터 분석"])
    
    with tab1:
        show_recommendation_tab(df_products)
    
    with tab2:
        show_data_insights(df_products, df_reviews)


if __name__ == "__main__":
    main()
