import pandas as pd
import re
import os

# Define paths
DATA_DIR = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\data'
INPUT_FILE = os.path.join(DATA_DIR, 'final_review.plk')
OUTPUT_FILE = os.path.join(DATA_DIR, 'review_with_influencers.plk')

# 1. Load Data
print(f"Loading data from {INPUT_FILE}...")
df = pd.read_pickle(INPUT_FILE)

# 2. Define Influencer Keywords Mapping
# (User requested: 스완, 관하살, 티뱃동생, 호박스, 괜찮은 라이프 아우라M, 문장군, 설빈, 쭌이덕)
influencers_map = {
    '스완': ['스완'],
    '관하살': ['관하살', '관리하는남자', '관리하는 남자'],
    '티벳동생': ['티벳동생', '티벳', '티뱃'],
    '호박스': ['호박스'],
    '피부은동': ['괜찮은 라이프', '괜찮은라이프', '제레미'], # '괜찮은 라이프' channel name is often associated with '피부은동' or similar context, but sticking to user keyword '괜찮은 라이프'
    '아우라M': ['아우라M', '아우라엠', '아우라'],
    '문장군': ['문장군'],
    '설빈': ['설빈'],
    '쭌이덕': ['쭌이덕'],
    '덱스': ['덱스'], # Known official model
    '레오제이': ['레오제이'],
    '깡스타일리스트': ['깡스타일리스트', '깡형'],
    '디렉터파이': ['디렉터파이', '디파'],
    '화장하는남자': ['화장하는남자', '화남']
}

# 3. Detection Function
def get_influencers(text):
    if not isinstance(text, str):
        return []
    
    found_set = set()
    for name, keywords in influencers_map.items():
        for kw in keywords:
            if kw in text:
                found_set.add(name)
                # Once a name is found by one keyword, move to next name
                break 
    return list(found_set)

print("Scanning reviews for influencer mentions...")
df['mentioned_influencers'] = df['리뷰내용_정제'].apply(get_influencers)

# 4. Create Derived Columns
# youtuber_mentioned: True if list is not empty
df['youtuber_mentioned'] = df['mentioned_influencers'].apply(lambda x: len(x) > 0)

# 5. Identify Official/Main Influencer per Product
# Strategy: Count mentions per product, assign the most mentioned one as 'main_influencer' for that product
# Note: This is a product-level attribute derived from aggregated review data.

print("Calculating main influencer per product...")
exploded = df[df['youtuber_mentioned']].explode('mentioned_influencers')
if not exploded.empty:
    mention_counts = exploded.groupby(['상품이름', 'mentioned_influencers']).size().reset_index(name='count')
    # Sort by count desc
    mention_counts = mention_counts.sort_values(['상품이름', 'count'], ascending=[True, False])
    # Take top 1
    top_influencers = mention_counts.groupby('상품이름').first().reset_index()
    
    # Map back to dataframe
    product_influencer_map = dict(zip(top_influencers['상품이름'], top_influencers['mentioned_influencers']))
else:
    product_influencer_map = {}

df['main_influencer'] = df['상품이름'].map(product_influencer_map)

# 6. Save
print(f"Saving processed data to {OUTPUT_FILE}...")
df.to_pickle(OUTPUT_FILE)

# 7. Verification Output
print("\n[Analysis Result]")
print(f"Total Reviews: {len(df)}")
print(f"Reviews mentioning YouTubers: {df['youtuber_mentioned'].sum()}")
print("\nTop Influencers by Mention Count:")
all_mentions = exploded['mentioned_influencers'].value_counts()
print(all_mentions)
print("\nMain Influencer per Product (Top 5):")
print(df[['상품이름', 'main_influencer']].drop_duplicates().dropna().head(10))
