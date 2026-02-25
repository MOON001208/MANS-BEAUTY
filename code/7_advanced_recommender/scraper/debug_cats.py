import json
from curl_cffi import requests as cf_requests
from bs4 import BeautifulSoup

def test_cat(category_id):
    url = "https://www.oliveyoung.co.kr/store/display/getGoodsListAjax.do"
    payload = {
        "dispCatNo": category_id,
        "fltDispCatNo": "",
        "prdSort": "01",
        "pageIdx": 1,
        "rowsPerPage": 24,
        "searchType": "01",
        "gateCd": "Drawer",
    }
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }
    res = cf_requests.post(url, data=payload, headers=HEADERS, impersonate="chrome124")
    print(f"Cat {category_id} Status: {res.status_code}")
    soup = BeautifulSoup(res.text, "html.parser")
    items = soup.select("li")
    print(f"Items found: {len(items)}")
    if len(items) > 0:
        print("First item:", items[0].select_one(".tx_name").get_text(strip=True) if items[0].select_one(".tx_name") else "No name")

test_cat("1000001000700080011") # Cushion
test_cat("1000001000700080015") # Tone Lotion
