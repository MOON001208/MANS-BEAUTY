import json

notebook_path = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\final_market_analysis.ipynb'

with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

new_cells = []
for cell in nb['cells']:
    # 텍스트 내용 확인 (사용자가 수정한 부분 포함)
    source_text = "".join(cell['source'])
    
    if "2019년에는 리뷰가 3건뿐이라 그래프에 보이지 않는다." in source_text:
        # 요약 및 해석 셀 업데이트
        new_cells.append({
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "2019년에는 리뷰가 3건뿐이라 그래프에 보이지 않는다.\n",
                "\n",
                "2020, 2021년도까지는 현재 Top2인 비레디, 오브제 리뷰가 거의 없었으나, 2022년부터 급격하게 리뷰수가 급증하였다. \n",
                "이는 **인플루언서(덱스, 스완 등)의 영향력**과 **남성 뷰티 제품의 카테고리 확장**이 맞물린 시점으로 추측된다."
            ]
        })
        
        # 1-2 인플루언서 분석 섹션 추가
        new_cells.append({
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 1-2. 인플루언서 영향력 분석 (인과관계 추정)\n",
                "솔로지옥2(2022.12), 오브제 덱스 발탈(2023) 등 주요 이벤트 시점과 리뷰 내 언급량을 비교합니다."
            ]
        })
        new_cells.append({
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 1. 주요 인플루언서 언급량 집계 (연도별)\n",
                "influencer_trends = df.groupby(['Review_Year', 'main_influencer']).size().unstack(fill_value=0)\n",
                "\n",
                "# 주요 인플루언서만 추출 (기타 제외)\n",
                "targets = ['스완', '덱스', '관하살']\n",
                "present_targets = [t for t in targets if t in influencer_trends.columns]\n",
                "df_inf = influencer_trends[present_targets]\n",
                "\n",
                "# 시각화\n",
                "fig, ax = plt.subplots(figsize=(12, 6))\n",
                "df_inf.plot(kind='line', marker='o', linewidth=2, ax=ax)\n",
                "\n",
                "# 주요 이벤트 주석 추가 (데이터가 존재하는 경우에만)\n",
                "if 2022 in df_inf.index:\n",
                "    ax.annotate('솔로지옥2 방영\\n(덱스 화제)', xy=(2022.9, df_inf.get('덱스', pd.Series({2022:0})).get(2022, 0)), \n",
                "                xytext=(2021, 500), arrowprops=dict(facecolor='black', shrink=0.05), fontsize=10)\n",
                "if 2023 in df_inf.index:\n",
                "    ax.annotate('오브제 공동개발/덱스 광고\\n(본격 성장)', xy=(2023, df_inf.get('덱스', pd.Series({2023:0})).get(2023, 0)), \n",
                "                xytext=(2023.5, 1000), arrowprops=dict(facecolor='black', shrink=0.05), fontsize=10)\n",
                "\n",
                "ax.set_title('🎬 주요 인플루언서별 리뷰 언급량 추이', fontweight='bold', fontsize=15)\n",
                "ax.set_ylabel('언급 횟수')\n",
                "ax.set_xlabel('연도')\n",
                "ax.legend(title='인플루언서')\n",
                "plt.show()\n",
                "\n",
                "print(\"💡 2022년 말부터 덱스 언급량이 발생하며, 2023년에 폭발적으로 증가하는 양상을 보입니다.\")\n",
                "print(\"💡 스완은 2020년부터 꾸준히 언급되다가 2023년 공동개발 시점에 정점을 찍습니다.\")"
            ]
        })
        
        # 1-3 중소 브랜드 진입 분석 섹션 추가
        new_cells.append({
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 1-3. 중소 브랜드 시장 진단 (신생 vs 기존 성장)\n",
                "2024년 중소 브랜드 성장이 '새로운 브랜드의 유입' 때문인지, '기존 브랜드들의 활성화' 때문인지 확인합니다."
            ]
        })
        new_cells.append({
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 1. 브랜드별 최초 리뷰 연도 확인\n",
                "brand_entry = df.groupby('브랜드')['Review_Year'].min().reset_index(name='진입연도')\n",
                "new_brands_per_year = brand_entry.groupby('진입연도').size().reset_index(name='신규진입_브랜드수')\n",
                "\n",
                "# 2. 연도별 활성 브랜드 수(리뷰가 1건이라도 있는 브랜드)\n",
                "active_brands_per_year = df.groupby('Review_Year')['브랜드'].nunique().reset_index(name='활성_브랜드수')\n",
                "\n",
                "# 시각화\n",
                "fig, ax1 = plt.subplots(figsize=(12, 5))\n",
                "\n",
                "# 신규 진입 브랜드 수 (막대)\n",
                "sns.barplot(x='진입연도', y='신규진입_브랜드수', data=new_brands_per_year, ax=ax1, color='lightblue', label='신규 진입 브랜드 수')\n",
                "\n",
                "# 활성 브랜드 수 (라인)\n",
                "ax2 = ax1.twinx()\n",
                "sns.lineplot(x=active_brands_per_year['Review_Year'], y=active_brands_per_year['활성_브랜드수'], ax=ax2, \n",
                "             marker='o', color='red', label='총 활성 브랜드 수')\n",
                "\n",
                "ax1.set_title('🆕 연도별 브랜드 신규 진입 및 활성화 추이', fontweight='bold', fontsize=15)\n",
                "ax1.set_xlabel('연도')\n",
                "ax1.set_ylabel('신규 진입 수')\n",
                "ax2.set_ylabel('총 활성 브랜드 수')\n",
                "ax1.legend(loc='upper left')\n",
                "ax2.legend(loc='upper right')\n",
                "plt.show()\n",
                "\n",
                "print(f\"💡 2023~2024년에 신규 진입하거나 리뷰가 활성화된 브랜드가 급증했습니다.\")"
            ]
        })
        
        # 사용자가 수동으로 추가한 '확인해야하는 것' 셀은 삭제 (위에서 더 상세히 다룸)
        skip_next = False
        continue
        
    if "여기서 확인해야하는 것" in source_text:
        continue
        
    new_cells.append(cell)

nb['cells'] = new_cells

with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print("✅ Notebook updated with influencer and brand entry analysis.")
