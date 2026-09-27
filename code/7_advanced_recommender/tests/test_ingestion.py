import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scraper import crawler

class IngestionTests(unittest.TestCase):
    def run_pipeline(self, limited=False, related_failure=False, current_failure=False):
        db, api = MagicMock(), MagicMock()
        writes = []
        def table(name):
            query = MagicMock()
            def upsert(value, **kwargs):
                writes.append((name, value))
                return SimpleNamespace(execute=lambda: SimpleNamespace(data=value if isinstance(value, list) else [value]))
            query.upsert.side_effect = upsert
            return query
        db.table.side_effect = table
        def detail(pid):
            if current_failure and pid == 'p':
                raise crawler.SourceError('code=31502')
            if related_failure and pid == 'q':
                raise crawler.SourceError('단종 상품 상세 없음')
            return {'goodsNumber': pid, 'goodsName': '남성 쿠션', 'menCategoryFlag': True,
                    'standardCategory': {'middleCategoryName': '베이스 메이크업', 'lowerCategoryName': '쿠션'}}
        api.detail.side_effect = detail
        api.stats.return_value = {}
        if limited:
            api.reviews_page.side_effect = crawler.RateLimited('429')
        else:
            api.reviews_page.return_value = {'goodsReviewList': [{'reviewId': 1, 'reviewScore': 5, 'createdDateTime': '2026.09.17', 'goodsDto': {'goodsNumber': 'q'}}], 'hasNext': False}
        args = crawler.parser().parse_args(['--write', '--product', 'p', '--product', 'next', '--skip-ingredients'])
        with tempfile.TemporaryDirectory() as cache, patch.object(crawler, 'CACHE', Path(cache)), patch.object(crawler, 'database', return_value=db), patch.object(crawler, 'OliveYoung', return_value=api), patch.object(crawler, 'read_all', side_effect=lambda db, table, *a: [{'id': 'p'}] if table == 'products' else []):
            result = crawler.run(args)
        return result, writes, api

    def test_related_review_keeps_source_id_and_parent_is_saved_first(self):
        result, writes, _ = self.run_pipeline()
        self.assertEqual(result['errors'], [])
        reviews = [(i, value) for i, (name, value) in enumerate(writes) if name == 'reviews']
        self.assertEqual(len(reviews), 1)
        index, rows = reviews[0]
        self.assertEqual(rows[0]['product_id'], 'q')
        self.assertTrue(any(name == 'products' and value['id'] == 'q' for name, value in writes[:index]))
        self.assertEqual(result['products'][0]['cross_product_saved'], 1)

    def test_rate_limit_stops_remaining_products(self):
        result, _, api = self.run_pipeline(limited=True)
        self.assertEqual(result['stop'], 'RateLimited')
        api.detail.assert_called_once_with('p')

    def test_unavailable_related_product_skips_only_its_review(self):
        result, writes, _ = self.run_pipeline(related_failure=True)
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['products'][0]['cross_product_skipped'], 1)
        self.assertEqual(result['products'][0]['warnings'][0]['stage'], 'related_detail')
        self.assertFalse(any(name == 'reviews' for name, _ in writes))

    def test_known_product_can_collect_when_detail_is_unavailable(self):
        result, writes, _ = self.run_pipeline(current_failure=True)
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['products'][0]['warnings'][0]['stage'], 'detail')
        self.assertTrue(any(name == 'reviews' for name, _ in writes))

if __name__ == '__main__':
    unittest.main()
