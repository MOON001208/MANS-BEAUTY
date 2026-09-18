"""Gather YouTube text that may state which shade of a product to buy.

Only the official Data API v3 is used, and only what an API key may read:
video titles, descriptions and comments. Captions are not available for other
people's videos through the API, so spoken shade advice is out of reach here.

The key is read from YOUTUBE_API_KEY and never stored in this repository.
Search costs 100 quota units per product against a 10,000 unit daily default,
so the number of products searched is capped and reported.
"""
from __future__ import annotations
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared import CACHE, database, read_all, utc_now, write_json

API = 'https://www.googleapis.com/youtube/v3'
SEARCH_COST = 100
DEFAULT_QUOTA = 6000
VIDEOS_PER_PRODUCT = 4
COMMENTS_PER_VIDEO = 100

class QuotaExhausted(RuntimeError):
    pass

def _key():
    key = os.getenv('YOUTUBE_API_KEY')
    if not key:
        raise RuntimeError('YOUTUBE_API_KEY 환경변수가 필요합니다. 키를 코드에 넣지 마세요.')
    return key

def _call(endpoint, **params):
    params['key'] = _key()
    url = f'{API}/{endpoint}?' + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        body = error.read().decode('utf-8', 'replace')
        if error.code == 403 and 'quota' in body.lower():
            raise QuotaExhausted('YouTube 일일 할당량을 모두 사용했습니다.') from error
        raise RuntimeError(f'YouTube API {error.code}: {body[:200]}') from error

def search_videos(query, limit=VIDEOS_PER_PRODUCT):
    items = _call('search', part='snippet', q=query, type='video',
                  maxResults=limit, relevanceLanguage='ko').get('items', [])
    return [{'id': i['id']['videoId'], 'title': i['snippet']['title'],
             'description': i['snippet']['description']} for i in items]

def video_comments(video_id, limit=COMMENTS_PER_VIDEO):
    try:
        threads = _call('commentThreads', part='snippet', videoId=video_id,
                        maxResults=limit, textFormat='plainText').get('items', [])
    except RuntimeError as error:
        # Comments disabled on a video is normal and must not stop the run.
        if 'commentsDisabled' in str(error):
            return []
        raise
    return [t['snippet']['topLevelComment']['snippet']['textOriginal'] for t in threads]

def collect_texts(product_ids=None, quota=DEFAULT_QUOTA):
    """Returns {product_id: [text, ...]}; spends at most `quota` units."""
    db = database()
    products = [p for p in read_all(db, 'products', 'id,name,brand,profile_metadata')
                if not product_ids or p['id'] in product_ids]
    if not product_ids:
        # Products that already state a 21/23/25 shade need no mapping evidence.
        products = [p for p in products if not (p.get('profile_metadata') or {}).get('absolute_shade_source')]
    spent, texts, log = 0, {}, []
    for product in products:
        if spent + SEARCH_COST > quota:
            log.append({'id': product['id'], 'skipped': 'quota'})
            continue
        query = f"{product.get('brand') or ''} {product.get('name') or ''} 호수".strip()
        try:
            videos = search_videos(query)
            spent += SEARCH_COST
        except QuotaExhausted:
            log.append({'id': product['id'], 'skipped': 'quota'})
            break
        collected = []
        for video in videos:
            collected.append(f"{video['title']}\n{video['description']}")
            if spent + 1 <= quota:
                collected.extend(video_comments(video['id']))
                spent += 1
        texts[product['id']] = collected
        log.append({'id': product['id'], 'query': query, 'videos': len(videos), 'texts': len(collected)})
    write_json(CACHE / 'youtube-collection.json',
               {'collected_at': utc_now(), 'quota_spent': spent, 'products': log})
    print(json.dumps({'products': len(texts), 'quota_spent': spent}, ensure_ascii=False))
    return texts

if __name__ == '__main__':
    collect_texts()
