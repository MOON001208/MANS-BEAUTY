import json
import os

notebook_path = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\Gemini_Keywords_Topic_Modeling.ipynb'

# New cells to append
new_cells = [
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "## 5. 심층 분석: 선물 수요, 만족도, LDA 시각화"
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# 1. 여성이 남성에게 선물하는 경우 분석\n",
            "gift_keywords = ['남친', '남자친구', '남편', '신랑', '아빠', '아버지', '오빠', '동생', '선물']\n",
            "\n",
            "def is_gifter(text):\n",
            "    text = str(text)\n",
            "    return any(keyword in text for keyword in gift_keywords)\n",
            "\n",
            "df['is_gifter'] = df['gemini_normalized'].apply(is_gifter)\n",
            "df_gifter = df[df['is_gifter']]\n",
            "\n",
            "# 선물 관련 키워드 추출 (검색 키워드 제외)\n",
            "gifter_words = []\n",
            "for keywords in df_gifter['gemini_keywords']:\n",
            "    if isinstance(keywords, list):\n",
            "        cleaned_keywords = [k for k in keywords if k not in gift_keywords and len(k) > 1]\n",
            "        gifter_words.extend(cleaned_keywords)\n",
            "\n",
            "gifter_word_counts = Counter(gifter_words).most_common(20)\n",
            "df_gifter_freq = pd.DataFrame(gifter_word_counts, columns=['Keyword', 'Frequency'])\n",
            "\n",
            "plt.figure(figsize=(15, 6))\n",
            "sns.barplot(x='Frequency', y='Keyword', data=df_gifter_freq, palette='viridis')\n",
            "plt.title('여성이 남성에게 선물 시 주요 연관 키워드', fontsize=15)\n",
            "plt.xlabel('빈도수')\n",
            "plt.show()"
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# 2. 남성 실사용자(선물X) 제품 만족도 분석\n",
            "df_men = df[~df['is_gifter']]\n",
            "\n",
            "# 제품별 평점 평균 계산\n",
            "product_stats = df_men.groupby('상품이름').agg({\n",
            "    '별점': 'mean',\n",
            "    '리뷰내용_정제': 'count'\n",
            "}).reset_index()\n",
            "\n",
            "product_stats.rename(columns={'리뷰내용_정제': 'Review_Count', '별점': 'Avg_Rating'}, inplace=True)\n",
            "\n",
            "# 리뷰 10개 이상인 제품만 필터링하여 상위 15개 제품 시각화\n",
            "top_products = product_stats[product_stats['Review_Count'] >= 10].sort_values(by='Avg_Rating', ascending=False).head(15)\n",
            "\n",
            "plt.figure(figsize=(10, 8))\n",
            "sns.barplot(x='Avg_Rating', y='상품이름', data=top_products, palette='magma')\n",
            "plt.title('남성 실사용자 만족도 상위 제품 (10개 이상 리뷰)', fontsize=15)\n",
            "plt.xlim(4.0, 5.0) # 평점 차이 부각\n",
            "plt.xlabel('평균 별점')\n",
            "plt.show()\n",
            "\n",
            "print(\"상위 제품 평점:\\n\", top_products[['상품이름', 'Avg_Rating', 'Review_Count']])"
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# 3. LDA 인터랙티브 시각화 (pyLDAvis)\n",
            "!pip install pyLDAvis\n",
            "import pyLDAvis\n",
            "import pyLDAvis.sklearn\n",
            "\n",
            "# 데이터 준비: 키워드 리스트를 문자열로 변환\n",
            "def process_keywords_str(keywords):\n",
            "    if isinstance(keywords, list):\n",
            "        return ' '.join([k for k in keywords if len(k)>1])\n",
            "    return \"\"\n",
            "\n",
            "df['processed_text_lda'] = df['gemini_keywords'].apply(process_keywords_str)\n",
            "df_valid = df[df['processed_text_lda'] != \"\"]\n",
            "\n",
            "vectorizer_lda = CountVectorizer(min_df=10, max_df=0.9)\n",
            "X_lda = vectorizer_lda.fit_transform(df_valid['processed_text_lda'])\n",
            "\n",
            "# LDA 모델 적합 (토픽 5개 설정)\n",
            "lda_model = LatentDirichletAllocation(n_components=5, learning_decay=0.7, random_state=42)\n",
            "lda_model.fit(X_lda)\n",
            "\n",
            "# 시각화\n",
            "pyLDAvis.enable_notebook()\n",
            "panel = pyLDAvis.sklearn.prepare(lda_model, X_lda, vectorizer_lda, mds='tsne')\n",
            "panel"
        ]
    }
]

# Read Existing Notebook
with open(notebook_path, 'r', encoding='utf-8') as f:
    notebook_data = json.load(f)

# Append cells (removing the last empty one if it exists or just appending)
# Check last cell
if notebook_data['cells'][-1]['source'] == []:
    notebook_data['cells'].pop() # Remove empty cell

notebook_data['cells'].extend(new_cells)

# Write Back
with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(notebook_data, f, indent=4, ensure_ascii=False)

print("Successfully added analysis cells to notebook.")
