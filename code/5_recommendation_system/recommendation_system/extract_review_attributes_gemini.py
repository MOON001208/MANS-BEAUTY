"""
리뷰 속성 추출 모듈 (Gemini API 버전)
정규화된 한국어 리뷰에서 8가지 핵심 속성을 Gemini를 사용하여 추출합니다.

8가지 속성:
1. 피부 밝기 (21호/23호/25호)
2. 피부고민 (여드름/모공/트러블/홍조/잡티)
3. 피부타입 (건성/지성/복합성/민감성)
4. 커버력 (1-5점)
5. 지속력 (1-5점)
6. 가벼운 착용감 (1-5점)
7. 쿠션 vs 리퀴드 (제품 유형)
8. 성분정도 (자연유래/저자극/일반)
"""

import pandas as pd
import numpy as np
import json
import time
import os
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Gemini API
from google import genai

# .env 파일 로드
load_dotenv()

# Gemini 클라이언트 설정
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# ===== 프롬프트 템플릿 =====

EXTRACTION_PROMPT = """당신은 화장품 리뷰 분석 전문가입니다. 다음 남성 화장품(쿠션/파운데이션) 리뷰를 분석하고, 아래 속성들을 JSON 형식으로 추출해주세요.

### 추출할 속성:
1. **coverage** (커버력): 1-5점 (1=쌩얼/투명, 3=자연스러움, 5=풀커버). 언급 없으면 null
2. **longevity** (지속력): 1-5점 (1=금방 무너짐, 3=반나절, 5=하루종일). 언급 없으면 null
3. **lightweight** (착용감): 1-5점 (1=무겁고 답답, 3=보통, 5=가볍고 산뜻). 언급 없으면 null
4. **skin_types** (적합한 피부타입): ["oily", "dry", "combination", "sensitive"] 중 해당하는 것들 (배열)
5. **skin_concerns** (다루는 피부고민): ["acne", "pore", "redness", "spots", "wrinkle"] 중 해당하는 것들 (배열)
6. **product_type** (제품유형): "cushion", "liquid", "stick" 중 하나. 모르면 null
7. **shade** (호수): "21", "23", "25" 또는 null
8. **sentiment** (전반적 감정): "positive", "neutral", "negative" 중 하나

### 분석할 리뷰:
제품명: {product_name}
리뷰: {review_text}

### 응답 형식 (반드시 유효한 JSON만 출력):
```json
{{
  "coverage": null,
  "longevity": null,
  "lightweight": null,
  "skin_types": [],
  "skin_concerns": [],
  "product_type": null,
  "shade": null,
  "sentiment": "neutral"
}}
```

JSON만 출력하세요. 다른 설명은 불필요합니다."""


BATCH_EXTRACTION_PROMPT = """당신은 화장품 리뷰 분석 전문가입니다. 다음 {count}개의 남성 화장품 리뷰를 분석하고, 각 리뷰에 대해 속성을 추출해주세요.

### 추출할 속성:
1. **coverage** (커버력): 1-5점. 언급 없으면 null
2. **longevity** (지속력): 1-5점. 언급 없으면 null
3. **lightweight** (착용감): 1-5점. 언급 없으면 null
4. **skin_types**: ["oily", "dry", "combination", "sensitive"] 중 해당하는 것들
5. **skin_concerns**: ["acne", "pore", "redness", "spots", "wrinkle"] 중 해당하는 것들
6. **product_type**: "cushion", "liquid", "stick" 또는 null
7. **shade**: "21", "23", "25" 또는 null
8. **sentiment**: "positive", "neutral", "negative"

### 리뷰 목록:
{reviews_json}

### 응답 형식 (반드시 유효한 JSON 배열만 출력):
각 리뷰에 대해 순서대로 결과를 배열로 반환하세요.
```json
[
  {{"coverage": 4, "longevity": 3, "lightweight": 4, "skin_types": ["oily"], "skin_concerns": ["pore"], "product_type": "cushion", "shade": "23", "sentiment": "positive"}},
  ...
]
```

JSON 배열만 출력하세요. 다른 설명은 불필요합니다."""


def extract_single_review(review_text: str, product_name: str) -> Dict:
    """
    단일 리뷰에서 Gemini를 사용하여 속성 추출
    """
    prompt = EXTRACTION_PROMPT.format(
        product_name=product_name,
        review_text=review_text
    )
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=prompt,
            config={
                "temperature": 0.1,
                "max_output_tokens": 500,
            }
        )
        
        # JSON 파싱
        text = response.text.strip()
        # ```json ... ``` 형식 제거
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()
        
        result = json.loads(text)
        return result
        
    except Exception as e:
        print(f"Error extracting attributes: {e}")
        return {
            "coverage": None,
            "longevity": None,
            "lightweight": None,
            "skin_types": [],
            "skin_concerns": [],
            "product_type": None,
            "shade": None,
            "sentiment": "neutral"
        }


def extract_batch_reviews(reviews: List[Dict], batch_size: int = 10) -> List[Dict]:
    """
    배치로 여러 리뷰에서 속성 추출 (비용 효율적)
    """
    reviews_json = json.dumps([
        {"id": i, "product": r["product_name"], "review": r["review_text"][:300]}  # 길이 제한
        for i, r in enumerate(reviews)
    ], ensure_ascii=False)
    
    prompt = BATCH_EXTRACTION_PROMPT.format(
        count=len(reviews),
        reviews_json=reviews_json
    )
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=prompt,
            config={
                "temperature": 0.1,
                "max_output_tokens": 2000,
            }
        )
        
        # JSON 파싱
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()
        
        results = json.loads(text)
        return results
        
    except Exception as e:
        print(f"Error in batch extraction: {e}")
        # 실패 시 기본값 반환
        return [
            {
                "coverage": None,
                "longevity": None,
                "lightweight": None,
                "skin_types": [],
                "skin_concerns": [],
                "product_type": None,
                "shade": None,
                "sentiment": "neutral"
            }
            for _ in reviews
        ]


def process_reviews_with_gemini(df: pd.DataFrame, batch_size: int = 10, 
                                 delay_between_batches: float = 1.0,
                                 checkpoint_every: int = 100,
                                 checkpoint_path: Path = None) -> pd.DataFrame:
    """
    전체 DataFrame을 Gemini로 처리 (체크포인트 지원)
    
    Args:
        df: 입력 DataFrame
        batch_size: 한 번에 처리할 리뷰 수
        delay_between_batches: 배치 간 대기 시간 (초) - rate limiting 방지
        checkpoint_every: 체크포인트 저장 주기 (리뷰 수)
        checkpoint_path: 체크포인트 파일 경로
    """
    print(f"Processing {len(df)} reviews with Gemini API...")
    print(f"Batch size: {batch_size}, Estimated API calls: {len(df) // batch_size + 1}")
    
    # 체크포인트에서 복구
    all_results = []
    start_idx = 0
    
    if checkpoint_path and checkpoint_path.exists():
        print(f"Loading checkpoint from {checkpoint_path}...")
        checkpoint_data = pd.read_pickle(checkpoint_path)
        all_results = checkpoint_data.get('results', [])
        start_idx = checkpoint_data.get('last_idx', 0)
        print(f"Resuming from index {start_idx} ({len(all_results)} results loaded)")
    
    max_retries = 3
    
    for i in range(start_idx, len(df), batch_size):
        batch_df = df.iloc[i:i+batch_size]
        
        # 배치 데이터 준비
        batch_reviews = [
            {
                "product_name": row.get('상품이름', ''),
                "review_text": row.get('gemini_normalized', '') or row.get('리뷰내용_정제', '')
            }
            for _, row in batch_df.iterrows()
        ]
        
        # Gemini 호출 (재시도 로직)
        results = None
        for retry in range(max_retries):
            try:
                results = extract_batch_reviews(batch_reviews, batch_size)
                break
            except Exception as e:
                print(f"  Retry {retry + 1}/{max_retries} - Error: {e}")
                if retry < max_retries - 1:
                    wait_time = (retry + 1) * 10  # 점점 길게 대기
                    print(f"  Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    print(f"  Failed after {max_retries} retries, using default values")
                    results = [
                        {"coverage": None, "longevity": None, "lightweight": None,
                         "skin_types": [], "skin_concerns": [], "product_type": None,
                         "shade": None, "sentiment": "neutral"}
                        for _ in batch_reviews
                    ]
        
        all_results.extend(results)
        
        # 진행 상황 출력
        processed = i + len(batch_df)
        if (i // batch_size + 1) % 10 == 0 or processed == len(df):
            print(f"  Processed {processed} / {len(df)} reviews ({processed/len(df)*100:.1f}%)")
        
        # 체크포인트 저장
        if checkpoint_path and (processed % checkpoint_every == 0 or processed == len(df)):
            checkpoint_data = {
                'results': all_results,
                'last_idx': processed
            }
            pd.to_pickle(checkpoint_data, checkpoint_path)
            print(f"  Checkpoint saved at {processed} reviews")
        
        # Rate limiting 방지 (점진적 대기)
        if i > 0 and i % 500 == 0:
            print(f"  Taking a longer break (10s) to avoid rate limiting...")
            time.sleep(10)
        else:
            time.sleep(delay_between_batches)
    
    # DataFrame에 결과 추가
    df['attr_coverage'] = [r.get('coverage') for r in all_results]
    df['attr_longevity'] = [r.get('longevity') for r in all_results]
    df['attr_lightweight'] = [r.get('lightweight') for r in all_results]
    df['attr_skin_types'] = [r.get('skin_types', []) for r in all_results]
    df['attr_skin_concerns'] = [r.get('skin_concerns', []) for r in all_results]
    df['attr_product_type'] = [r.get('product_type') for r in all_results]
    df['attr_shade'] = [r.get('shade') for r in all_results]
    df['attr_sentiment'] = [r.get('sentiment', 'neutral') for r in all_results]
    
    # 완료 후 체크포인트 삭제
    if checkpoint_path and checkpoint_path.exists():
        checkpoint_path.unlink()
        print("Checkpoint file removed (processing complete)")
    
    return df


def main():
    """메인 실행 함수"""
    base_path = Path(__file__).parent.parent.parent / "data"
    
    # 정규화된 리뷰 로드
    input_path = base_path / "reviews_normalized.plk"
    print(f"Loading reviews from {input_path}...")
    df = pd.read_pickle(input_path)
    
    # 테스트를 위해 샘플만 처리할 수 있음
    #df = df.head(100)  # 테스트용
    
    # 체크포인트 경로 (중단 시 재개 가능)
    checkpoint_path = base_path / "gemini_extraction_checkpoint.plk"
    
    # Gemini로 속성 추출
    df_with_attrs = process_reviews_with_gemini(
        df, 
        batch_size=10,  # 한 번에 10개씩 처리
        delay_between_batches=1.0,  # 1초 대기 (rate limit 방지)
        checkpoint_every=200,  # 200개마다 체크포인트 저장
        checkpoint_path=checkpoint_path
    )
    
    # 결과 저장
    output_path = base_path / "review_attributes_gemini.plk"
    df_with_attrs.to_pickle(output_path)
    print(f"Saved to {output_path}")
    
    # 통계 출력
    print("\n=== Extraction Statistics ===")
    print(f"Total reviews: {len(df_with_attrs)}")
    print(f"Coverage extracted: {df_with_attrs['attr_coverage'].notna().sum()} ({df_with_attrs['attr_coverage'].notna().mean()*100:.1f}%)")
    print(f"Longevity extracted: {df_with_attrs['attr_longevity'].notna().sum()} ({df_with_attrs['attr_longevity'].notna().mean()*100:.1f}%)")
    print(f"Lightweight extracted: {df_with_attrs['attr_lightweight'].notna().sum()} ({df_with_attrs['attr_lightweight'].notna().mean()*100:.1f}%)")
    
    # 감정 분포
    print(f"\nSentiment distribution:")
    print(df_with_attrs['attr_sentiment'].value_counts())
    
    # 샘플 출력
    print("\n=== Sample Results ===")
    sample = df_with_attrs[['gemini_normalized', 'attr_coverage', 'attr_longevity', 
                            'attr_lightweight', 'attr_sentiment']].head(5)
    for idx, row in sample.iterrows():
        print(f"\nReview: {row['gemini_normalized'][:100]}...")
        print(f"  Coverage: {row['attr_coverage']}, Longevity: {row['attr_longevity']}, "
              f"Lightweight: {row['attr_lightweight']}, Sentiment: {row['attr_sentiment']}")


if __name__ == "__main__":
    main()
