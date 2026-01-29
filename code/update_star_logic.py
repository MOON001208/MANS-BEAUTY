import json
import os

path = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\리뷰수집.ipynb'

with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 두 번째 셀 (index 1)이 scroll_and_crawl 함수가 있는 셀입니다.
cell = data['cells'][1]
source = cell['source']
new_source = []

for line in source:
    if 'star_rating = user.find_elements(By.CSS_SELECTOR, "div.meta div.rating oy-review-star-icon")' in line:
        # 별점 수집 로직 시작 부분 교체
        indent = line[:line.find('star_rating')]
        new_source.append(f'{indent}star_icons = user.find_elements(By.CSS_SELECTOR, "div.meta div.rating oy-review-star-icon")\n')
        new_source.append(f'{indent}rating_score = 0\n')
        new_source.append(f'{indent}for icon in star_icons:\n')
        new_source.append(f'{indent}    try:\n')
        new_source.append(f'{indent}        icon_shadow = icon.shadow_root\n')
        new_source.append(f'{indent}        path_el = icon_shadow.find_element(By.CSS_SELECTOR, "path")\n')
        new_source.append(f'{indent}        if path_el.get_attribute("fill") != "none":\n')
        new_source.append(f'{indent}            rating_score += 1\n')
        new_source.append(f'{indent}    except:\n')
        new_source.append(f'{indent}        continue\n')
    elif 'star_list.append(len(star_rating))' in line:
        # 별점 리스트에 추가하는 부분 교체
        indent = line[:line.find('star_list')]
        new_source.append(f'{indent}star_list.append(rating_score)\n')
    else:
        new_source.append(line)

cell['source'] = new_source

with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=1, ensure_ascii=False)

print("Successfully updated the notebook.")
