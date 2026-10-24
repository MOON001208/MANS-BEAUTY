"""One command: catalog discovery -> review ingestion -> versioned profiles."""
import json
from scraper.crawler import parser, validate_args, run as crawl
from pipeline.build_profiles import run as profile
from shared import CACHE, utc_now, write_json

def main():
    p = parser()
    p.add_argument('--profiles-only', action='store_true')
    args = p.parse_args()
    validate_args(p, args)
    result = {'started_at': utc_now(), 'errors': []}
    if not args.profiles_only:
        try:
            result['crawl'] = crawl(args)
        except Exception as error:
            result['errors'].append({'stage': 'crawl', 'error': type(error).__name__})
    # Successfully stored pages remain usable even if other source requests failed.
    try:
        # A source query can return reviews owned by another known product.
        # Rebuild every affected profile rather than leaving related rows stale.
        result['profiles'] = profile(args.write, args.product if args.profiles_only else None)
    except Exception as error:
        result['profiles'] = {'updated': [], 'errors': [{'stage': 'profiles', 'error': type(error).__name__}]}
    result['finished_at'] = utc_now()
    write_json(CACHE / 'pipeline-report.json', result)
    errors = len(result['errors']) + len(result.get('crawl', {}).get('errors', [])) + len(result['profiles']['errors'])
    incomplete = result.get('crawl', {}).get('incomplete_products', 0)
    print(json.dumps({'errors': errors, 'incomplete_products': incomplete, 'profiles_updated': len(result['profiles']['updated'])}))
    return bool(errors or incomplete)

if __name__ == '__main__':
    raise SystemExit(main())
