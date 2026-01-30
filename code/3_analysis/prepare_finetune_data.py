# -*- coding: utf-8 -*-
"""
[Gemini 파인튜닝용 학습 데이터 생성 스크립트]

리뷰 데이터에서 원본-교정본 쌍을 추출하여 
Gemini 파인튜닝에 필요한 JSONL 형식으로 변환합니다.

출력 형식:
{
  "text_input": "원본 리뷰 텍스트",
  "output": "교정된 리뷰 텍스트"
}
"""

import os
import json
import pandas as pd
from datetime import datetime


# 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
OUTPUT_DIR = os.path.join(BASE_DIR, 'finetune_data')

# 출력 디렉토리 생성
os.makedirs(OUTPUT_DIR, exist_ok=True)


def create_training_examples(df, original_col, corrected_col, max_examples=1000):
    """
    학습 데이터 예제 생성
    
    Args:
        df: 데이터프레임
        original_col: 원본 텍스트 컬럼명
        corrected_col: 교정된 텍스트 컬럼명
        max_examples: 최대 예제 수
        
    Returns:
        학습 예제 리스트
    """
    examples = []
    
    # 원본과 교정본이 다른 것만 선택 (실제로 교정이 필요한 케이스)
    df_filtered = df[df[original_col] != df[corrected_col]].copy()
    
    # 너무 짧거나 긴 텍스트 제외
    df_filtered = df_filtered[
        (df_filtered[original_col].str.len() >= 10) &
        (df_filtered[original_col].str.len() <= 500)
    ]
    
    # 샘플링
    if len(df_filtered) > max_examples:
        df_filtered = df_filtered.sample(n=max_examples, random_state=42)
    
    for _, row in df_filtered.iterrows():
        example = {
            "text_input": str(row[original_col]),
            "output": str(row[corrected_col])
        }
        examples.append(example)
    
    return examples


def save_to_jsonl(examples, output_file):
    """JSONL 형식으로 저장"""
    with open(output_file, 'w', encoding='utf-8') as f:
        for example in examples:
            f.write(json.dumps(example, ensure_ascii=False) + '\n')
    
    print(f"저장 완료: {output_file}")
    print(f"총 {len(examples)}개 예제")


def create_validation_split(examples, train_ratio=0.8):
    """학습/검증 데이터 분할"""
    split_idx = int(len(examples) * train_ratio)
    train_examples = examples[:split_idx]
    val_examples = examples[split_idx:]
    
    return train_examples, val_examples


def main():
    print("=" * 60)
    print(" Gemini 파인튜닝 학습 데이터 생성")
    print("=" * 60)
    
    # 1. 데이터 로드
    # 옵션 1: 이미 정규화된 데이터가 있는 경우
    normalized_file = os.path.join(DATA_DIR, 'reviews_normalized.plk')
    
    # 옵션 2: 기존 Two-Track 데이터 사용
    two_track_file = os.path.join(DATA_DIR, 'review_two_track_final.plk')
    
    if os.path.exists(normalized_file):
        print(f"\n데이터 로드: {normalized_file}")
        df = pd.read_pickle(normalized_file)
        original_col = '리뷰내용'  # 또는 실제 컬럼명
        corrected_col = 'gemini_normalized'
    elif os.path.exists(two_track_file):
        print(f"\n데이터 로드: {two_track_file}")
        df = pd.read_pickle(two_track_file)
        original_col = '리뷰내용_정제'
        corrected_col = 'formal_review'
    else:
        print("오류: 학습 데이터 파일을 찾을 수 없습니다.")
        print(f"다음 파일 중 하나가 필요합니다:")
        print(f"  - {normalized_file}")
        print(f"  - {two_track_file}")
        return
    
    print(f"총 {len(df)}개 레코드 로드됨")
    
    # 2. 학습 예제 생성
    print("\n학습 예제 생성 중...")
    examples = create_training_examples(
        df, 
        original_col=original_col,
        corrected_col=corrected_col,
        max_examples=1000  # 필요에 따라 조정
    )
    
    if len(examples) == 0:
        print("오류: 생성된 학습 예제가 없습니다.")
        return
    
    # 3. 학습/검증 분할
    train_examples, val_examples = create_validation_split(examples, train_ratio=0.8)
    
    print(f"\n학습 데이터: {len(train_examples)}개")
    print(f"검증 데이터: {len(val_examples)}개")
    
    # 4. JSONL 파일로 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    train_file = os.path.join(OUTPUT_DIR, f'gemini_train_{timestamp}.jsonl')
    val_file = os.path.join(OUTPUT_DIR, f'gemini_val_{timestamp}.jsonl')
    
    save_to_jsonl(train_examples, train_file)
    save_to_jsonl(val_examples, val_file)
    
    # 5. 샘플 출력
    print("\n" + "=" * 60)
    print(" 학습 데이터 샘플 (처음 3개)")
    print("=" * 60)
    
    for i, example in enumerate(train_examples[:3], 1):
        print(f"\n[예제 {i}]")
        print(f"입력: {example['text_input']}")
        print(f"출력: {example['output']}")
        print("-" * 40)
    
    print("\n✅ 완료! 다음 파일을 Google AI Studio에 업로드하세요:")
    print(f"   - 학습: {train_file}")
    print(f"   - 검증: {val_file}")


if __name__ == "__main__":
    main()
