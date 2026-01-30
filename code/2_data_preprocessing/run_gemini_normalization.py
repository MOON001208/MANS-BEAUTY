# -*- coding: utf-8 -*-
"""
[Gemini API 기반 리뷰 정규화 실행 스크립트]

화장품 리뷰 데이터를 로드하고 Gemini API를 사용하여 
맞춤법 교정 및 텍스트 정규화를 수행합니다.

사용법:
    # 샘플 테스트 (10개 리뷰)
    python run_gemini_normalization.py --sample 10
    
    # 제한된 수의 리뷰 처리
    python run_gemini_normalization.py --limit 100 --batch-size 20
    
    # 전체 처리
    python run_gemini_normalization.py
"""

import os
import sys
import argparse
import pandas as pd
from datetime import datetime
from tqdm import tqdm

# 현재 디렉토리를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gemini_text_normalizer import GeminiTextNormalizer


# 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')

# 입력 파일 (우선순위대로)
INPUT_FILES = [
    os.path.join(DATA_DIR, 'analysis_master.plk'),
    os.path.join(DATA_DIR, '화장품리뷰all.plk'),
    os.path.join(DATA_DIR, 'review_with_influencers_clean.plk'),
]

# 출력 파일
OUTPUT_FILE = os.path.join(DATA_DIR, 'reviews_normalized.plk')
CHECKPOINT_FILE = os.path.join(DATA_DIR, 'normalization_checkpoint.plk')

# 리뷰 컬럼명 (데이터셋마다 다를 수 있음)
REVIEW_COLUMNS = ['리뷰내용', '리뷰내용_정제', 'cleaned_text', 'review_text']


def find_input_file() -> str:
    """사용 가능한 입력 파일 찾기"""
    for filepath in INPUT_FILES:
        if os.path.exists(filepath):
            return filepath
    raise FileNotFoundError(
        f"입력 파일을 찾을 수 없습니다. 다음 경로 중 하나에 파일이 있어야 합니다:\n"
        + "\n".join(INPUT_FILES)
    )


def find_review_column(df: pd.DataFrame) -> str:
    """데이터프레임에서 리뷰 컬럼 찾기"""
    for col in REVIEW_COLUMNS:
        if col in df.columns:
            return col
    raise ValueError(
        f"리뷰 컬럼을 찾을 수 없습니다. 다음 중 하나의 컬럼이 필요합니다: {REVIEW_COLUMNS}\n"
        f"현재 컬럼: {list(df.columns)}"
    )


def load_checkpoint() -> pd.DataFrame:
    """체크포인트 파일 로드"""
    if os.path.exists(CHECKPOINT_FILE):
        print(f"체크포인트 파일 로드: {CHECKPOINT_FILE}")
        return pd.read_pickle(CHECKPOINT_FILE)
    return None


def save_checkpoint(df: pd.DataFrame, processed_count: int):
    """체크포인트 저장"""
    df.to_pickle(CHECKPOINT_FILE)
    print(f"\n체크포인트 저장 완료: {processed_count}개 처리됨")


def display_comparison(df: pd.DataFrame, review_col: str, n_samples: int = 5):
    """원본 vs 교정본 비교 출력"""
    print("\n" + "=" * 80)
    print(" [원본 vs 교정본 비교 샘플]")
    print("=" * 80)
    
    # 변경된 항목만 필터링
    if 'gemini_normalized' in df.columns:
        changed = df[df[review_col] != df['gemini_normalized']]
        if len(changed) > 0:
            sample_df = changed.head(n_samples)
        else:
            sample_df = df.head(n_samples)
    else:
        sample_df = df.head(n_samples)
    
    for idx, row in sample_df.iterrows():
        original = str(row[review_col])[:100]
        if 'gemini_normalized' in df.columns:
            normalized = str(row['gemini_normalized'])[:100]
            print(f"▶ 원본: {original}")
            print(f"▷ 교정: {normalized}")
            print("-" * 80)
        else:
            print(f"▶ 원본: {original}")
            print("-" * 80)


def run_sample_test(normalizer: GeminiTextNormalizer, df: pd.DataFrame, 
                    review_col: str, n_samples: int):
    """샘플 리뷰로 테스트 실행"""
    print(f"\n[샘플 테스트 모드: {n_samples}개 리뷰]")
    
    sample_df = df.head(n_samples).copy()
    texts = sample_df[review_col].fillna("").tolist()
    
    print("Gemini API로 맞춤법 교정 중...")
    normalized = normalizer.normalize_batch(texts, batch_size=min(n_samples, 20))
    
    sample_df['gemini_normalized'] = normalized
    display_comparison(sample_df, review_col, n_samples)
    
    return sample_df


def run_full_processing(
    normalizer: GeminiTextNormalizer, 
    df: pd.DataFrame, 
    review_col: str,
    batch_size: int,
    checkpoint_interval: int,
    limit: int = None
):
    """전체 데이터 처리"""
    # 처리할 데이터 제한
    if limit:
        df = df.head(limit).copy()
        print(f"\n[제한 모드: {limit}개 리뷰만 처리]")
    else:
        df = df.copy()
        print(f"\n[전체 처리 모드: {len(df)}개 리뷰]")
    
    # 기존 체크포인트 확인
    checkpoint_df = load_checkpoint()
    start_idx = 0
    
    if checkpoint_df is not None and 'gemini_normalized' in checkpoint_df.columns:
        # 이미 처리된 부분 복원
        processed = checkpoint_df['gemini_normalized'].notna().sum()
        if processed > 0:
            print(f"이전 체크포인트에서 복원: {processed}개 이미 처리됨")
            df['gemini_normalized'] = checkpoint_df['gemini_normalized']
            start_idx = processed
    else:
        df['gemini_normalized'] = None
    
    texts = df[review_col].fillna("").tolist()
    total = len(texts)
    
    print(f"시작 인덱스: {start_idx}, 총 {total - start_idx}개 처리 예정")
    print(f"배치 크기: {batch_size}, 체크포인트 간격: {checkpoint_interval}")
    
    # 배치 처리
    for batch_start in tqdm(range(start_idx, total, batch_size), desc="전체 진행률"):
        batch_end = min(batch_start + batch_size, total)
        batch_texts = texts[batch_start:batch_end]
        
        try:
            normalized = normalizer.normalize_batch(
                batch_texts, 
                batch_size=len(batch_texts),
                show_progress=False
            )
            
            for i, text in enumerate(normalized):
                df.iloc[batch_start + i, df.columns.get_loc('gemini_normalized')] = text
                
        except Exception as e:
            print(f"\n오류 발생 (인덱스 {batch_start}-{batch_end}): {e}")
            # 오류 시 원본 유지
            for i in range(len(batch_texts)):
                if pd.isna(df.iloc[batch_start + i]['gemini_normalized']):
                    df.iloc[batch_start + i, df.columns.get_loc('gemini_normalized')] = batch_texts[i]
        
        # 체크포인트 저장
        if (batch_end % checkpoint_interval == 0) or (batch_end >= total):
            save_checkpoint(df, batch_end)
    
    return df


def main():
    parser = argparse.ArgumentParser(description='Gemini API 기반 리뷰 맞춤법 교정')
    parser.add_argument('--sample', type=int, default=None,
                        help='샘플 테스트할 리뷰 수 (예: --sample 10)')
    parser.add_argument('--limit', type=int, default=None,
                        help='처리할 최대 리뷰 수 (예: --limit 100)')
    parser.add_argument('--batch-size', type=int, default=20,
                        help='배치 크기 (기본값: 20)')
    parser.add_argument('--checkpoint', type=int, default=100,
                        help='체크포인트 저장 간격 (기본값: 100)')
    parser.add_argument('--api-key', type=str, default=None,
                        help='Gemini API 키 (환경변수 대신 사용)')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print(" Gemini API 기반 리뷰 맞춤법 교정 시스템")
    print("=" * 60)
    
    # 입력 파일 찾기
    try:
        input_file = find_input_file()
        print(f"입력 파일: {input_file}")
    except FileNotFoundError as e:
        print(f"오류: {e}")
        return
    
    # 데이터 로드
    print("데이터 로드 중...")
    df = pd.read_pickle(input_file)
    print(f"총 {len(df)}개 레코드 로드됨")
    
    # 리뷰 컬럼 찾기
    try:
        review_col = find_review_column(df)
        print(f"리뷰 컬럼: {review_col}")
    except ValueError as e:
        print(f"오류: {e}")
        return
    
    # Gemini 클라이언트 초기화
    try:
        print("\nGemini API 클라이언트 초기화 중...")
        normalizer = GeminiTextNormalizer(api_key=args.api_key)
        print("초기화 완료!")
    except Exception as e:
        print(f"Gemini 초기화 오류: {e}")
        print("\nGEMINI_API_KEY 환경변수를 설정하거나 --api-key 옵션을 사용하세요.")
        print("예: set GEMINI_API_KEY=your_api_key_here")
        return
    
    # 실행
    if args.sample:
        # 샘플 테스트 모드
        result_df = run_sample_test(normalizer, df, review_col, args.sample)
    else:
        # 전체 처리 모드
        result_df = run_full_processing(
            normalizer, df, review_col,
            batch_size=args.batch_size,
            checkpoint_interval=args.checkpoint,
            limit=args.limit
        )
        
        # 최종 결과 저장
        result_df.to_pickle(OUTPUT_FILE)
        print(f"\n최종 결과 저장 완료: {OUTPUT_FILE}")
        
        # 비교 샘플 출력
        display_comparison(result_df, review_col, 10)
    
    print("\n처리 완료!")


if __name__ == "__main__":
    main()
