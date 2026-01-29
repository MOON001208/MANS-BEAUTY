
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from collections import Counter
import warnings

# 한글 폰트 설정
plt.rc('font', family='Malgun Gothic')
plt.rcParams['axes.unicode_minus'] = False
warnings.filterwarnings('ignore')

# 1. 데이터 로드
file_path = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\data\review_keywords_gemini3.pkl'
print(f"Loading data from {file_path}...")
try:
    df = pd.read_pickle(file_path)
    print("Data loaded successfully.")
except Exception as e:
    print(f"Error loading data: {e}")
    exit()

# 2. 페르소나 정의 (Notebook 로직 복원)
gift_keywords = ['남친', '남자친구', '남편', '신랑', '아빠', '아버지', '오빠', '동생', '선물']

def is_gifter(text):
    text = str(text)
    return any(keyword in text for keyword in gift_keywords)

# 텍스트 컬럼 확인
text_col = 'gemini_normalized' if 'gemini_normalized' in df.columns else '리뷰내용_정제'
print(f"Using text column: {text_col}")

# Persona 컬럼이 없거나 갱신이 필요할 수 있으므로 다시 계산
if 'Persona' not in df.columns:
    df['Persona'] = 'User' # 기본값

# Gifter 식별
# 기존 User인 경우에만 체크 (이미 다른 페르소나인 경우 유지할지 여부는 로직에 따라 다르지만, 
# 여기서는 기프트 키워드가 있으면 무조건 Gifter로 보거나, 기존 로직 따름.
# notebook 로직: condition = (df['is_gifter_temp'] == True) & (df['Persona'] == 'User')
# 간단히 구현:
is_gift = df[text_col].apply(is_gifter)
# 기존 Persona가 'User'이고 선물 키워드가 있으면 'Gifter'로 변경
# (단, 데이터프레임에 이미 Newbie/Loyalist 등이 마킹되어 있다고 가정)
# 만약 Persona 컬럼이 초기화 상태라면 Newbie/Loyalist 로직도 필요하지만, 
# 여기서는 pickle에 이미 있을 수도 있고, Gifter만 업데이트해도 시각화 테스트엔 충분함.
# 안전하게: Persona가 User인 행 중에서만 Gifter로 업데이트
df.loc[(df['Persona'] == 'User') & is_gift, 'Persona'] = 'Gifter'

print("Persona counts:")
print(df['Persona'].value_counts())

# 3. 시각화 (키워드별 색상 통일 버전)
personas = ['Gifter', 'Newbie', 'Loyalist', 'User']

# 페르소나별 제외할 키워드
exclusion_map = {
    'Gifter': gift_keywords + ['구매', '제품', '사용', '생각'],
    'Newbie': ['입문', '초보', '처음', '모르다', '구매', '제품', '사용'],
    'Loyalist': ['재구매', '정착', '계속', '항상', '몇통', '구매', '제품', '사용'],
    'User': ['구매', '제품', '사용', '생각', '정도', '느낌', '사람']
}

# 데이터 집계
all_plot_data = {}
all_unique_keywords = set()

print("Analyzing keywords...")
for persona in personas:
    subset = df[df['Persona'] == persona]
    exclude_words = exclusion_map.get(persona, [])
    
    all_keywords = []
    # gemini_keywords 컬럼 사용
    if 'gemini_keywords' in df.columns:
        target_col = 'gemini_keywords'
    else:
        # gemini_normalized가 리스트가 아니라면 토크나이징 필요할 수 있음. 
        # 여기서는 pickle에 이미 리스트로 있다고 가정 (gemini output)
        target_col = text_col 
    
    for keywords in subset[target_col]:
        if isinstance(keywords, list):
            clean_k = [k for k in keywords if k not in exclude_words and len(k) > 1]
            all_keywords.extend(clean_k)
            
    # 빈도 분석
    count_data = Counter(all_keywords).most_common(15)
    viz_df = pd.DataFrame(count_data, columns=['Keyword', 'Frequency'])
    all_plot_data[persona] = viz_df
    all_unique_keywords.update(viz_df['Keyword'].tolist())

# 색상 맵 생성
unique_keywords_list = sorted(list(all_unique_keywords))
if not unique_keywords_list:
    print("No keywords found to plot.")
    exit()

palette = sns.color_palette("husl", len(unique_keywords_list))
keyword_color_map = dict(zip(unique_keywords_list, palette))

# 시각화 생성
fig, axes = plt.subplots(2, 2, figsize=(20, 16))
axes = axes.flatten()

print(f"Generating plot with {len(unique_keywords_list)} unique keywords...")

for idx, persona in enumerate(personas):
    viz_df = all_plot_data[persona]
    ax = axes[idx]
    
    if not viz_df.empty:
        sns.barplot(x='Frequency', y='Keyword', data=viz_df, ax=ax, 
                    hue='Keyword', palette=keyword_color_map, dodge=False, legend=False)
        ax.set_title(f'Top 15 Keywords for "{persona}" (n={len(df[df["Persona"]==persona])})', fontsize=15, fontweight='bold')
        ax.set_xlabel('Frequency')
        ax.set_ylabel('')
    else:
        ax.text(0.5, 0.5, 'Not enough data', ha='center')
        
plt.tight_layout()
output_path = 'persona_keywords_analysis_consistent_colors.png'
plt.savefig(output_path)
print(f"Visualization saved to {output_path}")
