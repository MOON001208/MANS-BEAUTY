import json
import pandas as pd

notebook_path = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\Gemini_Keywords_Topic_Modeling.ipynb'

# New code for Task 2
new_source_code = [
    "# 2. 남성 실사용자(선물X) 제품별 만족 이유(키워드) 분석\n",
    "df_men = df[~df['is_gifter']]\n",
    "\n",
    "# 리뷰 많은 상위 5개 제품 추출\n",
    "top_reviewed_products = df_men['상품이름'].value_counts().head(5).index.tolist()\n",
    "\n",
    "print(\"--- 남성 실사용자 주요 제품별 만족 키워드 TOP 5 ---\")\n",
    "for product in top_reviewed_products:\n",
    "    product_reviews = df_men[df_men['상품이름'] == product]\n",
    "    \n",
    "    # 키워드 모으기\n",
    "    all_keywords = []\n",
    "    for keywords in product_reviews['gemini_keywords']:\n",
    "        if isinstance(keywords, list):\n",
    "            # 불용어 처리 (필요시 추가)\n",
    "            filtered = [k for k in keywords if len(k) > 1 and k not in ['사용', '제품', '구매', '생각']]\n",
    "            all_keywords.extend(filtered)\n",
    "            \n",
    "    # 빈도 계산\n",
    "    top_k = Counter(all_keywords).most_common(5)\n",
    "    print(f\"\\n[제품명: {product}]\")\n",
    "    for k, freq in top_k:\n",
    "        print(f\" - {k}: {freq}회\")\n"
]

# Read Notebook
with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Find the cell index for Task 2 (It should be the 3rd to last cell currently)
# We look for the cell containing "# 2. 남성 실사용자(선물X) 제품 만족도 분석"
target_index = -1
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] == 'code':
        source_text = "".join(cell['source'])
        if "# 2. 남성 실사용자(선물X) 제품 만족도 분석" in source_text:
            target_index = i
            break

if target_index != -1:
    nb['cells'][target_index]['source'] = new_source_code
    print(f"Updated cell {target_index} with new keyword analysis logic.")
else:
    print("Could not find the target cell to update.")

# Write back
with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=4, ensure_ascii=False)
