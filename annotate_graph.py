import json
import numpy as np
import pandas as pd

notebook_path = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\final_market_analysis.ipynb'

with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

target_found = False
for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source_text = "".join(cell['source'])
        if "연도별 브랜드 신규 진입 및 활성화 추이" in source_text:
            cell['source'] = [
                "# 1. 브랜드별 최초 리뷰 연도 확인\n",
                "brand_entry = df.groupby('브랜드')['Review_Year'].min().reset_index(name='진입연도')\n",
                "new_brands_per_year = brand_entry.groupby('진입연도').size().reset_index(name='신규진입_브랜드수')\n",
                "active_brands_per_year = df.groupby('Review_Year')['브랜드'].nunique().reset_index(name='활성_브랜드수')\n",
                "\n",
                "# [수정] 연도별 신규 진입 브랜드 목록 생성\n",
                "brands_by_year = brand_entry.groupby('진입연도')['브랜드'].apply(lambda x: '\\n'.join(x)).to_dict()\n",
                "\n",
                "# 모든 연도를 포함하는 마스터 데이터프레임으로 결합\n",
                "all_years = sorted(df['Review_Year'].unique())\n",
                "plot_data = pd.DataFrame({'연도': all_years})\n",
                "plot_data = plot_data.merge(new_brands_per_year, left_on='연도', right_on='진입연도', how='left').fillna(0)\n",
                "plot_data = plot_data.merge(active_brands_per_year, left_on='연도', right_on='Review_Year', how='left').fillna(0)\n",
                "\n",
                "# 시각화\n",
                "fig, ax1 = plt.subplots(figsize=(14, 7))\n",
                "\n",
                "# 1. 신규 진입 브랜드 수 (막대)\n",
                "bar_plot = sns.barplot(x='연도', y='신규진입_브랜드수', data=plot_data, ax=ax1, color='lightblue', label='신규 진입 브랜드 수', alpha=0.7)\n",
                "\n",
                "# 막대 위에 브랜드명 기입\n",
                "for i, row in plot_data.iterrows():\n",
                "    year = row['연도']\n",
                "    count = row['신규진입_브랜드수']\n",
                "    if count > 0:\n",
                "        brand_names = brands_by_year.get(year, \"\")\n",
                "        ax1.text(i, count + 0.1, brand_names, ha='center', va='bottom', \n",
                "                 fontsize=10, fontweight='bold', color='#2c3e50', \n",
                "                 bbox=dict(facecolor='white', alpha=0.5, edgecolor='none', pad=1))\n",
                "\n",
                "# 2. 총 활성 브랜드 수 (라인)\n",
                "ax2 = ax1.twinx()\n",
                "sns.lineplot(x=np.arange(len(plot_data)), y=plot_data['활성_브랜드수'], ax=ax2, \n",
                "             marker='o', markersize=10, color='red', linewidth=2.5, label='총 활성 브랜드 수')\n",
                "\n",
                "ax1.set_title('🆕 연도별 브랜드 신규 진입 및 활성화 추이', fontweight='bold', fontsize=16, pad=20)\n",
                "ax1.set_xlabel('연도', fontsize=12)\n",
                "ax1.set_ylabel('신규 진입 수', fontsize=12)\n",
                "ax2.set_ylabel('총 활성 브랜드 수', fontsize=12)\n",
                "ax1.set_ylim(0, plot_data['신규진입_브랜드수'].max() + 2) # 라벨 공간 확보\n",
                "\n",
                "# 범례 통합\n",
                "lines1, labels1 = ax1.get_legend_handles_labels()\n",
                "lines2, labels2 = ax2.get_legend_handles_labels()\n",
                "ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=11)\n",
                "if ax2.get_legend(): ax2.get_legend().remove()\n",
                "\n",
                "plt.tight_layout()\n",
                "plt.show()\n"
            ]
            target_found = True
            break

if target_found:
    with open(notebook_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    print("✅ Successfully added brand name annotations to the graph.")
else:
    print("❌ Could not find the target cell in the notebook.")
