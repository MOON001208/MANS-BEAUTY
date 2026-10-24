"""Seller-listed ingredients, preserving option and bundle boundaries verbatim."""
from __future__ import annotations

import re
from bs4 import BeautifulSoup
from shared import CACHE, database, read_all, read_json, utc_now, write_json

INGREDIENT_TITLE = re.compile(r'전\s*성분|모든\s*성분')
REFERENCE_ONLY = re.compile(r'상세\s*(?:페이지|설명)|이미지.*(?:참조|참고)|별도\s*(?:표기|기재)|제품.*(?:참조|참고)')


def ingredient_listing(data, pid, checked_at=None):
    entries, references, seen = [], [], set()

    def visit(node, group=''):
        if isinstance(node, list):
            for child in node:
                visit(child, group)
        elif isinstance(node, dict):
            title = node.get('title') or node.get('name') or node.get('label') or ''
            content = node.get('content') or node.get('value') or node.get('description')
            if isinstance(title, str) and INGREDIENT_TITLE.search(title) and isinstance(content, str):
                text = BeautifulSoup(content, 'html.parser').get_text('\n', strip=True)
                text = text.replace('\\n', '\n').replace('\x00', ' ').strip()
                label = ' / '.join(x for x in [group, title] if x)
                if text and (label, text) not in seen:
                    seen.add((label, text))
                    target = references if REFERENCE_ONLY.search(text) and ',' not in text else entries
                    target.append({'label': label, 'text': text})
            for key, child in node.items():
                if isinstance(child, (dict, list)):
                    visit(child, title if key == 'items' and isinstance(title, str) else group)

    visit(data)
    return {
        'status': 'partial' if entries and references else 'collected' if entries else 'reference_only' if references else 'not_listed',
        'source_url': 'https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=' + pid,
        'checked_at': checked_at or utc_now(), 'entries': entries, 'references': references,
        'scope': 'seller_listing',
    }


def ingredient_patch(product, article, checked_at=None, unavailable=False, images=None):
    listing = ingredient_listing(article, product['id'], checked_at)
    if unavailable:
        listing['status'] = 'unavailable'
        listing['references'] = [{'label': '현재 원문', 'text': '상품을 찾을 수 없어 현재 전성분을 확인하지 못했습니다.'}]
    if images and not unavailable:
        listing['images'] = [item for item in images if item.get('url', '').startswith('https://image.oliveyoung.co.kr/')]
        if listing['images'] and not listing['entries']:
            listing['status'] = 'image_only'
    patch = {'profile_metadata': {**(product.get('profile_metadata') or {}), 'ingredient_source': listing}}
    if listing['entries']:
        # Keep all labels and the original [shade]/[bundle component] sections.
        patch['ingredients_raw'] = '\n\n'.join(
            f"{entry['label']}\n{entry['text']}" for entry in listing['entries'])
    # Missing/blocked data must not delete an earlier successfully stored text.
    return patch, listing


def collect(args, session=None):
    from scraper.crawler import OliveYoung, SourceError, AccessLimited, RateLimited, BudgetReached, product_from_detail
    db = database()
    products = [p for p in read_all(db, 'products') if not args.product or p['id'] in args.product]
    api = OliveYoung(args.delay, session=session, max_seconds=args.max_seconds)
    report = {'started_at': utc_now(), 'dry_run': not args.write, 'products': [], 'errors': []}
    for product in products:
        pid = product['id']
        item = {'id': pid, 'name': product['name']}
        report['products'].append(item)
        try:
            cached = CACHE / 'ingredient-articles' / f'{pid}.json'
            if getattr(args, 'from_ingredient_cache', False):
                if not cached.exists():
                    raise SourceError('성분 응답 캐시 없음; 온라인 수집 필요')
                payload = read_json(cached, {})
            else:
                warning = None
                try:
                    detail = api.detail(pid)
                except (AccessLimited, RateLimited, BudgetReached):
                    raise
                except SourceError as error:
                    detail, warning = {}, str(error)
                payload = {'detail': detail, 'article': api.ingredient_article(pid, detail),
                           'checked_at': utc_now(), 'detail_warning': warning}
                write_json(cached, payload)
            detail = payload.get('detail') or {}
            patch, listing = ingredient_patch(product, payload['article'], payload.get('checked_at'), payload.get('unavailable', False), payload.get('ingredient_images'))
            if detail:
                refreshed = product_from_detail(pid, detail, product)
                patch = {**refreshed, **patch}
                patch['profile_metadata']['source_category'] = refreshed.get('profile_metadata', {}).get('source_category')
            if args.write:
                response = db.table('products').update(patch).eq('id', pid).execute()
                if not response.data:
                    raise RuntimeError('상품 성분 갱신 결과 0행')
            item.update(status=listing['status'], entries=len(listing['entries']),
                        references=len(listing['references']), checked_at=listing['checked_at'])
        except Exception as error:
            item['status'] = 'failed'
            report['errors'].append({'id': pid, 'error': str(error) if isinstance(error, SourceError) else type(error).__name__})
            if isinstance(error, (AccessLimited, RateLimited, BudgetReached)):
                report['stop'] = type(error).__name__
                break
        finally:
            report['finished_at'] = utc_now()
            write_json(CACHE / 'ingredient-report.json', report)
        print(f"성분 {pid}: {item['status']}", flush=True)
    return report
