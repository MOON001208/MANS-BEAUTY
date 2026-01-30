"""
별점 수정 및 신규 리뷰 추가 스크립트
- analysis_master.plk의 별점을 중복데이터제거.plk의 별점으로 수정
- 신규 리뷰 407건 추가 및 전처리
"""

import pandas as pd
import numpy as np
import re
from datetime import datetime
import os

# 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER_PATH = os.path.join(BASE_DIR, 'data', 'analysis_master.plk')
NEW_DATA_PATH = os.path.join(BASE_DIR, 'code', '중복데이터제거.plk')
BACKUP_DIR = os.path.join(BASE_DIR, 'data')

def create_backup(file_path):
    """원본 파일 백업 생성"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"analysis_master_backup_{timestamp}.plk"
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    
    df = pd.read_pickle(file_path)
    df.to_pickle(backup_path)
    print(f"✅ 백업 생성 완료: {backup_name}")
    return backup_path

def extract_shade_number(option_str):
    """옵션에서 호수 추출"""
    if pd.isna(option_str):
        return None
    
    # 호수 패턴 매칭 (1호, 01호, 21호, 001 등)
    patterns = [
        r'(\d{1,2})호',  # 1호, 21호
        r'\b(0*\d{1,2})\b(?!\s*[가-힣])',  # 01, 001
    ]
    
    for pattern in patterns:
        match = re.search(pattern, str(option_str))
        if match:
            return match.group(1).lstrip('0') + '호' if match.group(1) else None
    return None

def map_shade_standard(shade):
    """호수를 Shade_Standard로 매핑"""
    if pd.isna(shade):
        return 'Unknown'
    
    shade_str = str(shade)
    # 21호 계열 → Light
    if any(x in shade_str for x in ['1호', '21호', '01', '라이트']):
        return 'Light (21호)'
    # 23호 계열 → Medium
    elif any(x in shade_str for x in ['2호', '23호', '02', '미디엄', '내추럴']):
        return 'Medium (23호)'
    # 25호 계열 → Dark
    elif any(x in shade_str for x in ['3호', '4호', '5호', '25호', '03', '04', '05', '다크', '딥']):
        return 'Dark (25호)'
    else:
        return 'Unknown'

def parse_skin_type(skin_type_str):
    """피부타입 문자열에서 각 플래그 추출"""
    if pd.isna(skin_type_str):
        return {
            'is_dry': 0, 'is_oily': 0, 'is_combi': 0, 'is_sensitive': 0,
            'is_cool': 0, 'is_warm': 0,
            'concern_pore': 0, 'concern_trouble': 0, 'concern_wrinkle': 0, 'concern_whitening': 0
        }
    
    s = str(skin_type_str)
    return {
        'is_dry': 1 if '건성' in s else 0,
        'is_oily': 1 if '지성' in s else 0,
        'is_combi': 1 if '복합성' in s else 0,
        'is_sensitive': 1 if '민감성' in s else 0,
        'is_cool': 1 if '쿨톤' in s else 0,
        'is_warm': 1 if '웜톤' in s else 0,
        'concern_pore': 1 if any(x in s for x in ['모공', '블랙헤드']) else 0,
        'concern_trouble': 1 if '트러블' in s else 0,
        'concern_wrinkle': 1 if any(x in s for x in ['주름', '각질']) else 0,
        'concern_whitening': 1 if any(x in s for x in ['미백', '잡티']) else 0
    }

def preprocess_new_reviews(new_reviews, master_df):
    """신규 리뷰에 대한 전처리 수행"""
    print(f"\n📝 신규 리뷰 {len(new_reviews)}건 전처리 시작...")
    
    # 상품링크별 기존 정보 매핑 테이블 생성
    product_info = master_df.groupby('상품링크').first()[[
        '유해성분개수', 'main_influencer', 'Brand_Tier',
        'ingredients_clean_str', 'ingredients_list', 'ingredient_count'
    ]].to_dict('index')
    
    # 신규 리뷰 복사
    df = new_reviews.copy()
    
    # 1. 호수 추출
    df['호수'] = df['옵션'].apply(extract_shade_number)
    
    # 2. 옵션개수 (옵션이 있으면 1)
    df['옵션개수'] = df['옵션'].apply(lambda x: 1 if pd.notna(x) and str(x).strip() else 0)
    
    # 3. 상품링크 기반 정보 매핑
    def get_product_info(link, col):
        if link in product_info:
            return product_info[link].get(col, None)
        return None
    
    df['유해성분개수'] = df['상품링크'].apply(lambda x: get_product_info(x, '유해성분개수'))
    df['main_influencer'] = df['상품링크'].apply(lambda x: get_product_info(x, 'main_influencer'))
    df['Brand_Tier'] = df['상품링크'].apply(lambda x: get_product_info(x, 'Brand_Tier'))
    df['ingredients_clean_str'] = df['상품링크'].apply(lambda x: get_product_info(x, 'ingredients_clean_str'))
    df['ingredients_list'] = df['상품링크'].apply(lambda x: get_product_info(x, 'ingredients_list'))
    df['ingredient_count'] = df['상품링크'].apply(lambda x: get_product_info(x, 'ingredient_count'))
    
    # 4. 피부타입 파싱
    skin_flags = df['피부타입'].apply(parse_skin_type).apply(pd.Series)
    for col in skin_flags.columns:
        df[col] = skin_flags[col]
    
    # 5. Shade_Standard 매핑
    df['Shade_Standard'] = df['호수'].apply(map_shade_standard)
    
    # 6. is_viral (main_influencer가 있으면 1)
    df['is_viral'] = df['main_influencer'].apply(lambda x: 1 if pd.notna(x) else 0)
    
    # 7. Review_Year, Review_Month
    df['Review_Year'] = df['날짜'].dt.year.astype('int32')
    df['Review_Month'] = df['날짜'].dt.month.astype('int32')
    
    # 8. 리뷰내용 컬럼 제거 (master에는 없음)
    if '리뷰내용' in df.columns:
        df = df.drop(columns=['리뷰내용'])
    
    print(f"✅ 전처리 완료")
    return df

def main():
    print("=" * 60)
    print("🔄 별점 수정 및 신규 리뷰 추가 스크립트")
    print("=" * 60)
    
    # 1. 데이터 로드
    print("\n📂 데이터 로드 중...")
    master = pd.read_pickle(MASTER_PATH)
    new_data = pd.read_pickle(NEW_DATA_PATH)
    
    print(f"   - analysis_master.plk: {master.shape}")
    print(f"   - 중복데이터제거.plk: {new_data.shape}")
    
    # 2. 백업 생성
    print("\n💾 백업 생성 중...")
    create_backup(MASTER_PATH)
    
    # 3. 매칭 키 생성
    print("\n🔑 매칭 키 생성 중...")
    master['match_key'] = master['작성자'].astype(str) + '_' + master['리뷰내용_정제'].astype(str)
    new_data['match_key'] = new_data['작성자'].astype(str) + '_' + new_data['리뷰내용_정제'].astype(str)
    
    # 4. 별점 수정
    print("\n⭐ 별점 수정 중...")
    original_ratings = master['별점'].copy()
    
    # 새 데이터에서 별점 매핑 딕셔너리 생성
    rating_map = new_data.set_index('match_key')['별점'].to_dict()
    
    # 매칭되는 경우 별점 업데이트
    master['별점_new'] = master['match_key'].map(rating_map)
    mask = master['별점_new'].notna()
    master.loc[mask, '별점'] = master.loc[mask, '별점_new'].astype(int)
    master = master.drop(columns=['별점_new'])
    
    # 변경 통계
    changed_count = (original_ratings != master['별점']).sum()
    matched_count = mask.sum()
    print(f"   - 매칭된 레코드: {matched_count}건")
    print(f"   - 실제 별점 변경: {changed_count}건")
    
    # 5. 신규 리뷰 추출 및 전처리
    print("\n🆕 신규 리뷰 처리 중...")
    new_reviews = new_data[~new_data['match_key'].isin(master['match_key'])].copy()
    new_reviews = new_reviews.drop(columns=['match_key'])
    
    print(f"   - 신규 리뷰 수: {len(new_reviews)}건")
    
    if len(new_reviews) > 0:
        new_reviews_processed = preprocess_new_reviews(new_reviews, master)
        
        # match_key 제거 후 병합
        master = master.drop(columns=['match_key'])
        
        # 컬럼 순서 맞추기
        for col in master.columns:
            if col not in new_reviews_processed.columns:
                new_reviews_processed[col] = None
        
        new_reviews_processed = new_reviews_processed[master.columns]
        
        # 데이터 병합
        master = pd.concat([master, new_reviews_processed], ignore_index=True)
        print(f"   - 병합 완료: {master.shape}")
    else:
        master = master.drop(columns=['match_key'])
    
    # 6. 결과 저장
    print("\n💾 결과 저장 중...")
    master.to_pickle(MASTER_PATH)
    print(f"✅ 저장 완료: {MASTER_PATH}")
    
    # 7. 검증
    print("\n" + "=" * 60)
    print("📊 검증 결과")
    print("=" * 60)
    print(f"   - 최종 데이터 shape: {master.shape}")
    print(f"   - 별점 분포:")
    print(master['별점'].value_counts().sort_index().to_string())
    
    print("\n✅ 모든 작업이 완료되었습니다!")
    
    return master

if __name__ == "__main__":
    result = main()
