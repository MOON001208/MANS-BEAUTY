"""One command: catalog discovery -> review ingestion -> versioned profiles."""
import json
from scraper.crawler import parser, run as crawl
from pipeline.build_profiles import run as profile
from shared import CACHE, utc_now, write_json

def main():
    p = parser()
    p.add_argument('--profiles-only', action='store_true')
    args = p.parse_args()
    if args.max_review_pages < 2 or args.max_catalog_pages < 1 or args.delay < 0 or args.max_seconds <= 0:
        p.error('review pages >=2, catalog pages >=1, delay >=0 required')
    result = {'started_at': utc_now(), 'errors': []}
    if not args.profiles_only:
        try:
            result['crawl'] = crawl(args)
        except Exception as error:
            result['errors'].append({'stage': 'crawl', 'error': type(error).__name__})
    # Successfully stored pages remain usable even if other source requests failed.
    try:
        result['profiles'] = profile(args.write, args.product)
    except Exception as error:
        result['profiles'] = {'updated': [], 'errors': [{'stage': 'profiles', 'error': type(error).__name__}]}
    result['finished_at'] = utc_now()
    write_json(CACHE / 'pipeline-report.json', result)
    errors = len(result['errors']) + len(result.get('crawl', {}).get('errors', [])) + len(result['profiles']['errors'])
    print(json.dumps({'errors': errors, 'profiles_updated': len(result['profiles']['updated'])}))
    return bool(errors)

if __name__ == '__main__':
    raise SystemExit(main())
