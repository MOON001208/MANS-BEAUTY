"""
data/ 폴더의 파일들이 코드에서 참조되는지 확인하는 스크립트
"""
import os
import re

PROJECT_ROOT = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석'
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
CODE_DIR = os.path.join(PROJECT_ROOT, 'code')

# data 폴더의 모든 파일 목록
data_files = [
    'analysis_master.plk',
    'analysis_master_backup_20260123_104131.plk',
    'final_review.plk',
    'gemini_analysis_results.csv',
    'gemini_extraction_checkpoint.plk',
    'ingredient_risk_mapping.csv',
    'ingredient_risk_mapping.plk',
    'keyword_extraction_checkpoint.pkl',
    'keyword_extraction_checkpoint2.pkl',
    'keyword_extraction_checkpoint3.pkl',
    'master_table.plk',
    'normalization_checkpoint.plk',
    'oy_data.plk',
    'product_ingredients.csv',
    'product_ingredients_clean.plk',
    'product_master_final.plk',
    'product_profiles.csv',
    'product_profiles.plk',
    'review_attributes.plk',
    'review_attributes_gemini.plk',
    'review_attributes_gemini_backup.plk',
    'review_keywords_gemini.pkl',
    'review_keywords_gemini2.pkl',
    'review_keywords_gemini3.pkl',
    'review_processed_metadata.plk',
    'review_two_track_final.plk',
    'review_with_influencers.plk',
    'review_with_influencers_clean.plk',
    'reviews_normalized.plk',
    'test_recommendations.plk',
    '리뷰tranfomer.plk',
    '리뷰수all.csv',
    '중복데이터제거2.plk',
    '화장품리뷰all.plk',
    '화장품정보all.plk',
    '화장품최종본all.plk',
    '화장품호수정리.csv',
]

def search_in_file(file_path, search_terms):
    """파일에서 검색어 찾기"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        found = []
        for term in search_terms:
            if term in content:
                found.append(term)
        return found
    except:
        return []

def main():
    # 각 데이터 파일에 대한 참조 여부 추적
    file_references = {f: [] for f in data_files}
    
    print("="*70)
    print("데이터 파일 참조 검색 중...")
    print("="*70 + "\n")
    
    # 모든 코드 파일 검색
    code_files_checked = 0
    for root, dirs, files in os.walk(CODE_DIR):
        for file in files:
            if file.endswith(('.py', '.ipynb')):
                file_path = os.path.join(root, file)
                code_files_checked += 1
                
                # 각 데이터 파일명으로 검색
                for data_file in data_files:
                    # 파일명만으로 검색 (확장자 포함)
                    if data_file in open(file_path, 'r', encoding='utf-8', errors='ignore').read():
                        file_references[data_file].append(os.path.relpath(file_path, PROJECT_ROOT))
    
    # 결과 출력
    print(f"검색 완료: {code_files_checked}개 코드 파일 검색\n")
    
    # 참조되는 파일
    referenced_files = []
    unreferenced_files = []
    
    for data_file, refs in file_references.items():
        if refs:
            referenced_files.append((data_file, refs))
        else:
            unreferenced_files.append(data_file)
    
    # 참조되지 않는 파일 출력
    print("="*70)
    print(f"🔴 참조되지 않는 데이터 파일 ({len(unreferenced_files)}개)")
    print("="*70)
    if unreferenced_files:
        for i, f in enumerate(unreferenced_files, 1):
            file_path = os.path.join(DATA_DIR, f)
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            print(f"{i:2d}. {f:<50} ({size_mb:>8.2f} MB)")
    else:
        print("모든 파일이 참조되고 있습니다!")
    
    # 참조되는 파일 출력
    print(f"\n{'='*70}")
    print(f"✅ 참조되는 데이터 파일 ({len(referenced_files)}개)")
    print("="*70)
    for data_file, refs in sorted(referenced_files, key=lambda x: len(x[1]), reverse=True):
        print(f"\n📄 {data_file}")
        print(f"   참조 횟수: {len(refs)}개 파일")
        for ref in refs[:3]:  # 최대 3개만 표시
            print(f"   - {ref}")
        if len(refs) > 3:
            print(f"   ... 외 {len(refs)-3}개")
    
    # 요약 통계
    total_size = sum(os.path.getsize(os.path.join(DATA_DIR, f)) for f in unreferenced_files)
    print(f"\n{'='*70}")
    print("📊 요약 통계")
    print("="*70)
    print(f"전체 데이터 파일: {len(data_files)}개")
    print(f"참조되는 파일: {len(referenced_files)}개")
    print(f"참조되지 않는 파일: {len(unreferenced_files)}개")
    print(f"참조되지 않는 파일 총 용량: {total_size / (1024*1024):.2f} MB")

if __name__ == "__main__":
    main()
