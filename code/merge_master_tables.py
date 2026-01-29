"""
merge_master_tables.py
----------------------
product_master_final.plk와 review_processed_metadata.plk를 병합하여
최종 분석용 마스터 테이블을 생성합니다.

Output: data/analysis_master.plk
"""

import pandas as pd
import os

# 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

# 파일 로드
print("📂 파일 로드 중...")
df_product = pd.read_pickle(os.path.join(DATA_DIR, "product_master_final.plk"))
df_metadata = pd.read_pickle(os.path.join(DATA_DIR, "review_processed_metadata.plk"))

print(f"  - product_master_final.plk: {df_product.shape}")
print(f"  - review_processed_metadata.plk: {df_metadata.shape}")

# 공통 컬럼 확인
common_cols = list(set(df_product.columns) & set(df_metadata.columns))
print(f"\n🔗 공통 컬럼 ({len(common_cols)}개): {common_cols}")

# df_product에만 있는 고유 컬럼 (성분 관련)
product_only_cols = [col for col in df_product.columns if col not in common_cols]
print(f"\n📦 product_master_final에만 있는 컬럼: {product_only_cols}")

# df_metadata에만 있는 고유 컬럼 (메타데이터 관련)
metadata_only_cols = [col for col in df_metadata.columns if col not in common_cols]
print(f"📦 review_processed_metadata에만 있는 컬럼: {metadata_only_cols}")

# 병합: df_metadata를 베이스로, df_product의 고유 컬럼만 추가
# 인덱스 기준으로 병합 (행 수가 동일하고 순서 맞음)
print("\n🔧 테이블 병합 중...")
df_merged = df_metadata.copy()

# product_only_cols를 df_merged에 추가
for col in product_only_cols:
    df_merged[col] = df_product[col].values

print(f"\n✅ 병합 완료!")
print(f"  - 최종 Shape: {df_merged.shape}")
print(f"  - 최종 컬럼 ({len(df_merged.columns)}개):")
for i, col in enumerate(df_merged.columns, 1):
    print(f"    {i:02d}. {col}")

# 저장
output_path = os.path.join(DATA_DIR, "analysis_master.plk")
df_merged.to_pickle(output_path)
print(f"\n💾 저장 완료: {output_path}")

# 샘플 미리보기
print("\n📋 샘플 데이터 (첫 3행):")
print(df_merged.head(3).T)  # Transpose for better readability
