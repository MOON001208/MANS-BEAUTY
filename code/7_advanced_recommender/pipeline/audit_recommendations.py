"""Audit stored claims against their actual review rows; no relevance labels implied."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared import CACHE, database, read_all, read_json, utc_now, write_json
from pipeline.profiles import ATTRIBUTES, VERSION, METADATA_REVISION, build_profile, extract_attributes


def audit(products, reviews):
    errors, samples, grouped = [], [], defaultdict(list)
    product_ids = {p['id'] for p in products}
    indexed = {str(r['id']): r for r in reviews}
    if len(product_ids) != len(products):
        errors.append({'issue': 'duplicate_product_id'})
    if len(indexed) != len(reviews):
        errors.append({'issue': 'duplicate_review_id'})
    for review in reviews:
        grouped[review['product_id']].append(review)
        if review['product_id'] not in product_ids:
            errors.append({'issue': 'orphan_review', 'review_id': str(review['id'])})
    references = 0
    for product in products:
        pid, meta = product['id'], product.get('profile_metadata') or {}
        def fail(issue):
            errors.append({'product_id': pid, 'issue': issue})
        if meta.get('version') != VERSION or meta.get('metadata_revision') != METADATA_REVISION:
            fail('stale_profile')
        if meta.get('analyzed_count') != len(grouped[pid]):
            fail('analyzed_count_mismatch')
        expected = build_profile(product, grouped[pid])
        # Independent row ownership and threshold checks below supplement replay.
        for field, value in expected.items():
            if field != 'profile_metadata' and product.get(field) != value:
                fail('recalculation_mismatch:' + field)
        for field in ['input_hash', 'evidence_counts', 'positive_concern_counts', 'negative_concern_counts',
                      'skin_review_counts', 'shade_source', 'shade_lineup']:
            if meta.get(field) != expected['profile_metadata'].get(field):
                fail('metadata_mismatch:' + field)
        claims = [(attr, (meta.get('evidence_review_ids') or {}).get(attr, []), False)
                  for attr in ATTRIBUTES if product.get(attr + '_score') is not None]
        claims += [(concern, (meta.get('concern_evidence_ids') or {}).get(concern, []), True)
                   for concern in product.get('suitable_concerns') or []]
        for claim, ids, concern in claims:
            if len(set(map(str, ids))) < 3:
                fail('claim_under_three:' + claim)
            for rid in ids:
                references += 1
                row = indexed.get(str(rid))
                if not row or row['product_id'] != pid:
                    fail('missing_or_foreign_evidence:' + claim + ':' + str(rid))
                    continue
                extracted = extract_attributes(row)
                matches = claim in extracted['positive_concerns'] if concern else extracted.get(claim) is not None
                if not matches:
                    fail('evidence_expression_mismatch:' + claim + ':' + str(rid))
                # Inspectable deterministic sample: one actual row per product/claim.
                if str(rid) == str(ids[0]):
                    samples.append({'product_id': pid, 'claim': claim, 'review_id': str(rid),
                                    'content': row.get('content', ''), 'rating': row.get('rating'),
                                    'extracted': extracted.get('positive_concerns') if concern else extracted['evidence'][claim]})
    ingredients = Counter((p.get('profile_metadata') or {}).get('ingredient_source', {}).get('status', 'unknown')
                          for p in products if (p.get('profile_metadata') or {}).get('ingredient_source') is not None)
    return {'audited_at': utc_now(), 'version': VERSION, 'metadata_revision': METADATA_REVISION,
            'products': len(products), 'reviews': len(reviews), 'evidence_references_checked': references,
            'products_without_reviews': sum(not grouped[p['id']] for p in products),
            'ingredient_statuses': dict(ingredients),
            'products_with_explicit_shades': sum(bool(p.get('suitable_shades')) for p in products),
            'products_with_lineup': sum(bool((p.get('profile_metadata') or {}).get('shade_lineup')) for p in products),
            'errors': errors, 'claim_samples': samples,
            'limitation': 'Row integrity and rule replay only; semantic samples still require human/model reading. No relevance accuracy or clinical safety measured.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, help='JSON containing products and reviews; otherwise reads DB')
    parser.add_argument('--output', type=Path, default=CACHE / 'recommendation-audit.json')
    args = parser.parse_args()
    if args.input:
        data = read_json(args.input, {})
    else:
        db = database()
        data = {'products': list(read_all(db, 'products')),
                'reviews': list(read_all(db, 'reviews', 'id,product_id,content,rating,skin_type,option_name'))}
    report = audit(data['products'], data['reviews'])
    write_json(args.output, report)
    print({key: value for key, value in report.items() if key not in ('claim_samples', 'errors', 'limitation')})
    print(f"오류 {len(report['errors'])}건 · 검토용 주장 표본 {len(report['claim_samples'])}개")
    return int(bool(report['errors']))


if __name__ == '__main__':
    raise SystemExit(main())
