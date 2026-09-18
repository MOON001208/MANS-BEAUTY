"""Olive Young public catalog and cursor review collector (verified 2026-09-16).

No login bypass. Stop on loginRequired/401/403; never interpret failures as zeros.
Default is dry-run. Each successful page is persisted before its cursor advances.
"""
from __future__ import annotations
import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from bs4 import BeautifulSoup
from curl_cffi import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared import CACHE, database, read_all, read_json, utc_now, write_json, product_type as infer_product_type

LOG = logging.getLogger(__name__)
SITE = 'https://www.oliveyoung.co.kr'
REVIEW_ROOT = 'https://m.oliveyoung.co.kr/review/api/v2/reviews'
CATALOG_ID = '100000100020001'  # current base makeup, filtered by menCategoryFlag
PRODUCT_SORTS = {'new': '02', 'popular': '01'}
REVIEW_SORTS = ('DATETIME_DESC', 'USEFUL_SCORE_DESC', 'RATING_DESC', 'RATING_ASC')
SKIN_TYPES = {'A01': '건성', 'A02': '지성', 'A03': '복합성', 'A04': '중성', 'A05': '민감성'}
SKIN_TONES = {'B01': '쿨톤', 'B02': '웜톤', 'B03': '뉴트럴'}
SKIN_TROUBLES = {'C01': '건조함', 'C02': '여드름', 'C03': '모공', 'C04': '블랙헤드', 'C05': '미백', 'C06': '주름', 'C07': '탄력', 'C08': '다크서클', 'C09': '홍조', 'C10': '잡티', 'C11': '각질'}

class SourceError(RuntimeError):
    pass

class AccessLimited(SourceError):
    pass

class RateLimited(SourceError):
    pass

class BudgetReached(SourceError):
    pass

class OliveYoung:
    def __init__(self, delay=2.0, session=None, max_seconds=5400):
        self.session = session or requests.Session(impersonate='chrome124')
        self.delay, self.last_request = delay, 0.0
        self.deadline = time.monotonic() + max_seconds

    def request(self, method, url, **kwargs):
        headers = {'accept': 'application/json, text/plain, */*', 'origin': SITE, 'referer': SITE + '/'}
        for attempt in range(4):
            if time.monotonic() >= self.deadline:
                raise BudgetReached('실행 시간 예산 종료; 다음 실행에서 이어갑니다.')
            time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
            try:
                self.last_request = time.monotonic()
                response = self.session.request(method, url, headers=headers, timeout=30, **kwargs)
            except requests.RequestsError:
                if attempt == 3:
                    raise SourceError('올리브영 네트워크 재시도 소진') from None
                time.sleep(2 ** attempt)
                continue
            if response.status_code in (401, 403):
                raise AccessLimited(f'올리브영 접근 제한 HTTP {response.status_code}')
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 3:
                    if response.status_code == 429:
                        raise RateLimited('HTTP 429 요청량 제한; 수집을 중단합니다.')
                    raise SourceError(f'올리브영 재시도 소진 HTTP {response.status_code}')
                wait = response.headers.get('Retry-After', '')
                if wait.isdigit() and float(wait) > 60:
                    raise RateLimited('서버가 긴 대기 시간을 요청했습니다. 수집을 중단합니다.')
                time.sleep(float(wait) if wait.isdigit() else 2 ** (attempt + 2))
                continue
            if not 200 <= response.status_code < 300:
                raise SourceError(f'올리브영 HTTP {response.status_code}')
            return response
        raise SourceError('올리브영 응답 없음')

    def json(self, method, url, **kwargs):
        try:
            payload = self.request(method, url, **kwargs).json()
        except ValueError:
            raise SourceError('JSON 응답이 아닙니다.') from None
        if not isinstance(payload, dict) or payload.get('code', 200) not in (200, '200'):
            raise SourceError('올리브영 API 실패 응답')
        if payload.get('data') is None:
            raise SourceError('올리브영 API data 누락')
        return payload['data']

    def catalog_page(self, page, sort):
        response = self.request('GET', SITE + '/store/display/getMCategoryList.do', params={
            'dispCatNo': CATALOG_ID, 'prdSort': PRODUCT_SORTS[sort], 'pageIdx': page, 'rowsPerPage': 48})
        soup = BeautifulSoup(response.text, 'html.parser')
        products = []
        for item in soup.select('div.prd_info'):
            link = item.select_one('a.prd_thumb')
            if not link:
                continue
            match = re.search(r'goodsNo=([A-Z0-9]+)', link.get('href', ''))
            pid = link.get('data-ref-goodsno') or (match.group(1) if match else '')
            if not re.fullmatch(r'[A-Z]\d+', pid):
                continue
            products.append({'id': pid})
        if not products and (page == 1 or '상품이 등록되어' not in soup.get_text()):
            raise SourceError('카테고리 변경/파싱 실패: 상품 0개')
        return products

    def detail(self, pid):
        return self.json('GET', SITE + '/goods/api/v1/detail', params={'goodsNo': pid})

    def stats(self, pid):
        data = self.json('GET', REVIEW_ROOT + f'/{pid}/stats')
        count = data.get('reviewCount')
        rating = (data.get('ratingDistribution') or {}).get('averageRating')
        if not isinstance(count, (int, float)) or count < 0 or rating is None:
            raise SourceError('리뷰 통계 필드가 변경되었습니다.')
        return {'review_count': int(count), 'star_rating': float(rating)}

    def ingredients(self, pid, detail):
        data = self.json('POST', SITE + '/goods/api/v1/article', json={
            'goodsNumber': pid, 'liquorFlag': detail.get('liquorFlag', False),
            'goodsOptionInfoList': [{'standardCode': o.get('standardCode'), 'optionName': o.get('optionName')} for o in detail.get('options', [])]})
        return parse_ingredients(data)

    def reviews_page(self, pid, sort, cursor=None):
        if sort not in REVIEW_SORTS:
            raise ValueError('검증되지 않은 정렬')
        data = self.json('POST', REVIEW_ROOT + '/cursor', json={
            'goodsNumber': pid, 'size': 10, 'sortType': sort, 'reviewType': 'ALL', **(cursor or {})})
        if not isinstance(data, dict) or not isinstance(data.get('goodsReviewList'), list) or not isinstance(data.get('hasNext'), bool):
            raise SourceError('리뷰 커서 응답 스키마 변경')
        return data

def parse_ingredients(data):
    found = []
    def walk(node):
        if isinstance(node, dict):
            labels = [v for k, v in node.items() if isinstance(v, str) and re.search(r'name|title|label', k, re.I)]
            if any('성분' in label for label in labels):
                for key, value in node.items():
                    if isinstance(value, str) and re.search(r'value|content|description|info', key, re.I):
                        clean = BeautifulSoup(value, 'html.parser').get_text(' ', strip=True)
                        if len(clean) > 15:
                            found.append(clean)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(data)
    unique = list(dict.fromkeys(found))
    # Do not concatenate different options' formulations.
    return unique[0] if len(unique) == 1 else None

def is_target(detail, known=False):
    """Every men's base makeup product, as Olive Young classifies it.

    Olive Young has no men's category to browse: menCategoryFlag on the product
    is what marks one. Matching the standard middle category rather than name
    keywords keeps 컨실러, 파우더 and 프라이머 in, which a keyword list dropped.
    """
    standard = detail.get('standardCategory') or {}
    middle = (standard.get('middleCategoryName') or '').replace(' ', '')
    return known or (detail.get('menCategoryFlag') is True and middle == '베이스메이크업')

def product_from_detail(pid, detail):
    kind = (detail.get('standardCategory') or {}).get('lowerCategoryName', '')
    name = detail.get('goodsName', '')
    if not name or detail.get('goodsNumber') != pid:
        raise SourceError('상품 상세 ID/이름 불일치')
    product_type = infer_product_type(name, kind)
    group = '톤 로션/BB' if product_type == 'tone_lotion' else '쿠션/파운데이션'
    images = detail.get('thumbnailImage') or []
    image = images[0] if images else {}
    image_url = '/'.join([str(image.get('url') or '').rstrip('/'), str(image.get('path') or '').lstrip('/')]).rstrip('/')
    result = {'id': pid, 'name': name, 'brand': detail.get('onlineBrandName', ''), 'category': group,
              'product_type': product_type, 'product_url': SITE + '/store/goods/getGoodsDetail.do?goodsNo=' + pid,
              'last_updated_at': utc_now(),
              'source_options': [{'id': o.get('optionNumber'), 'name': o.get('optionName') or '', 'sold_out': bool(o.get('soldOutFlag'))} for o in detail.get('options', [])]}
    if image_url and image_url.startswith('https://'):
        result['thumbnail_url'] = image_url
    for target, source in [('price', 'finalPrice'), ('original_price', 'salePrice')]:
        value = detail.get(source)
        if isinstance(value, (int, float)) and value >= 0:
            result[target] = value
    return result

def normalize_review(raw, pid):
    rid, rating = raw.get('reviewId'), raw.get('reviewScore')
    if rid is None or str(rid) == '' or not isinstance(rating, (int, float)) or not 1 <= rating <= 5:
        raise SourceError('리뷰 ID/평점 오류')
    profile, goods = raw.get('profileDto') or {}, raw.get('goodsDto') or {}
    source_pid = goods.get('goodsNumber') or goods.get('goodsNo') or pid
    try:
        date = datetime.fromisoformat(raw['createdDateTime'].replace('.', '-').replace('Z', '+00:00'))
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone(timedelta(hours=9)))
    except (KeyError, ValueError, TypeError):
        raise SourceError('리뷰 작성일 형식 오류') from None
    trouble = profile.get('skinTrouble') or []
    if isinstance(trouble, str):
        trouble = [trouble]
    return {'id': str(rid), 'product_id': source_pid, 'rating': int(rating), 'content': raw.get('content') or '',
            'author': None, 'skin_type': SKIN_TYPES.get(profile.get('skinType'), profile.get('skinType')),
            'skin_tone': SKIN_TONES.get(profile.get('skinTone'), profile.get('skinTone')),
            'skin_trouble': ','.join(SKIN_TROUBLES.get(t, t) for t in trouble) or None,
            'option_name': goods.get('optionName') or None, 'is_best': bool(raw.get('isBest', False)),
            'created_at': date.isoformat(), 'last_updated_at': utc_now()}

def harvest_reviews(api, pid, save_page, state, max_pages=500, sorts=REVIEW_SORTS, checkpoint=lambda: None):
    """Fresh head of every sort, then resume historical cursor. Never stop on known IDs."""
    seen, report = set(), {'sorts': {}}
    for sort in sorts:
        key = pid + ':' + sort
        cursor = state.get(key)
        pending = [None] + ([cursor] if cursor else [])
        visited, pages, fetched, stop = set(), 0, 0, 'page_budget'
        while pages < max_pages:
            current = pending.pop(0) if pending else cursor
            signature = json.dumps(current, sort_keys=True)
            if signature in visited:
                stop = 'repeated_cursor'
                break
            visited.add(signature)
            data = api.reviews_page(pid, sort, current)
            rows = [normalize_review(r, pid) for r in data['goodsReviewList']]
            new = {r['id']: r for r in rows if r['id'] not in seen}
            save_page(list(new.values()))
            seen.update(new)
            fetched += len(new)
            pages += 1
            next_cursor = {k: data.get('next' + k[0].upper() + k[1:]) for k in ('cursorId', 'cursorScore', 'cursorCount')}
            if data.get('loginRequired'):
                stop = 'login_required'
                break
            if not data['hasNext']:
                state.pop(key, None)
                checkpoint()
                stop = 'exhausted'
                break
            if not rows or next_cursor['cursorId'] is None:
                raise SourceError('hasNext인데 리뷰 또는 다음 커서가 없습니다.')
            if not pending:
                cursor = next_cursor
                state[key] = cursor
                checkpoint()
        report['sorts'][sort] = {'pages': pages, 'unique_fetched': fetched, 'stop': stop}
    report['unique_fetched'] = len(seen)
    return report

def run(args):
    db, api = database(), OliveYoung(args.delay, max_seconds=args.max_seconds)
    if args.write:
        db.table('products').select('id,profile_metadata,source_options').limit(1).execute()
    existing = {p['id']: p for p in read_all(db, 'products')}
    known_review_ids = {str(r['id']) for r in read_all(db, 'reviews', 'id')}
    rejected_sources = set()
    state_path = CACHE / 'review-cursors.json'
    state = read_json(state_path, {}) if not args.fresh else {}
    history_path = CACHE / 'collection-history.json'
    history = read_json(history_path, {})
    report = {'started_at': utc_now(), 'dry_run': not args.write, 'catalog': {}, 'products': [], 'errors': []}
    def checkpoint():
        if args.write:
            write_json(state_path, state)
    candidates = dict.fromkeys(args.product or [])
    if not args.product:
        # Discover new products first, then include every known product.
        for sort in PRODUCT_SORTS:
            seen_catalog, stop = set(), 'page_budget'
            try:
                for page in range(1, args.max_catalog_pages + 1):
                    products = api.catalog_page(page, sort)
                    ids = {p['id'] for p in products}
                    if not ids:
                        stop = 'exhausted'
                        break
                    if ids <= seen_catalog:
                        stop = 'repeated_page'
                        break
                    seen_catalog.update(ids)
                    for p in products:
                        candidates.setdefault(p['id'], None)
                    if len(products) < 48:
                        stop = 'exhausted'
                        break
                report['catalog'][sort] = {'unique': len(seen_catalog), 'stop': stop}
            except (AccessLimited, RateLimited, BudgetReached) as error:
                report['errors'].append({'stage': 'catalog', 'sort': sort, 'error': str(error)})
                write_json(CACHE / 'crawl-report.json', report)
                return report
            except SourceError as error:
                report['errors'].append({'stage': 'catalog', 'sort': sort, 'error': str(error)})
        for pid in existing:
            candidates.setdefault(pid, None)
    details_path = CACHE / 'catalog-details.json'
    details_cache = read_json(details_path, {})
    processed = 0
    # Oldest successful collection first prevents repeatedly exhausting the budget on the same products.
    for pid in sorted(candidates, key=lambda key: history.get(key, 0)):
        if args.max_products and processed >= args.max_products:
            report['product_budget_reached'] = True
            break
        item, counts = None, {}
        try:
            cached = details_cache.get(pid)
            if pid not in existing and cached and time.time() - cached['at'] < 7 * 86400 and not cached['target']:
                continue
            detail = api.detail(pid)
            target = is_target(detail, pid in existing)
            details_cache[pid] = {'at': time.time(), 'target': target}
            if not target:
                continue
            product = product_from_detail(pid, detail)
            item = {'id': pid, 'is_new': pid not in existing, 'warnings': [], 'status': 'running'}
            report['products'].append(item)
            try:
                product.update(api.stats(pid))
            except (AccessLimited, RateLimited, BudgetReached):
                raise
            except SourceError as error:
                item['warnings'].append({'stage': 'stats', 'error': str(error)})
            if not args.skip_ingredients and not (existing.get(pid) or {}).get('ingredients_raw'):
                try:
                    ingredients = api.ingredients(pid, detail)
                    if ingredients:
                        product['ingredients_raw'] = ingredients
                    else:
                        item['warnings'].append({'stage': 'ingredients', 'error': '단일 성분표 미확인'})
                except (RateLimited, BudgetReached):
                    raise
                except SourceError as error:
                    item['warnings'].append({'stage': 'ingredients', 'error': str(error)})
            if args.write:
                db.table('products').upsert(product).execute()
            counts = {'new_saved': 0, 'cross_product_skipped': 0, 'cross_product_saved': 0}
            def save_page(rows):
                accepted = []
                for row in rows:
                    source = row['product_id']
                    if source != pid and source not in existing and source not in rejected_sources:
                        source_detail = api.detail(source)
                        if is_target(source_detail):
                            source_product = product_from_detail(source, source_detail)
                            if args.write:
                                db.table('products').upsert(source_product).execute()
                            existing[source] = source_product
                        else:
                            rejected_sources.add(source)
                    if source == pid or source in existing:
                        accepted.append(row)
                    else:
                        counts['cross_product_skipped'] += 1
                fresh = [r for r in accepted if r['id'] not in known_review_ids]
                if args.write and fresh:
                    # Global ID conflicts do not overwrite earlier product assignments.
                    result = db.table('reviews').upsert(fresh, on_conflict='id', ignore_duplicates=True).execute()
                    counts['new_saved'] += len(result.data or [])
                    counts['cross_product_saved'] += sum(r['product_id'] != pid for r in result.data or [])
                elif not args.write:
                    counts['would_insert'] = counts.get('would_insert', 0) + len(fresh)
                known_review_ids.update(r['id'] for r in accepted)
            if getattr(args, 'products_only', False):
                item['reviews'] = {'skipped': 'products_only'}
            else:
                item['reviews'] = harvest_reviews(api, pid, save_page, state, args.max_review_pages, checkpoint=checkpoint)
            item.update(counts)
            item['status'] = 'complete'
            history[pid] = time.time()
            processed += 1
            LOG.info('%s: %s', pid, json.dumps(counts))
        except Exception as error:
            if item is not None:
                item['status'] = 'partial_or_failed'
            report['errors'].append({'stage': 'product', 'id': pid, 'error': str(error) if isinstance(error, SourceError) else type(error).__name__})
            LOG.error('%s 실패 (%s)', pid, type(error).__name__)
            processed += 1
            if isinstance(error, (AccessLimited, RateLimited, BudgetReached)):
                report['stop'] = type(error).__name__
                break
        finally:
            if item is not None:
                item.update(counts)
            if args.write:
                write_json(details_path, details_cache)
                write_json(history_path, history)
            report['finished_at'] = utc_now()
            write_json(CACHE / 'crawl-report.json', report)
    write_json(CACHE / 'crawl-report.json', report)
    return report

def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--write', action='store_true')
    p.add_argument('--product', action='append')
    p.add_argument('--max-products', type=int, default=0)
    p.add_argument('--max-catalog-pages', type=int, default=100)
    p.add_argument('--max-review-pages', type=int, default=500)
    p.add_argument('--delay', type=float, default=2.0)
    p.add_argument('--max-seconds', type=int, default=5400)
    p.add_argument('--fresh', action='store_true')
    p.add_argument('--skip-ingredients', action='store_true')
    # Refreshes catalog and option data only; review cursors are left untouched.
    p.add_argument('--products-only', action='store_true')
    return p

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    args = parser().parse_args()
    if args.max_review_pages < 2 or args.max_catalog_pages < 1 or args.delay < 0 or args.max_seconds <= 0:
        raise SystemExit('리뷰 페이지 예산 >=2, 카테고리 페이지 >=1, 지연 >=0 필요')
    result = run(args)
    print(json.dumps({'products': len(result['products']), 'errors': len(result['errors'])}))
    raise SystemExit(1 if result['errors'] else 0)
