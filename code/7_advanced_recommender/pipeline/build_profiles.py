"""Build versioned profiles from all stored reviews, without Gemini or paid APIs."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared import CACHE, database, read_all, utc_now, write_json
from pipeline.profiles import build_profile, input_hash, VERSION

def run(write=False, product_ids=None):
    db = database()
    # Fail before writing anything if the migration has not been applied.
    if write:
        db.table('products').select('id,profile_metadata,source_options').limit(1).execute()
    products = [p for p in read_all(db, 'products') if not product_ids or p['id'] in product_ids]
    report = {'started_at': utc_now(), 'provider': VERSION, 'dry_run': not write, 'updated': [], 'unchanged': [], 'errors': []}
    for product in products:
        pid = product['id']
        try:
            reviews = list(read_all(db, 'reviews', 'id,content,rating,skin_type,option_name', {'product_id': pid}))
            fingerprint = input_hash(product, reviews)
            if (product.get('profile_metadata') or {}).get('input_hash') == fingerprint:
                report['unchanged'].append(pid)
                continue
            profile = build_profile(product, reviews)
            profile['profile_metadata']['analyzed_at'] = utc_now()
            if write:
                response = db.table('products').update(profile).eq('id', pid).execute()
                if not response.data:
                    raise RuntimeError('프로필 갱신 결과 0행')
            write_json(CACHE / 'profiles' / f'{pid}.json', profile)
            report['updated'].append({'id': pid, 'reviews': len(reviews), 'evidence': profile['profile_metadata']['evidence_counts']})
        except Exception as error:
            report['errors'].append({'id': pid, 'error': type(error).__name__})
        finally:
            report['finished_at'] = utc_now()
            write_json(CACHE / 'profile-report.json', report)
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--product', action='append')
    args = parser.parse_args()
    result = run(args.write, args.product)
    print(json.dumps({k: len(result[k]) for k in ['updated', 'unchanged', 'errors']}))
    raise SystemExit(1 if result['errors'] else 0)
