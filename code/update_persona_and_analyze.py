
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
import os

# 시각화 설정 (한글 폰트)
plt.rc('font', family='Malgun Gothic')
plt.rcParams['axes.unicode_minus'] = False

def main():
    # 1. 데이터 로드
    base_path = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\data'
    file_path = os.path.join(base_path, 'review_keywords_gemini3.pkl')
    
    print(f"Loading data from {file_path}...")
    df = pd.read_pickle(file_path)
    
    # 2. 페르소나 업데이트 로직 적용
    print("Updating Persona logic...")
    
    # 선물하기 키워드 정의
    gift_keywords = ['남친', '남자친구', '남편', '신랑', '아빠', '아버지', '오빠', '동생', '선물']
    
    # is_gifter 판별 함수
    def is_gifter(text):
        text = str(text)
        return any(keyword in text for keyword in gift_keywords)
    
    # is_gifter 컬럼 생성 (임시)
    # gemini_normalized 컬럼 사용 (없으면 리뷰내용_정제 사용)
    text_col = 'gemini_normalized' if 'gemini_normalized' in df.columns else '리뷰내용_정제'
    df['is_gifter_temp'] = df[text_col].apply(is_gifter)
    
    # 업데이트 전 통계
    print("Before Update:")
    print(df['Persona'].value_counts())
    
    # 로직 적용: is_gifter가 True이고 Persona가 'User'인 경우 -> 'Gifter'로 변경
    condition = (df['is_gifter_temp'] == True) & (df['Persona'] == 'User')
    update_count = condition.sum()
    df.loc[condition, 'Persona'] = 'Gifter'
    
    print(f"\nUpdated {update_count} rows from 'User' to 'Gifter'.")
    
    # 업데이트 후 통계
    print("After Update:")
    print(df['Persona'].value_counts())
    
    # 임시 컬럼 제거
    df.drop(columns=['is_gifter_temp'], inplace=True)
    
    # 3. 4가지 페르소나별 연관 키워드 분석 및 시각화
    personas = ['Gifter', 'Newbie', 'Loyalist', 'User']
    
    # 페르소나별 제외할 키워드 (각 페르소나를 정의하는 단어 자체는 제외하여 연관어만 분석)
    exclusion_map = {
        'Gifter': gift_keywords + ['구매', '제품', '사용', '생각'],
        'Newbie': ['입문', '초보', '처음', '모르다', '구매', '제품', '사용'],
        'Loyalist': ['재구매', '정착', '계속', '항상', '몇통', '구매', '제품', '사용'],
        'User': ['구매', '제품', '사용', '생각', '정도', '느낌', '사람']
    }
    
    # Plot 설정 (2x2)
    fig, axes = plt.subplots(2, 2, figsize=(20, 16))
    axes = axes.flatten()
    
    print("\n--- Analyzing Keywords by Persona ---")
    
    for idx, persona in enumerate(personas):
        subset = df[df['Persona'] == persona]
        exclude_words = exclusion_map.get(persona, [])
        
        all_keywords = []
        for keywords in subset['gemini_keywords']:
            if isinstance(keywords, list):
                # 키워드 필터링: 제외어 목록에 없고, 1글자 초과인 경우
                clean_k = [k for k in keywords if k not in exclude_words and len(k) > 1]
                all_keywords.extend(clean_k)
        
        # 빈도 분석
        count_data = Counter(all_keywords).most_common(15)
        viz_df = pd.DataFrame(count_data, columns=['Keyword', 'Frequency'])
        
        # 시각화
        ax = axes[idx]
        if not viz_df.empty:
            sns.barplot(x='Frequency', y='Keyword', data=viz_df, ax=ax, palette='viridis')
            ax.set_title(f'Top 15 Keywords for "{persona}" (n={len(subset)})', fontsize=15, fontweight='bold')
            ax.set_xlabel('Frequency')
            ax.set_ylabel('')
        else:
            ax.text(0.5, 0.5, 'Not enough data', ha='center')
            
    plt.tight_layout()
    save_img_path = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\persona_keywords_analysis.png'
    plt.savefig(save_img_path)
    print(f"\nExample visualization saved to: {save_img_path}")
    
    # 4. 결과 저장
    df.to_pickle(file_path)
    print(f"Updated DataFrame saved to: {file_path}")

if __name__ == "__main__":
    main()
