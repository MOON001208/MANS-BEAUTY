"""리뷰 수집 디버깅: 다양한 sortType 테스트"""
import json
from curl_cffi import requests as cf_requests

REVIEWS_URL = "https://m.oliveyoung.co.kr/review/api/v2/reviews"
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json",
    "origin": "https://www.oliveyoung.co.kr",
    "referer": "https://www.oliveyoung.co.kr/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
}

goods_no = "A000000198001"

for sort_type in ["USEFUL_SCORE_DESC", "REGISTER_DATETIME_DESC", "HIGH_SCORE_DESC", "LOW_SCORE_DESC"]:
    payload = {
        "goodsNumber": goods_no,
        "page": 1,
        "size": 3,
        "sortType": sort_type,
        "reviewType": "ALL",
    }

    res = cf_requests.post(REVIEWS_URL, headers=HEADERS, json=payload, impersonate="chrome124")
    data = res.json()
    reviews = data.get("data", [])
    print(f"[{sort_type}] status={res.status_code}, reviews={len(reviews)}")
    if reviews:
        print(f"  first review ID: {reviews[0].get('reviewId')}, date: {reviews[0].get('createdDateTime')}")
