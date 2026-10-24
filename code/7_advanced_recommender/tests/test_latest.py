import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scraper.latest import prepare_cycle, harvest_since
from scraper.crawler import SourceError
import run_pipeline


def page(ids, day, cursor=None, login=False):
    return {'goodsReviewList': [{'reviewId': i, 'reviewScore': 5, 'createdDateTime': day, 'content': '가벼워요'} for i in ids],
            'hasNext': cursor is not None, 'nextCursorId': cursor, 'nextCursorScore': None,
            'nextCursorCount': None, 'loginRequired': login}


class Api:
    def __init__(self, pages):
        self.pages, self.calls = pages, []
    def reviews_page(self, pid, sort, cursor):
        key = cursor['cursorId'] if cursor else None
        self.calls.append(key)
        return copy.deepcopy(self.pages[key])


class LatestTests(unittest.TestCase):
    def test_existing_ids_do_not_hide_gaps_on_later_pages(self):
        api = Api({None: page([1], '2026.10.24', 'a'), 'a': page([2], '2026.10.23', 'b'),
                   'b': page([3], '2026.10.21', 'c'), 'c': page([4], '2026.09.26', 'd')})
        inserted = []
        entry = prepare_cycle(None, '2026-09-27', '2026-10-24T00:00:00Z')
        result = harvest_since(api, 'p', lambda rows: inserted.extend(r['id'] for r in rows if r['id'] not in {'1', '2'}), entry)
        self.assertTrue(result['complete'])
        self.assertEqual(inserted, ['3', '4'])
        self.assertEqual(api.calls, [None, 'a', 'b', 'c'])

    def test_entire_boundary_day_is_included(self):
        api = Api({None: page([1], '2026.10.24', 'a'), 'a': page([2], '2026.10.23', 'b')})
        entry = prepare_cycle(None, '2026-10-24', '2026-10-24T12:00:00Z')
        result = harvest_since(api, 'p', lambda rows: None, entry)
        self.assertEqual(api.calls, [None, 'a'])
        self.assertTrue(result['complete'])

    def test_resume_scans_new_head_then_saved_older_cursor(self):
        previous = {'head_checked_at': '2026-10-24T00:00:00Z',
                    'pending': [{'cursor': {'cursorId': 'old'}, 'cutoff_day': '2026-09-27'}]}
        entry = prepare_cycle(previous, 'ignored', '2026-10-25T00:00:00Z')
        api = Api({None: page([9], '2026.10.23', 'a'), 'old': page([2], '2026.09.26', 'b')})
        result = harvest_since(api, 'p', lambda rows: None, entry)
        self.assertEqual(api.calls, [None, 'old'])
        self.assertTrue(result['complete'])
        self.assertEqual(previous['pending'][0]['cursor']['cursorId'], 'old')

    def test_failed_write_keeps_cursor_and_pending_segment(self):
        entry = prepare_cycle(None, '2026-09-27', '2026-10-24T00:00:00Z')
        original = copy.deepcopy(entry)
        api = Api({None: page([1], '2026.10.24', 'next')})
        with self.assertRaises(RuntimeError):
            harvest_since(api, 'p', lambda rows: (_ for _ in ()).throw(RuntimeError('db failure')), entry)
        self.assertEqual(entry, original)

    def test_login_gate_never_completes_or_advances_blocked_cursor(self):
        api = Api({None: page([1], '2026.10.24', 'blocked', login=True)})
        entry = prepare_cycle(None, '2026-09-27', '2026-10-24T00:00:00Z')
        result = harvest_since(api, 'p', lambda rows: None, entry)
        self.assertFalse(result['complete'])
        self.assertEqual(result['stop'], 'login_required')
        self.assertIsNone(entry['pending'][0]['cursor'])

    def test_budget_retains_next_cursor_without_claiming_completion(self):
        api = Api({None: page([1], '2026.10.24', 'a')})
        entry = prepare_cycle(None, '2026-09-27', '2026-10-24T00:00:00Z')
        result = harvest_since(api, 'p', lambda rows: None, entry, max_pages=1)
        self.assertFalse(result['complete'])
        self.assertEqual(entry['pending'][0]['cursor']['cursorId'], 'a')

    def test_bad_cursor_response_is_not_an_empty_success(self):
        api = Api({None: page([], '2026.10.24', 'a')})
        entry = prepare_cycle(None, None, '2026-10-24T00:00:00Z')
        with self.assertRaises(SourceError):
            harvest_since(api, 'p', lambda rows: None, entry)

    def test_pipeline_rebuilds_related_product_profiles(self):
        with TemporaryDirectory() as folder, patch.object(run_pipeline, 'CACHE', Path(folder)), \
                patch.object(sys, 'argv', ['run_pipeline', '--product', 'p', '--write']), \
                patch.object(run_pipeline, 'crawl', return_value={'errors': []}), \
                patch.object(run_pipeline, 'profile', return_value={'errors': [], 'updated': []}) as profiles:
            self.assertFalse(run_pipeline.main())
        profiles.assert_called_once_with(True, None)


if __name__ == '__main__':
    unittest.main()
