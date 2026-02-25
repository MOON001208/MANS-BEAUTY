import json
from curl_cffi import requests as cf_requests
from bs4 import BeautifulSoup
import re

def fetch_ingredients_mock(goods_no="A000000198001"):
    url = f"https://m.oliveyoung.co.kr/m/goods/getGoodsDetail.do?goodsNo={goods_no}"
    print(f"URL: {url}")
    res = cf_requests.get(url, impersonate="chrome124")
    print("Status:", res.status_code)
    
    soup = BeautifulSoup(res.text, "html.parser")
    # mobile usually has getGoodsArtc.do
    # Let's search text
    match = re.search(r'전성분', res.text)
    if match:
        print("Found text '전성분' at index", match.start())
        print(res.text[max(0, match.start()-50):min(len(res.text), match.start()+300)])
    else:
        print("Not found in mobile HTML")
        
    # Check if there is an api endpoint for ArtcInfo
    art_url = f"https://m.oliveyoung.co.kr/m/goods/getGoodsArtcInfo.do?goodsNo={goods_no}"
    res2 = cf_requests.post(art_url, data={"goodsNo": goods_no}, impersonate="chrome124", headers={"X-Requested-With": "XMLHttpRequest"})
    print("\nArtcInfo Status:", res2.status_code)
    match2 = re.search(r'전성분', res2.text)
    if match2:
        print("Found text '전성분' in ArtcInfo")
        print(res2.text[max(0, match2.start()-50):min(len(res2.text), match2.start()+300)])
    else:
        print("Not found in ArtcInfo")

fetch_ingredients_mock()
