
import nbformat
import os

def update_influencer_threshold(file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        nb = nbformat.read(f, as_version=4)

    for cell in nb.cells:
        if cell.cell_type == 'code' and "product_mentions = exploded.groupby(['상품이름', 'mentioned_influencers'])" in cell.source:
            source = [
                "# 5. 제품별 메인 인플루언서 도출",
                "# 제품별로 3회 이상 언급된 유튜버 중 가장 많이 언급된 유튜버를 해당 제품의 'main_influencer'로 선정합니다.",
                "",
                "product_mentions = exploded.groupby(['상품이름', 'mentioned_influencers']).size().reset_index(name='count')",
                "",
                "# 3회 이상 언급된 경우만 필터링",
                "product_mentions_filtered = product_mentions[product_mentions['count'] >= 3]",
                "",
                "top_influencers = product_mentions_filtered.sort_values(['상품이름', 'count'], ascending=[True, False]).groupby('상품이름').first().reset_index()",
                "",
                "print(\"제품별 주요 인플루언서 (3회 이상 언급):\")",
                "print(top_influencers[['상품이름', 'mentioned_influencers', 'count']])",
                "",
                "# 원래 데이터프레임에 병합을 위해 매핑 딕셔너리 생성",
                "product_influencer_map = dict(zip(top_influencers['상품이름'], top_influencers['mentioned_influencers']))",
                "df['main_influencer'] = df['상품이름'].map(product_influencer_map)",
                "",
                "df[['상품이름', 'main_influencer']].drop_duplicates().dropna()"
            ]
            cell.source = '\n'.join(source)
            break

    with open(file_path, 'w', encoding='utf-8') as f:
        nbformat.write(nb, f)
    print("Influencer analysis threshold updated.")

if __name__ == "__main__":
    target = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\influencer_analysis.ipynb'
    update_influencer_threshold(target)
