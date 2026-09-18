"""Collect statements that map a brand's own shade number to the 21/23/25 scale.

A sentence naming only a cushion-scale shade describes the writer ("저는 23호를
쓰는데"), not the product. Only a sentence naming a brand shade *and* a cushion
shade states a mapping ("2호 라이언(23호)", "22-23호 분들은 2호로"). That rule is
what separates signal from self-description, and it is the same rule whether the
text comes from stored reviews or from YouTube.

Nothing here writes to the database: it produces a report to review, because a
wrong absolute shade is worse for a buyer than no absolute shade.
"""
from __future__ import annotations
import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared import CACHE, database, read_all, utc_now, write_json

CUSHION_SHADE = re.compile(r'(?<!\d)(19|2[0-9])\s*호')
BRAND_SHADE = re.compile(r'(?<!\d)([1-9])\s*호')
SCALE = [21, 23, 25]
MIN_STATEMENTS = 5

def mapping_statements(text):
    """Brand shade to cushion shade pairs stated in one piece of text."""
    pairs = []
    for sentence in re.split(r'[.!?\n]+', text or ''):
        cushions = [(m.start(), int(m.group(1))) for m in CUSHION_SHADE.finditer(sentence)]
        if not cushions:
            continue
        for match in BRAND_SHADE.finditer(sentence):
            # 21호 also matches the brand pattern at its second digit; skip those.
            if any(abs(match.start() - start) < 3 for start, _ in cushions):
                continue
            nearest = min(cushions, key=lambda c: abs(c[0] - match.start()))[1]
            pairs.append((int(match.group(1)), nearest))
    return pairs

def summarise(votes):
    """Median of the shades a brand number was compared to, snapped to the scale.

    The median suits this data because neighbouring shades disagree by one step,
    not at random: 21호 and 22호 are near-agreement, which a mode would discard.
    """
    summary = {}
    for brand, values in sorted(votes.items()):
        if len(values) < MIN_STATEMENTS:
            continue
        middle = statistics.median(values)
        summary[brand] = {'statements': len(values), 'median': middle,
                          'shade': str(min(SCALE, key=lambda s: abs(s - middle)))}
    # Two brand numbers resolving to one shade cannot tell a buyer them apart.
    shades = [entry['shade'] for entry in summary.values()]
    if len(summary) < 2 or len(set(shades)) != len(shades):
        return None
    # A brighter brand number must not resolve darker than a duller one.
    ordered = [summary[brand]['shade'] for brand in sorted(summary)]
    return summary if ordered == sorted(ordered) else None

def collect_from_reviews(db, product_ids=None):
    votes = defaultdict(lambda: defaultdict(list))
    for review in read_all(db, 'reviews', 'id,product_id,content'):
        if product_ids and review['product_id'] not in product_ids:
            continue
        for brand, cushion in mapping_statements(review.get('content')):
            votes[review['product_id']][brand].append(cushion)
    return votes

def run(product_ids=None, extra_texts=None):
    db = database()
    votes = collect_from_reviews(db, product_ids)
    for pid, texts in (extra_texts or {}).items():
        for text in texts:
            for brand, cushion in mapping_statements(text):
                votes[pid][brand].append(cushion)
    names = {p['id']: p.get('name') for p in read_all(db, 'products', 'id,name')}
    report = {'generated_at': utc_now(), 'min_statements': MIN_STATEMENTS,
              'accepted': {}, 'rejected': {}}
    for pid, brand_votes in votes.items():
        summary = summarise(brand_votes)
        target = report['accepted'] if summary else report['rejected']
        target[pid] = {'name': names.get(pid), 'shades': summary,
                       'raw': {brand: sorted(v) for brand, v in sorted(brand_votes.items())}}
    write_json(CACHE / 'shade-mapping-report.json', report)
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--product', action='append')
    parser.add_argument('--youtube', action='store_true',
                        help='also mine YouTube descriptions and comments (needs YOUTUBE_API_KEY)')
    args = parser.parse_args()
    extra = None
    if args.youtube:
        from pipeline.youtube_shades import collect_texts
        extra = collect_texts(args.product)
    result = run(args.product, extra)
    for pid, entry in result['accepted'].items():
        shades = ', '.join(f"{b}호→{v['shade']}호({v['statements']}건)" for b, v in entry['shades'].items())
        print(f"채택 {pid} {(entry['name'] or '')[:30]}: {shades}")
    print(json.dumps({'accepted': len(result['accepted']), 'rejected': len(result['rejected'])}))
