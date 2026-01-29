import pandas as pd
import numpy as np
from kiwipiepy import Kiwi
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.decomposition import NMF
import re
from collections import Counter

# 1. Load Data
file_path = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\data\review_attributes_gemini.plk'
print(f"Loading data from {file_path}...")
df = pd.read_pickle(file_path)

# Ensure text column is string
df['gemini_normalized'] = df['gemini_normalized'].astype(str)

# 2. Preprocessing with Kiwi
print("Initializing Kiwi for morphological analysis...")
kiwi = Kiwi()

def extract_keywords(text):
    result = kiwi.analyze(text)
    keywords = []
    for token, pos, _, _ in result[0][0]:
        # Extract Nouns (NNG, NNP) and Adjectives (VA) and Verbs (VV)
        if pos.startswith('NN') or pos.startswith('VA') or pos.startswith('VV'):
             keywords.append(token)
    return keywords

print("Extracting keywords (this may take a moment)...")
# Sampling for speed if needed, but 17k is fine.
# Let's clean the text first simply
df['clean_text'] = df['gemini_normalized'].apply(lambda x: re.sub(r'[^가-힣\s]', '', x))

# Batch processing might be faster but simple apply is easier to write
# To speed up, we can use kiwi.analyze in parallel or just iterate.
# For 17k, single thread is likely ~10-20 seconds.
try:
    # Use simple list comprehension for speed
    texts = df['clean_text'].tolist()
    # kiwi.analyze returns an iterator
    tokens_list = []
    for res in kiwi.analyze(texts):
        tokens = [token.form for token in res[0] if token.tag.startswith('NN') or token.tag.startswith('VA') or token.tag == 'XR'] # Nouns, Adjectives, Roots
        tokens_list.append(tokens)
    df['tokens'] = tokens_list
except Exception as e:
    print(f"Kiwi processing failed: {e}")
    # Fallback to split
    df['tokens'] = df['clean_text'].apply(lambda x: x.split())

# Join tokens for Vectorizer
df['processed_string'] = df['tokens'].apply(lambda x: ' '.join(x))

# Stopwords
stopwords = ['하다', '있다', '없다', '같다', '쓰다', '좋다', '너무', '정말', '진짜', '구매', '사용', '제품', '생각', '사람', '정도', '느낌', '바르다', '피부', '많이', '그냥', '아직', '완전']

# --- Analysis 1: Topic Modeling (NMF) ---
print("\n--- 1. Topic Modeling (NMF) ---")
n_topics = 5
vectorizer = TfidfVectorizer(max_features=1000, stop_words=stopwords, min_df=10)
tfidf = vectorizer.fit_transform(df['processed_string'])
nmf = NMF(n_components=n_topics, random_state=42)
nmf_topics = nmf.fit_transform(tfidf)

feature_names = vectorizer.get_feature_names_out()
for topic_idx, topic in enumerate(nmf.components_):
    top_features_ind = topic.argsort()[:-11:-1]
    top_features = [feature_names[i] for i in top_features_ind]
    print(f"Topic {topic_idx+1}: {', '.join(top_features)}")

# Assign dominant topic
df['topic'] = nmf_topics.argmax(axis=1)

# --- Analysis 2: Keyword Co-occurrence (Focus on '트러블', '선물') ---
print("\n--- 2. Keyword Co-occurrence ---")
target_keywords = ['트러블', '선물']

for target in target_keywords:
    print(f"\n[Keywords co-occurring with '{target}']")
    related_words = []
    for tokens in df['tokens']:
        if target in tokens:
            related_words.extend([t for t in tokens if t != target and t not in stopwords])
    
    common = Counter(related_words).most_common(10)
    print(common)

# --- Analysis 3: Aspect Analysis (Why Negative?) ---
print("\n--- 3. Aspect Based Severity Analysis (Negative Reviews) ---")
# Focus on reviews where 'attr_coverage' is low (<=2) if it exists
if 'attr_coverage' in df.columns:
    neg_coverage = df[df['attr_coverage'] <= 2]
    if not neg_coverage.empty:
        print(f"\n[Negative Coverage Reviews ({len(neg_coverage)} reviews)] Top Keywords:")
        neg_words = []
        for tokens in neg_coverage['tokens']:
            neg_words.extend([t for t in tokens if t not in stopwords])
        print(Counter(neg_words).most_common(10))
    else:
        print("No negative coverage reviews found.")

if 'attr_longevity' in df.columns:
    neg_long = df[df['attr_longevity'] <= 2]
    if not neg_long.empty:
        print(f"\n[Negative Longevity Reviews ({len(neg_long)} reviews)] Top Keywords:")
        neg_words = []
        for tokens in neg_long['tokens']:
            neg_words.extend([t for t in tokens if t not in stopwords])
        print(Counter(neg_words).most_common(10))

# --- Analysis 4: Persona Classification ---
print("\n--- 4. Persona Classification ---")
def classify_persona(text):
    text = str(text)
    if any(x in text for x in ['선물', '남친', '남편', '아빠', '오빠', '동생']):
        return 'Gifter'
    if any(x in text for x in ['처음', '입문', '모르다', '초보']):
        return 'Newbie'
    if any(x in text for x in ['재구매', '정착', '계속', '항상', '몇통']):
        return 'Loyalist'
    return 'User'

df['Persona'] = df['gemini_normalized'].apply(classify_persona)
print(df['Persona'].value_counts())

# Save results
output_path = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\data\gemini_analysis_results.csv'
print(f"\nSaving processed data with topics and personas to {output_path}")
df.to_csv(output_path, index=False)
