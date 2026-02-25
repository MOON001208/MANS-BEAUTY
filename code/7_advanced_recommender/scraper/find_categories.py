"""톤로션/BB 카테고리 ID 확인"""
from curl_cffi import requests
from bs4 import BeautifulSoup
import re

candidates = [
    "1000001000700080010",
    "1000001000700080011",  # 쿠션/파운데이션 (확인됨)
    "1000001000700080012",
    "1000001000700080013",
    "1000001000700080014",
    "1000001000700080015",
    "1000001000700080016",
    "1000001000700080017",
    "1000001000700080018",
    "1000001000700080019",
    "1000001000700080020",
]

for cat_id in candidates:
    url = f"https://www.oliveyoung.co.kr/store/display/getMCategoryList.do?dispCatNo={cat_id}"
    r = requests.get(url, impersonate="chrome124")
    s = BeautifulSoup(r.text, "html.parser")
    title = s.title.text.strip() if s.title else "N/A"
    goods = set(re.findall(r"goodsNo=([A-Z0-9]+)", r.text))
    print(f"[{cat_id}] goods={len(goods):>3}, title={title}")
