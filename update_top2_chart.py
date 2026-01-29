
import nbformat
import os

def add_top2_chart(file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        nb = nbformat.read(f, as_version=4)

    for cell in nb.cells:
        if cell.cell_type == 'code' and "yearly_excl_top2 = df[~df['브랜드'].isin(TOP2)]" in cell.source:
            source = cell.source
            
            # 신규 로직으로 교체
            new_source = [
                "# 1. 전체 시장 트렌드",
                "yearly_all = df.groupby('Review_Year').size().reset_index(name='전체')",
                "",
                "# 2. Top 2(오브제, 비레디) 제외 트렌드 (중소 브랜드 성장성 확인)",
                "TOP2 = ['오브제', '비레디']",
                "yearly_excl_top2 = df[~df['브랜드'].isin(TOP2)].groupby('Review_Year').size().reset_index(name='Top2제외')",
                "",
                "# 3. Top 2 브랜드(오브제, 비레디) 자체 트렌드",
                "yearly_top2 = df[df['브랜드'].isin(TOP2)].groupby('Review_Year').size().reset_index(name='Top2')",
                "",
                "# 데이터 병합 (결측치 처리를 위해 전체 연도 기준으로 병합)",
                "plot_df = yearly_all.merge(yearly_excl_top2, on='Review_Year', how='left').merge(yearly_top2, on='Review_Year', how='left').fillna(0)",
                "",
                "# 시각화",
                "fig, ax1 = plt.subplots(figsize=(14, 6))",
                "x = plot_df['Review_Year']",
                "width = 0.25",
                "",
                "ax1.bar(x - width, plot_df['전체'], width=width, label='전체 시장', color='lightsteelblue', alpha=0.8)",
                "ax1.bar(x, plot_df['Top2'], width=width, label='Top 2 시장 (오브제, 비레디)', color='royalblue', alpha=0.9)",
                "ax1.bar(x + width, plot_df['Top2제외'], width=width, label='중소 브랜드 시장 (Top2 제외)', color='salmon', alpha=0.8)",
                "",
                "ax1.set_xticks(x)",
                "ax1.set_xticklabels(x.astype(int))",
                "ax1.set_title('📈 연도별 리뷰 수 성장 추이 (전체 vs Top 2 vs 중소 브랜드)', fontweight='bold', fontsize=16)",
                "ax1.set_xlabel('연도')",
                "ax1.set_ylabel('리뷰 수')",
                "ax1.legend()",
                "",
                "plt.tight_layout()",
                "plt.show()"
            ]
            cell.source = '\n'.join(new_source)
            break

    with open(file_path, 'w', encoding='utf-8') as f:
        nbformat.write(nb, f)
    print("Top 2 chart updated successfully.")

if __name__ == "__main__":
    target = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\final_market_analysis.ipynb'
    add_top2_chart(target)
