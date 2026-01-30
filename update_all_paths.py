"""
모든 코드 파일의 하드코딩된 경로를 새로운 폴더 구조에 맞게 업데이트
"""
import os
import json

PROJECT_ROOT = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석'

# 경로 매핑 (old -> new)
PATH_REPLACEMENTS = [
    # 이미지 출력 경로: code/ -> outputs/
    (r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\gifter_words_analysis.png',
     r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\outputs\gifter_words_analysis.png'),
    
    (r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\men_satisfaction_keywords.png',
     r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\outputs\men_satisfaction_keywords.png'),
    
    (r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\lda_visualization.html',
     r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\outputs\lda_visualization.html'),
    
    (r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\lda_topics_static.png',
     r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\outputs\lda_topics_static.png'),
    
    (r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\persona_keywords_analysis.png',
     r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\outputs\persona_keywords_analysis.png'),
    
    # 데이터 파일: 루트 -> data/
    (r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\final_review.plk',
     r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\data\final_review.plk'),
    
    (r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\product_ingredients.csv',
     r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\data\product_ingredients.csv'),
]

def update_content(content):
    """내용에서 경로 업데이트"""
    original = content
    
    for old_path, new_path in PATH_REPLACEMENTS:
        content = content.replace(old_path, new_path)
    
    return content, content != original

def update_python_file(file_path):
    """Python 파일 업데이트"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        new_content, changed = update_content(content)
        
        if changed:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"✅ Updated: {os.path.relpath(file_path, PROJECT_ROOT)}")
            return True
        return False
    except Exception as e:
        print(f"❌ Error: {file_path}: {e}")
        return False

def update_jupyter_file(file_path):
    """Jupyter 노트북 업데이트"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            notebook = json.load(f)
        
        changed = False
        for cell in notebook.get('cells', []):
            if cell.get('cell_type') == 'code':
                source = cell.get('source', [])
                new_source = []
                
                for line in source:
                    new_line, line_changed = update_content(line)
                    new_source.append(new_line)
                    if line_changed:
                        changed = True
                
                cell['source'] = new_source
        
        if changed:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(notebook, f, ensure_ascii=False, indent=1)
            print(f"✅ Updated: {os.path.relpath(file_path, PROJECT_ROOT)}")
            return True
        return False
    except Exception as e:
        print(f"❌ Error: {file_path}: {e}")
        return False

def main():
    print("="*70)
    print("경로 업데이트 시작...")
    print(f"프로젝트 루트: {PROJECT_ROOT}")
    print("="*70 + "\n")
    
    updated_count = 0
    total_count = 0
    
    code_dir = os.path.join(PROJECT_ROOT, 'code')
    
    for root, dirs, files in os.walk(code_dir):
        for file in files:
            file_path = os.path.join(root, file)
            
            if file.endswith('.py'):
                total_count += 1
                if update_python_file(file_path):
                    updated_count += 1
            elif file.endswith('.ipynb'):
                total_count += 1
                if update_jupyter_file(file_path):
                    updated_count += 1
    
    print(f"\n{'='*70}")
    print(f"총 {total_count}개 파일 중 {updated_count}개 파일 업데이트 완료!")
    print(f"{'='*70}")
    
    print("\n주요 변경사항:")
    print("  - code/*.png → outputs/*.png")
    print("  - code/*.html → outputs/*.html")
    print("  - 루트/final_review.plk → data/final_review.plk")
    print("  - 루트/product_ingredients.csv → data/product_ingredients.csv")

if __name__ == "__main__":
    main()
