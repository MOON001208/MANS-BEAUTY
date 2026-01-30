import pandas as pd
import numpy as np
import re
import os

# 1. 데이터 로드
input_file = r'..\data\review_with_influencers_clean.plk'
df = pd.read_pickle(input_file)

print(f"원본 데이터 수: {len(df)}")

# =============================================================================
# 2. 브랜드 권역(Tier) 구분 (데이터 불균형 전략 반영)
# =============================================================================
# Major Group: 리뷰 수 800개 이상 (오브제, 비레디, 원오브뎀, 그라펜, 라끌랑, 듀이셀)
# Minor Group: 그 외 (다슈, 스웨거, 두잉왓, 정샘물, 엠도씨)
# * 다슈(726개)는 Major에 가까우나 전략 문서 기준 재확인 필요, 여기선 자동 로직 적용
review_counts = df['브랜드'].value_counts()
major_brands = review_counts[review_counts >= 800].index.tolist()

df['Brand_Tier'] = df['브랜드'].apply(lambda x: 'Major' if x in major_brands else 'Minor')
print(f"\n[Brand Tier 분포]\n{df['Brand_Tier'].value_counts()}")

# =============================================================================
# 3. 피부 타입/고민 One-Hot Encoding
# =============================================================================
# 예: "건성,쿨톤,주름" -> is_dry=1, is_cool=1, concern_wrinkle=1

def parse_skin_props(text):
    props = {
        'is_dry': 0, 'is_oily': 0, 'is_combi': 0, 'is_sensitive': 0, # 타입
        'is_cool': 0, 'is_warm': 0, # 톤
        'concern_pore': 0, 'concern_trouble': 0, 'concern_wrinkle': 0, 'concern_whitening': 0 # 고민
    }
    
    if not isinstance(text, str):
        return props
        
    if '건성' in text: props['is_dry'] = 1
    if '지성' in text: props['is_oily'] = 1
    if '복합성' in text: props['is_combi'] = 1
    if '민감' in text: props['is_sensitive'] = 1
    
    if '쿨톤' in text: props['is_cool'] = 1
    if '웜톤' in text: props['is_warm'] = 1
    
    if '모공' in text: props['concern_pore'] = 1
    if '트러블' in text or '잡티' in text: props['concern_trouble'] = 1
    if '주름' in text or '탄력' in text: props['concern_wrinkle'] = 1
    if '미백' in text or '칙칙' in text: props['concern_whitening'] = 1
    
    return props

print("피부타입 변수 전처리 중...")
# 데이터프레임 확장
skin_props_df = df['피부타입'].apply(parse_skin_props).apply(pd.Series)
df = pd.concat([df, skin_props_df], axis=1)

# =============================================================================
# 4. 호수(Shade) 표준화
# =============================================================================
# 1호/21호/밝은 -> Light (21)
# 2호/23호/보통/내추럴 -> Medium (23)
# 3호/25호/어두운 -> Dark (25)

def standardize_shade(brand, shade_str, option_str):
    # 1. 텍스트 정규화 (브랜드, 호수, 옵션 결합)
    target = f"{str(shade_str)} {str(option_str)}".lower()
    
    # 2. 브랜드별 특수 로직 적용
    if brand == '비레디':
        # 1호(Stone), 2호(Ryan) -> Light
        if re.search(r'(1호|01|stone|스톤|2호|02|ryan|라이언)', target):
            return 'Light (21호)'
        # 3호(Jeffrey) -> Medium
        elif re.search(r'(3호|03|jeffrey|제프리)', target):
            return 'Medium (23호)'
        # 4호(Damien), 5호(Owen) -> Dark
        elif re.search(r'(4호|04|damien|데미안|5호|05|owen|오웬)', target):
            return 'Dark (25호)'

    elif brand == '원오브뎀':
        # 원오브뎀 1호는 23~25호(밝은~중간) -> Medium으로 분류 (시중 23호 대응)
        if re.search(r'(1호|001)', target): 
            return 'Medium (23호)'
        # 2호는 25~27호 -> Dark
        elif re.search(r'(2호|002)', target):
            return 'Dark (25호)'
            
    elif brand == '오브제':
        # 1호 -> Light (21~23)
        if re.search(r'(1호|01|아이보리|라이트)', target):
            return 'Light (21호)'
        # 2호 -> Medium (23~25)
        elif re.search(r'(2호|02|베이지|미디움)', target):
            return 'Medium (23호)'
        # 3호(있다면) -> Dark
        elif re.search(r'(3호|03)', target):
            return 'Dark (25호)'

    elif brand == '엠도씨':
        # 1호(21~23) -> Light
        if re.search(r'(1호|01)', target):
            return 'Light (21호)'
        # 2호(23~25) -> Medium
        elif re.search(r'(2호|02)', target):
            return 'Medium (23호)'
        # 3호(25~27) -> Dark
        elif re.search(r'(3호|03)', target):
            return 'Dark (25호)'
            
    # 그라펜, 스웨거, 다슈 등 일반적인 1,2,3호 체계
    # 1호/21호/밝은 -> Light
    if re.search(r'(1호|21호|아이보리|라이트|밝은|bright)', target):
        return 'Light (21호)'
    # 2호/23호/중간/내추럴 -> Medium
    elif re.search(r'(2호|23호|베이지|내추럴|미디움|보통|medium)', target):
        return 'Medium (23호)'
    # 3호/25호/어두운 -> Dark
    elif re.search(r'(3호|24호|25호|딥|다크|어두운|dark)', target):
        return 'Dark (25호)'
        
    return 'Unknown'

print("호수(Shade) 표준화 중... (브랜드별 기준 적용)")
df['Shade_Standard'] = df.apply(lambda x: standardize_shade(x['브랜드'], x['호수'], x['옵션']), axis=1)
print(f"\n[호수 표준화 결과]\n{df['Shade_Standard'].value_counts().head()}")

# =============================================================================
# 5. 바이럴 및 기타 변수
# =============================================================================
df['is_viral'] = df['main_influencer'].notnull().astype(int)
df['Review_Year'] = df['날짜'].dt.year
df['Review_Month'] = df['날짜'].dt.month

# 저장
save_path = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\data\review_processed_metadata.plk'
df.to_pickle(save_path)
print(f"\n메타데이터 전처리 완료 및 저장: {save_path}")
