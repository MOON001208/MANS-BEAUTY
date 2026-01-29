
# 2. 페르소나별 키워드 시각화 (2x2 Grid) - 키워드별 색상 통일

import seaborn as sns
import matplotlib.pyplot as plt
from collections import Counter
import pandas as pd

personas = ['Gifter', 'Newbie', 'Loyalist', 'User']

# 페르소나별 제외할 키워드 (각 페르소나를 정의하는 단어 자체는 제외하여 연관어만 분석)
exclusion_map = {
    'Gifter': gift_keywords + ['구매', '제품', '사용', '생각'],
    'Newbie': ['입문', '초보', '처음', '모르다', '구매', '제품', '사용'],
    'Loyalist': ['재구매', '정착', '계속', '항상', '몇통', '구매', '제품', '사용'],
    'User': ['구매', '제품', '사용', '생각', '정도', '느낌', '사람']
}

# 1. 모든 페르소나의 상위 키워드 데이터를 먼저 수집하여 유니크 키워드 리스트 생성
all_plot_data = {}
all_unique_keywords = set()

print("데이터 집계 중...")
for persona in personas:
    subset = df[df['Persona'] == persona]
    exclude_words = exclusion_map.get(persona, [])
    
    all_keywords = []
    # gemini_keywords 컬럼 사용
    for keywords in subset['gemini_keywords']:
        if isinstance(keywords, list):
            # 키워드 필터링: 제외어 목록에 없고, 1글자 초과인 경우
            clean_k = [k for k in keywords if k not in exclude_words and len(k) > 1]
            all_keywords.extend(clean_k)
            
    # 빈도 분석
    count_data = Counter(all_keywords).most_common(15)
    viz_df = pd.DataFrame(count_data, columns=['Keyword', 'Frequency'])
    all_plot_data[persona] = viz_df
    all_unique_keywords.update(viz_df['Keyword'].tolist())

# 2. 유니크 키워드에 대한 색상 맵 생성 (일관된 색상 부여)
unique_keywords_list = sorted(list(all_unique_keywords))
# husl 팔레트를 사용하여 키워드 개수만큼의 유니크한 색상 생성
palette = sns.color_palette("husl", len(unique_keywords_list))
keyword_color_map = dict(zip(unique_keywords_list, palette))

# 3. 시각화
fig, axes = plt.subplots(2, 2, figsize=(20, 16))
axes = axes.flatten()

print("\\n--- 페르소나별 연관 키워드 분석 (키워드별 색상 통일) ---")

for idx, persona in enumerate(personas):
    viz_df = all_plot_data[persona]
    ax = axes[idx]
    
    if not viz_df.empty:
        # hue를 Keyword로 지정하고 palette에 매핑 딕셔너리 전달
        sns.barplot(x='Frequency', y='Keyword', data=viz_df, ax=ax, 
                    hue='Keyword', palette=keyword_color_map, dodge=False, legend=False)
        ax.set_title(f'Top 15 Keywords for "{persona}" (n={len(df[df["Persona"]==persona])})', fontsize=15, fontweight='bold')
        ax.set_xlabel('Frequency')
        ax.set_ylabel('')
    else:
        ax.text(0.5, 0.5, 'Not enough data', ha='center')
        
plt.tight_layout()
plt.show()
plt.savefig('persona_keywords_analysis_consistent_colors.png')
print("시각화 완료 및 저장됨: persona_keywords_analysis_consistent_colors.png")
