
import pandas as pd
import os

def add_persona_to_pkl():
    # 경로 설정
    base_path = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\data'
    pkl_path = os.path.join(base_path, 'review_keywords_gemini3.pkl')
    csv_path = os.path.join(base_path, 'gemini_analysis_results.csv')

    # 파일 로드
    print(f"Loading PKL data from: {pkl_path}")
    if not os.path.exists(pkl_path):
        print("Error: PKL file not found.")
        return

    df_pkl = pd.read_pickle(pkl_path)
    print(f"PKL Rows: {len(df_pkl)}")

    print(f"Loading CSV data from: {csv_path}")
    if not os.path.exists(csv_path):
        print("Error: CSV file not found.")
        return

    df_csv = pd.read_csv(csv_path)
    print(f"CSV Rows: {len(df_csv)}")

    # 행 개수 비교
    if len(df_pkl) != len(df_csv):
        print("Warning: Row counts differ. Detailed check required.")
        # 만약 CSV가 더 적거나 많다면 단순 할당 불가.
        # 공통 컬럼(예: 'gemini_normalized' 또는 원본 텍스트)을 기준으로 병합 시도 가능여부 확인
        return

    # Persona 컬럼 존재 확인
    if 'Persona' not in df_csv.columns:
        print("Error: 'Persona' column is missing in the CSV file.")
        return

    # Persona 추가 (Data integrity 가정: 두 파일은 같은 소스에서 순서 변경 없이 생성됨)
    print("Adding 'Persona' column to PKL dataframe...")
    # .values를 사용하여 인덱스와 관계없이 순서대로 값 주입 (두 파일의 행 순서가 같다고 확신될 때)
    df_pkl['Persona'] = df_csv['Persona'].values

    # 검증: 샘플 출력
    print("\nUpdated DataFrame Sample:")
    print(df_pkl[['상품이름', 'Persona']].head())
    print("\nPersona Distribution:")
    print(df_pkl['Persona'].value_counts())

    # 저장 (덮어쓰기)
    print(f"Saving updated DataFrame to {pkl_path}...")
    df_pkl.to_pickle(pkl_path)
    print("Successfully updated review_keywords_gemini3.pkl")

if __name__ == "__main__":
    add_persona_to_pkl()
