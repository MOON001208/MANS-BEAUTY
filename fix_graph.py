import json
import numpy as np

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
                "# [수정] 모든 연도를 포함하는 마스터 데이터프레임으로 결합하여 x축 정렬\n",
                "# barplot과 lineplot의 x축 스케일을 맞추기 위해 통합된 연도 리스트를 사용합니다.\n",
                "all_years = sorted(df['Review_Year'].unique())\n",
                "plot_data = pd.DataFrame({'연도': all_years})\n",
                "plot_data = plot_data.merge(new_brands_per_year, left_on='연도', right_on='진입연도', how='left').fillna(0)\n",
                "plot_data = plot_data.merge(active_brands_per_year, left_on='연도', right_on='Review_Year', how='left').fillna(0)\n",
                "\n",
                "# 시각화\n",
                "fig, ax1 = plt.subplots(figsize=(12, 5))\n",
                "\n",
                "# 1. 신규 진입 브랜드 수 (막대)\n",
                "sns.barplot(x='연도', y='신규진입_브랜드수', data=plot_data, ax=ax1, color='lightblue', label='신규 진입 브랜드 수')\n",
                "\n",
                "# 2. 총 활성 브랜드 수 (라인)\n",
                "ax2 = ax1.twinx()\n",
                "# 중요: barplot의 x축은 범주형(0, 1, 2...)으로 처리되므로, lineplot도 같은 정수 인덱스를 좌표로 사용해야 정렬됩니다.\n",
                "sns.lineplot(x=np.arange(len(plot_data)), y=plot_data['활성_브랜드수'], ax=ax2, \n",
                "             marker='o', color='red', label='총 활성 브랜드 수')\n",
                "\n",
                "ax1.set_title('🆕 연도별 브랜드 신규 진입 및 활성화 추이', fontweight='bold', fontsize=15)\n",
                "ax1.set_xlabel('연도')\n",
                "ax1.set_ylabel('신규 진입 수')\n",
                "ax2.set_ylabel('총 활성 브랜드 수')\n",
                "\n",
                "# 범례 통합 (왼쪽, 오른쪽 축 범례를 하나로 합침)\n",
                "lines1, labels1 = ax1.get_legend_handles_labels()\n",
                "lines2, labels2 = ax2.get_legend_handles_labels()\n",
                "ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')\n",
                "if ax2.get_legend(): ax2.get_legend().remove()\n",
                "\n",
                "plt.show()\n",
                "\n",
                "print(f\"💡 {int(min(all_years))}~{int(max(all_years))}년 기간 동안 브랜드 진입 및 활성도가 증가하고 있습니다.\")"
            ]
            target_found = True
            break

if target_found:
    with open(notebook_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    print("✅ Successfully fixed the graph misalignment and alignment issue.")
else:
    print("❌ Could not find the target cell in the notebook.")
