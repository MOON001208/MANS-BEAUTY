"""How many collected products can actually tell a buyer which tone to pick.

Men's base makeup is bought to not look made up, so the shade decision is the
one the recommender has to get right. This reports, per product family, how far
each product gets: a shade on the 21/23/25 scale the quiz asks about, an order
within the product's own options, or nothing usable.

Tone-up and brightening products are counted apart: they lift overall tone and
ship in one shade, so having no shade is correct for them rather than missing.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared import CACHE, database, read_all, utc_now, write_json
from pipeline.profiles import shade_lineup

SINGLE_BY_NATURE = re.compile(r'톤업|브라이트닝|화이트닝|프라이머|선크림|에센스')
FAMILY = {'tone_lotion': '톤로션/커버로션/BB', 'cushion': '쿠션/파운데이션', 'concealer': '컨실러',
          'stick': '스틱', 'liquid': '기타 베이스'}
BUCKETS = [
    ('A', '21/23/25 명시'),
    ('B', '제품 내 밝기 순서 확보'),
    ('C', '호수 구조 파악, 재고 1종뿐'),
    ('D', '옵션은 있으나 호수 아님'),
    ('E', '옵션 데이터 없음 (본래 단일 호수)'),
    ('F', '옵션 데이터 없음 (커버 목적, 미확보)'),
]

def classify(product, review_options):
    """Bucket one product by how well its tone options are known."""
    meta = product.get('profile_metadata') or {}
    stored = meta.get('shade_lineup')
    if product.get('suitable_shades'):
        return 'A'
    if stored:
        return 'B'
    # Sold-out options leave the shade structure known but unbuyable.
    if shade_lineup(review_options):
        return 'C'
    if review_options:
        return 'D'
    return 'E' if SINGLE_BY_NATURE.search(product.get('name') or '') else 'F'

def run():
    db = database()
    products = list(read_all(db, 'products', 'id,name,product_type,suitable_shades,profile_metadata'))
    options = defaultdict(Counter)
    for review in read_all(db, 'reviews', 'id,product_id,option_name'):
        name = (review.get('option_name') or '').strip()
        if name:
            options[review['product_id']][name] += 1
    table = defaultdict(Counter)
    members = defaultdict(list)
    for product in products:
        bucket = classify(product, options.get(product['id'], Counter()))
        table[product.get('product_type') or 'liquid'][bucket] += 1
        members[bucket].append({'id': product['id'], 'name': product.get('name'),
                                'product_type': product.get('product_type')})
    report = {'generated_at': utc_now(), 'total': len(products),
              'buckets': {code: sum(table[f][code] for f in table) for code, _ in BUCKETS},
              'by_family': {f: dict(counts) for f, counts in table.items()},
              'members': members}
    write_json(CACHE / 'shade-coverage.json', report)
    families = sorted(table, key=lambda f: -sum(table[f].values()))
    print(f'수집 상품 {len(products)}개 — 톤 구분 현황\n')
    print(f"{'구분':<34}" + ''.join(f'{FAMILY.get(f, f):>20}' for f in families) + f"{'합계':>8}")
    print('-' * (34 + 20 * len(families) + 8))
    for code, label in BUCKETS:
        total = sum(table[f][code] for f in families)
        print(f'{code}. {label:<31}' + ''.join(f'{table[f][code]:>20}' for f in families) + f'{total:>8}')
    print('-' * (34 + 20 * len(families) + 8))
    print(f"{'합계':<34}" + ''.join(f'{sum(table[f].values()):>20}' for f in families) + f'{len(products):>8}')
    usable = sum(table[f][c] for f in families for c in 'AB')
    natural = sum(table[f]['E'] for f in families)
    print(f'\n톤 구분 가능 (A+B): {usable}/{len(products)} = {usable / len(products) * 100:.1f}%')
    if len(products) > natural:
        print(f'본래 단일 호수 {natural}개를 제외한 실질 분모 기준: '
              f'{usable}/{len(products) - natural} = {usable / (len(products) - natural) * 100:.1f}%')
    return report

if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    report = run()
    print(json.dumps({code: report['buckets'][code] for code, _ in BUCKETS}))
