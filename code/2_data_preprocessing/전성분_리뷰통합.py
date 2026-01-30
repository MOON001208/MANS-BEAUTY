import pandas as pd
import numpy as np

# 경로 설정
REVIEW_FILE = r'../data/review_with_influencers_clean.plk'
INGREDIENT_FILE = r'../data/product_ingredients_clean.plk'
OUTPUT_FILE = r'../data/product_master_final.plk'

def main():
    print("1. 데이터 로드 중...")
    df_reviews = pd.read_pickle(REVIEW_FILE)
    df_ing = pd.read_pickle(INGREDIENT_FILE)
    
    print(f"- 리뷰 데이터: {df_reviews.shape}")
    print(f"- 성분 데이터: {df_ing.shape}")
    
    # 2. Key 컬럼 통일 (상품이름 vs product_name)
    # df_ing의 'product_name'을 '상품이름'으로 변경하여 리뷰 데이터와 맞춤
    if 'product_name' in df_ing.columns:
        df_ing = df_ing.rename(columns={'product_name': '상품이름'})
    
    # 성분 데이터에서 필요한 컬럼만 선택 (중복 방지)
    # 'ingredients_clean_str': 세트 분리 후 정제된 성분 문자열
    # 'ingredients_list': 분석용 성분 리스트
    cols_to_use = ['상품이름', 'ingredients_clean_str', 'ingredients_list', 'ingredient_count']
    df_ing_subset = df_ing[cols_to_use]
    
    print("\n2. 데이터 병합 중 (Left Join)...")
    # 리뷰 데이터(Left)에 성분 데이터(Right)를 병합
    df_merged = pd.merge(df_reviews, df_ing_subset, on='상품이름', how='left')
    
    # 3. 병합 결과 확인
    print(f"- 병합된 데이터: {df_merged.shape}")
    
    # 누락된 데이터 확인 (전성분이 없는 상품)
    missing_ing = df_merged['ingredients_list'].isnull().sum()
    print(f"- 전성분 정보가 없는 리뷰 수: {missing_ing} (전체 {len(df_merged)} 중)")
    
    # 4. 저장
    print(f"\n3. 저장 중: {OUTPUT_FILE}")
    df_merged.to_pickle(OUTPUT_FILE)
    print("완료!")

if __name__ == "__main__":
    main()