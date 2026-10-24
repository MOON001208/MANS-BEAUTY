"""Incremental latest-review collection with separate durable day watermarks.

Known review IDs are deduplication keys, never termination markers. Partial
cycles keep their cursor queues; resuming also scans the new head before the
pending older segment. A watermark advances only when every segment completes.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from shared import CACHE, database, read_all, read_json, utc_now, write_json

KST = timezone(timedelta(hours=9))


def collection_day(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, KST).date().isoformat()
    if not value:
        return None
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(KST).date().isoformat()


def prepare_cycle(previous, cutoff_day, now):
    if previous and previous.get('pending'):
        entry = copy.deepcopy(previous)
        # New reviews can arrive while a partial cycle is paused. This head scan
        # reaches the old head day, then the saved older cursor resumes normally.
        entry['pending'].insert(0, {'cursor': None, 'cutoff_day': collection_day(entry['head_checked_at'])})
        entry['head_checked_at'] = now
        return entry
    return {'head_checked_at': now, 'pending': [{'cursor': None, 'cutoff_day': cutoff_day}]}


def harvest_since(api, pid, save_page, entry, checkpoint=lambda: None, max_pages=500):
    from scraper.crawler import normalize_review, SourceError
    report = {'pages': 0, 'fetched': 0, 'stop': 'page_budget', 'complete': False}
    while entry['pending'] and report['pages'] < max_pages:
        phase = entry['pending'][0]
        signature = json.dumps(phase['cursor'], sort_keys=True)
        if signature in phase.get('visited', []):
            raise SourceError('최신 리뷰 커서가 반복됩니다.')
        data = api.reviews_page(pid, 'DATETIME_DESC', phase['cursor'])
        rows = list({r['id']: r for r in (normalize_review(raw, pid) for raw in data['goodsReviewList'])}.values())
        days = [collection_day(r['created_at']) for r in rows]
        if days != sorted(days, reverse=True):
            raise SourceError('최신순 리뷰 작성일 정렬이 변경되었습니다.')
        save_page(rows)  # Never move a cursor before its batch is stored.
        report['pages'] += 1
        report['fetched'] += len(rows)
        if data.get('loginRequired'):
            report['stop'] = 'login_required'
            checkpoint()
            return report
        # Dates have day precision: include the entire boundary day.
        boundary = phase.get('cutoff_day')
        if not data['hasNext'] or (boundary and days and min(days) < boundary):
            entry['pending'].pop(0)
            checkpoint()
            report['stop'] = 'exhausted' if not data['hasNext'] else 'previous_collection_day'
            continue
        cursor = {k: data.get('next' + k[0].upper() + k[1:]) for k in ('cursorId', 'cursorScore', 'cursorCount')}
        if not rows or cursor['cursorId'] is None:
            raise SourceError('다음 페이지가 있지만 리뷰 또는 커서가 없습니다.')
        phase.setdefault('visited', []).append(signature)
        phase['cursor'] = cursor
        checkpoint()
    report['complete'] = not entry['pending']
    if not report['complete']:
        report['stop'] = 'page_budget'
    return report


def collect(args, session=None):
    from scraper.crawler import OliveYoung, SourceError, AccessLimited, RateLimited, BudgetReached
    db = database()
    products = list(read_all(db, 'products', 'id,name'))
    known_products = {p['id'] for p in products}
    products = [p for p in products if not args.product or p['id'] in args.product]
    known = {str(r['id']) for r in read_all(db, 'reviews', 'id')}
    state_path, watermark_path = CACHE / 'latest-cursors.json', CACHE / 'latest-watermarks.json'
    state, watermarks = read_json(state_path, {}), read_json(watermark_path, {})
    history = read_json(CACHE / 'collection-history.json', {})
    products.sort(key=lambda p: (p['id'] not in state, str(watermarks.get(p['id'], history.get(p['id'], 0))), p['id']))
    api = OliveYoung(args.delay, session=session, max_seconds=args.max_seconds)
    report = {'started_at': utc_now(), 'dry_run': not args.write, 'products': [], 'errors': [], 'new_saved': 0}

    def checkpoint():
        if args.write:
            write_json(state_path, state)
            write_json(watermark_path, watermarks)
        report['finished_at'] = utc_now()
        write_json(CACHE / 'latest-report.json', report)

    for product in products:
        pid = product['id']
        item = {'id': pid, 'name': product['name'], 'new_saved': 0, 'would_insert': 0,
                'unknown_source_skipped': 0, 'unknown_source_ids': [], 'status': 'running'}
        report['products'].append(item)
        day = collection_day(watermarks.get(pid, history.get(pid)))
        state[pid] = prepare_cycle(state.get(pid), day, utc_now())
        checkpoint()

        def save(rows):
            accepted = [r for r in rows if r['product_id'] in known_products]
            item['unknown_source_skipped'] += len(rows) - len(accepted)
            item['unknown_source_ids'] = sorted(set(item['unknown_source_ids']) | {r['product_id'] for r in rows if r['product_id'] not in known_products})
            fresh = [r for r in accepted if r['id'] not in known]
            if args.write and fresh:
                saved = db.table('reviews').upsert(fresh, on_conflict='id', ignore_duplicates=True).execute().data or []
                item['new_saved'] += len(saved)
                report['new_saved'] += len(saved)
            elif not args.write:
                item['would_insert'] += len(fresh)
            known.update(r['id'] for r in accepted)

        try:
            result = harvest_since(api, pid, save, state[pid], checkpoint, args.max_review_pages)
            item.update(result)
            item['status'] = 'complete' if result['complete'] else 'partial'
            if result['complete']:
                watermarks[pid] = state[pid]['head_checked_at']
                del state[pid]
        except Exception as error:
            item['status'] = 'partial_or_failed'
            report['errors'].append({'id': pid, 'error': str(error) if isinstance(error, SourceError) else type(error).__name__})
            if isinstance(error, (AccessLimited, RateLimited, BudgetReached)):
                report['stop'] = type(error).__name__
                break
        finally:
            checkpoint()
        print(f"최신 리뷰 {pid}: {item['status']} · 신규 저장 {item['new_saved']}", flush=True)
    report['incomplete_products'] = sum(p['status'] != 'complete' for p in report['products'])
    checkpoint()
    return report
