import json

notebook_path = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\Gemini_Keywords_Topic_Modeling.ipynb'

# Robust code that tries pyLDAvis but falls back to Matplotlib
robust_lda_code = [
    "# 3. LDA 토픽 모델링 시각화\n",
    "try:\n",
    "    import pyLDAvis\n",
    "    import pyLDAvis.sklearn\n",
    "    print(\"pyLDAvis 라이브러리를 사용하여 인터랙티브 시각화를 시도합니다...\")\n",
    "    \n",
    "    # 데이터 준비\n",
    "    def process_keywords_str(keywords):\n",
    "        if isinstance(keywords, list):\n",
    "            return ' '.join([k for k in keywords if len(k)>1])\n",
    "        return \"\"\n",
    "\n",
    "    df['processed_text_lda'] = df['gemini_keywords'].apply(process_keywords_str)\n",
    "    df_valid = df[df['processed_text_lda'] != \"\"]\n",
    "\n",
    "    # 벡터화 및 모델링\n",
    "    vectorizer_lda = CountVectorizer(min_df=10, max_df=0.9)\n",
    "    X_lda = vectorizer_lda.fit_transform(df_valid['processed_text_lda'])\n",
    "    \n",
    "    lda_model = LatentDirichletAllocation(n_components=5, learning_decay=0.7, random_state=42)\n",
    "    lda_model.fit(X_lda)\n",
    "    \n",
    "    # 시각화 실행\n",
    "    pyLDAvis.enable_notebook()\n",
    "    panel = pyLDAvis.sklearn.prepare(lda_model, X_lda, vectorizer_lda, mds='tsne')\n",
    "    display(panel)\n",
    "    \n",
    "except ImportError:\n",
    "    print(\"pyLDAvis 라이브러리 로드 실패. 정적 그래프로 대체합니다.\")\n",
    "    is_pyldavis_ok = False\n",
    "except Exception as e:\n",
    "    print(f\"시각화 중 오류 발생: {e}\\n정적 그래프로 토픽을 시각화합니다.\")\n",
    "    \n",
    "    # Fallback: Matplotlib Static Plot\n",
    "    feature_names = vectorizer_lda.get_feature_names_out()\n",
    "    \n",
    "    fig, axes = plt.subplots(1, 5, figsize=(20, 5), sharex=True)\n",
    "    axes = axes.flatten()\n",
    "    \n",
    "    for topic_idx, topic in enumerate(lda_model.components_):\n",
    "        top_features_ind = topic.argsort()[:-10 - 1:-1]\n",
    "        top_features = [feature_names[i] for i in top_features_ind]\n",
    "        weights = topic[top_features_ind]\n",
    "        \n",
    "        ax = axes[topic_idx]\n",
    "        ax.barh(top_features, weights, height=0.7)\n",
    "        ax.set_title(f'Topic {topic_idx + 1}', fontdict={'fontsize': 15})\n",
    "        ax.invert_yaxis()\n",
    "        ax.tick_params(axis='both', which='major', labelsize=10)\n",
    "        \n",
    "    plt.tight_layout()\n",
    "    plt.show()\n"
]

# Read Notebook
with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Find the last cell (Task 3) and replace it
# We search for "pyLDAvis" in the source
target_index = -1
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] == 'code':
        source_text = "".join(cell['source'])
        if "pyLDAvis" in source_text:
            target_index = i
            # Don't break immediately, we want the LAST one if there are duplicates
            # Actually, usually the new one is the last one.

if target_index != -1:
    nb['cells'][target_index]['source'] = robust_lda_code
    print(f"Replaced cell {target_index} with robust visualization code.")
else:
    print("Target cell not found.")

# Write back
with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=4, ensure_ascii=False)
