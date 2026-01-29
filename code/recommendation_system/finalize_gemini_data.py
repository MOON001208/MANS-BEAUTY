"""
Gemini 체크포인트에서 최종 데이터 파일 생성
"""

import pandas as pd
from pathlib import Path

def main():
    base_path = Path(__file__).parent.parent.parent / "data"
    
    # 체크포인트 로드
    checkpoint_path = base_path / "gemini_extraction_checkpoint.plk"
    print(f"Loading checkpoint from {checkpoint_path}...")
    checkpoint = pd.read_pickle(checkpoint_path)
    
    results = checkpoint['results']
    print(f"Loaded {len(results)} results")
    
    # 원본 리뷰 데이터 로드
    reviews_path = base_path / "reviews_normalized.plk"
    print(f"Loading reviews from {reviews_path}...")
    df = pd.read_pickle(reviews_path)
    print(f"Loaded {len(df)} reviews")
    
    # 결과 병합
    df = df.head(len(results))  # 결과 수만큼만 사용
    
    df['attr_coverage'] = [r.get('coverage') for r in results]
    df['attr_longevity'] = [r.get('longevity') for r in results]
    df['attr_lightweight'] = [r.get('lightweight') for r in results]
    df['attr_skin_types'] = [r.get('skin_types', []) for r in results]
    df['attr_skin_concerns'] = [r.get('skin_concerns', []) for r in results]
    df['attr_product_type'] = [r.get('product_type') for r in results]
    df['attr_shade'] = [r.get('shade') for r in results]
    df['attr_sentiment'] = [r.get('sentiment', 'neutral') for r in results]
    
    # 결과 저장
    output_path = base_path / "review_attributes_gemini.plk"
    df.to_pickle(output_path)
    print(f"Saved to {output_path}")
    
    # 통계 출력
    print("\n=== Extraction Statistics ===")
    print(f"Total reviews: {len(df)}")
    print(f"Coverage extracted: {df['attr_coverage'].notna().sum()} ({df['attr_coverage'].notna().mean()*100:.1f}%)")
    print(f"Longevity extracted: {df['attr_longevity'].notna().sum()} ({df['attr_longevity'].notna().mean()*100:.1f}%)")
    print(f"Lightweight extracted: {df['attr_lightweight'].notna().sum()} ({df['attr_lightweight'].notna().mean()*100:.1f}%)")
    
    # 감정 분포
    print(f"\nSentiment distribution:")
    print(df['attr_sentiment'].value_counts())
    
    # 제품 유형 분포
    print(f"\nProduct type distribution:")
    print(df['attr_product_type'].value_counts())

if __name__ == "__main__":
    main()
