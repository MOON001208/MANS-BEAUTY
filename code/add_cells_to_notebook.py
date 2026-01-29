
import json
import os

notebook_path = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\Gemini_Keywords_Topic_Modeling.ipynb'

# Define the new cells to be added
new_cells = [
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "## 3. 페르소나 재정의 및 키워드 분석\n",
            "기존 페르소나 분류를 기반으로, 리뷰 내용에 '선물' 관련 키워드가 포함된 경우 'User'에서 'Gifter'로 재분류합니다.\n",
            "그 후, 각 페르소나별로 자주 등장하는 핵심 키워드를 분석하여 시각화합니다."
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# 1. 페르소나 업데이트 로직\n",
            "print(\"페르소나 업데이트 중...\")\n",
            "\n",
            "# 선물하기 키워드 정의\n",
            "gift_keywords = ['남친', '남자친구', '남편', '신랑', '아빠', '아버지', '오빠', '동생', '선물']\n",
            "\n",
            "# is_gifter 판별 함수\n",
            "def is_gifter(text):\n",
            "    text = str(text)\n",
            "    return any(keyword in text for keyword in gift_keywords)\n",
            "\n",
            "# gemini_normalized 컬럼 사용 (없으면 리뷰내용_정제 사용)\n",
            "text_col = 'gemini_normalized' if 'gemini_normalized' in df.columns else '리뷰내용_정제'\n",
            "\n",
            "# is_gifter 컬럼 생성 및 업데이트\n",
            "df['is_gifter_temp'] = df[text_col].apply(is_gifter)\n",
            "\n",
            "print(\"업데이트 전 페르소나 분포:\")\n",
            "print(df['Persona'].value_counts())\n",
            "\n",
            "# 로직 적용: is_gifter가 True이고 Persona가 'User'인 경우 -> 'Gifter'로 변경\n",
            "condition = (df['is_gifter_temp'] == True) & (df['Persona'] == 'User')\n",
            "update_count = condition.sum()\n",
            "df.loc[condition, 'Persona'] = 'Gifter'\n",
            "\n",
            "print(f\"\\nUpdated {update_count} rows from 'User' to 'Gifter'.\")\n",
            "print(\"업데이트 후 페르소나 분포:\")\n",
            "print(df['Persona'].value_counts())\n",
            "\n",
            "# 임시 컬럼 제거\n",
            "df.drop(columns=['is_gifter_temp'], inplace=True)"
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# 2. 페르소나별 키워드 시각화 (2x2 Grid)\n",
            "\n",
            "personas = ['Gifter', 'Newbie', 'Loyalist', 'User']\n",
            "\n",
            "# 페르소나별 제외할 키워드 (각 페르소나를 정의하는 단어 자체는 제외하여 연관어만 분석)\n",
            "exclusion_map = {\n",
            "    'Gifter': gift_keywords + ['구매', '제품', '사용', '생각'],\n",
            "    'Newbie': ['입문', '초보', '처음', '모르다', '구매', '제품', '사용'],\n",
            "    'Loyalist': ['재구매', '정착', '계속', '항상', '몇통', '구매', '제품', '사용'],\n",
            "    'User': ['구매', '제품', '사용', '생각', '정도', '느낌', '사람']\n",
            "}\n",
            "\n",
            "# Plot 설정\n",
            "fig, axes = plt.subplots(2, 2, figsize=(20, 16))\n",
            "axes = axes.flatten()\n",
            "\n",
            "print(\"\\n--- 페르소나별 연관 키워드 분석 ---\")\n",
            "\n",
            "for idx, persona in enumerate(personas):\n",
            "    subset = df[df['Persona'] == persona]\n",
            "    exclude_words = exclusion_map.get(persona, [])\n",
            "    \n",
            "    all_keywords = []\n",
            "    for keywords in subset['gemini_keywords']:\n",
            "        if isinstance(keywords, list):\n",
            "            # 키워드 필터링: 제외어 목록에 없고, 1글자 초과인 경우\n",
            "            clean_k = [k for k in keywords if k not in exclude_words and len(k) > 1]\n",
            "            all_keywords.extend(clean_k)\n",
            "    \n",
            "    # 빈도 분석\n",
            "    count_data = Counter(all_keywords).most_common(15)\n",
            "    viz_df = pd.DataFrame(count_data, columns=['Keyword', 'Frequency'])\n",
            "    \n",
            "    # 시각화\n",
            "    ax = axes[idx]\n",
            "    if not viz_df.empty:\n",
            "        sns.barplot(x='Frequency', y='Keyword', data=viz_df, ax=ax, palette='viridis')\n",
            "        ax.set_title(f'Top 15 Keywords for \"{persona}\" (n={len(subset)})', fontsize=15, fontweight='bold')\n",
            "        ax.set_xlabel('Frequency')\n",
            "        ax.set_ylabel('')\n",
            "    else:\n",
            "        ax.text(0.5, 0.5, 'Not enough data', ha='center')\n",
            "        \n",
            "plt.tight_layout()\n",
            "plt.show()"
        ]
    }
]

def add_cells():
    try:
        with open(notebook_path, 'r', encoding='utf-8') as f:
            notebook = json.load(f)
        
        # Check if cells already exist to avoid duplication (simple check by source content)
        existing_sources = [cell.get('source', []) for cell in notebook['cells']]
        
        cells_to_append = []
        for new_cell in new_cells:
            # Flatten source list for comparison
            new_source_str = "".join(new_cell['source'])
            is_duplicate = False
            for existing_source in existing_sources:
                existing_source_str = "".join(existing_source)
                if new_source_str.strip() in existing_source_str.strip():
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                cells_to_append.append(new_cell)
        
        if cells_to_append:
            # Find the position to insert (after cell 6, or at the end for simplicity)
            # Actually, let's insert after the last code cell (which was index 6 in the viewed file)
            # But appending to the end is safer.
            notebook['cells'].extend(cells_to_append)
            
            with open(notebook_path, 'w', encoding='utf-8') as f:
                json.dump(notebook, f, indent=4, ensure_ascii=False)
            print(f"Successfully added {len(cells_to_append)} cells to the notebook.")
        else:
            print("Cells already exist in the notebook.")
            
    except Exception as e:
        print(f"Error updating notebook: {e}")

if __name__ == "__main__":
    add_cells()
