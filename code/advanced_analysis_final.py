
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
import pyLDAvis
import os

# Set Korean Font
plt.rc('font', family='Malgun Gothic')
plt.rcParams['axes.unicode_minus'] = False

# 1. Load Data
file_path = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\data\review_keywords_gemini3.pkl'
print(f"Loading data from {file_path}...")
df = pd.read_pickle(file_path)

# Ensure text columns are strings
df['리뷰내용_정제'] = df['리뷰내용_정제'].astype(str)

# --- Task 1: Words related to Women Gifting to Men ---
print("\n--- Task 1: Analysis of reviews by women gifting to men ---")
gift_keywords = ['남친', '남자친구', '남편', '신랑', '아빠', '아버지', '오빠', '동생', '선물']

# Function to check if any keyword is in text
def is_gifter(text):
    return any(keyword in text for keyword in gift_keywords)

df['is_gifter'] = df['리뷰내용_정제'].apply(is_gifter)
df_gifter = df[df['is_gifter']]
print(f"Number of gifter reviews found: {len(df_gifter)}")

# Extract keywords from gifter reviews
gifter_words = []
for keywords in df_gifter['gemini_keywords']:
    if isinstance(keywords, list):
        # Exclude the search keywords themselves to filter out obvious ones
        cleaned_keywords = [k for k in keywords if k not in gift_keywords and len(k) > 1]
        gifter_words.extend(cleaned_keywords)

# Count frequencies
gifter_word_counts = Counter(gifter_words).most_common(20)
df_gifter_freq = pd.DataFrame(gifter_word_counts, columns=['Keyword', 'Frequency'])

# Visualize Task 1
plt.figure(figsize=(12, 6))
sns.barplot(x='Frequency', y='Keyword', data=df_gifter_freq, palette='viridis')
plt.title('Top 20 Related Words for "Women Gifting to Men"', fontsize=15)
plt.savefig(r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\gifter_words_analysis.png')
print("Saved Task 1 visualization to gifter_words_analysis.png")


# --- Task 2: Men's Satisfaction by Product (Keywords) ---
print("\n--- Task 2: Men's Satisfaction Keywords by Product ---")
# Assume non-gifters are men/users
df_men = df[~df['is_gifter']]

# Get Top 5 Products by review count
top_products_list = df_men['상품이름'].value_counts().head(5).index.tolist()

print(f"Analyzing keywords for Top 5 Products: {top_products_list}")

# Data for visualization
viz_data = []

for product in top_products_list:
    prod_reviews = df_men[df_men['상품이름'] == product]
    
    keywords = []
    for k_list in prod_reviews['gemini_keywords']:
        if isinstance(k_list, list):
            # Filtering generic words
            keywords.extend([k for k in k_list if len(k) > 1 and k not in ['사용', '제품', '구매', '생각', '느낌', '정도', '사람']])
            
    top_k = Counter(keywords).most_common(10)
    print(f"\n[Product: {product}] Top Keywords:")
    for k, freq in top_k:
        print(f" - {k}: {freq}")
        
    # Keep data for top 1 product for visualization
    if product == top_products_list[0]:
        df_prod_freq = pd.DataFrame(top_k, columns=['Keyword', 'Frequency'])
        plt.figure(figsize=(12, 6))
        sns.barplot(x='Frequency', y='Keyword', data=df_prod_freq, palette='Blues_r')
        plt.title(f'Satisfaction Keywords for #1 Product: {product}', fontsize=15)
        plt.savefig(r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\men_satisfaction_keywords.png')
        print(f"Saved keyword chart for {product} to men_satisfaction_keywords.png")


# --- Task 3: LDA Analysis with Interactive Visualization ---
print("\n--- Task 3: LDA Interactive Visualization ---")

def process_keywords(keywords):
    if isinstance(keywords, list):
        return ' '.join([k for k in keywords if len(k)>1])
    return ""

df['processed_text_lda'] = df['gemini_keywords'].apply(process_keywords)
df_valid = df[df['processed_text_lda'].str.strip() != ""]

# Vectorize
print("Vectorizing text...")
vectorizer = CountVectorizer(min_df=10, max_df=0.9)
X = vectorizer.fit_transform(df_valid['processed_text_lda'])

# LDA Model
n_topics = 5 
print(f"Training LDA with {n_topics} topics...")
lda_model = LatentDirichletAllocation(n_components=n_topics, learning_decay=0.7, random_state=42)
lda_model.fit(X)

# PyLDAvis or Fallback
print("Generating LDA visualization...")
try:
    # Try dynamic import likely to fail if not installed properly, but worth a try in-block
    import pyLDAvis.sklearn
    pyLDAvis.enable_notebook()
    panel = pyLDAvis.sklearn.prepare(lda_model, X, vectorizer, mds='tsne')
    output_html = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\lda_visualization.html'
    pyLDAvis.save_html(panel, output_html)
    print(f"Saved interactive LDA visualization to {output_html}")
except Exception as e:
    print(f"Could not generate interactive pyLDAvis: {e}")
    print("Generating static topic visualization instead...")
    
    feature_names = vectorizer.get_feature_names_out()
    
    n_top_words = 10
    fig, axes = plt.subplots(1, 5, figsize=(20, 10), sharex=True)
    axes = axes.flatten()
    
    for topic_idx, topic in enumerate(lda_model.components_):
        top_features_ind = topic.argsort()[:-n_top_words - 1:-1]
        top_features = [feature_names[i] for i in top_features_ind]
        weights = topic[top_features_ind]
        
        ax = axes[topic_idx]
        ax.barh(top_features, weights, height=0.7)
        ax.set_title(f'Topic {topic_idx +1}', fontdict={'fontsize': 20})
        ax.invert_yaxis()
        ax.tick_params(axis='both', which='major', labelsize=10)
        for i in 'top right left'.split():
            ax.spines[i].set_visible(False)
    
    plt.subplots_adjust(top=0.90, bottom=0.05, wspace=0.90, hspace=0.3)
    static_output = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\lda_topics_static.png'
    plt.savefig(static_output)
    print(f"Saved static LDA topic plot to {static_output}")

print("Analysis Complete.")
