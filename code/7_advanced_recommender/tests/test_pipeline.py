import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scraper.crawler import harvest_reviews, normalize_review, is_target, parse_ingredients, product_from_detail, SourceError
from pipeline.profiles import build_profile, extract_attributes, get_shade_from_option, input_hash
from shared import read_all

def raw(rid, **kwargs):
    return {'reviewId': rid, 'reviewScore': 5, 'createdDateTime': '2026.09.17', 'content': '커버력이 좋아요', **kwargs}

def page(ids, cursor=None, login=False):
    return {'goodsReviewList': [raw(i) for i in ids], 'hasNext': cursor is not None,
            'nextCursorId': cursor, 'nextCursorScore': 1 if cursor else None,
            'nextCursorCount': 1 if cursor else None, 'loginRequired': login}

class FakeApi:
    def __init__(self, pages):
        self.pages, self.calls = pages, []
    def reviews_page(self, pid, sort, cursor):
        key = (sort, cursor.get('cursorId') if cursor else None)
        self.calls.append(key)
        return copy.deepcopy(self.pages[key])

class HarvestTests(unittest.TestCase):
    def test_all_sorts_deduplicate_without_early_stop(self):
        api = FakeApi({('new', None): page([1], 'next'), ('new', 'next'): page([2]), ('popular', None): page([1, 3])})
        saved = []
        result = harvest_reviews(api, 'p', saved.extend, {}, sorts=['new', 'popular'])
        self.assertEqual([r['id'] for r in saved], ['1', '2', '3'])
        self.assertEqual(result['unique_fetched'], 3)

    def test_existing_review_is_not_a_stop_marker(self):
        api = FakeApi({('new', None): page([1, 2])})
        inserted = []
        def save(rows):
            inserted.extend(r['id'] for r in rows if r['id'] != '1')
        harvest_reviews(api, 'p', save, {}, sorts=['new'])
        self.assertEqual(inserted, ['2'])

    def test_resume_checks_fresh_head_first(self):
        cursor = {'cursorId': 'old', 'cursorScore': 1, 'cursorCount': 1}
        state = {'p:new': cursor}
        api = FakeApi({('new', None): page([9], 'head'), ('new', 'old'): page([3], 'older')})
        harvest_reviews(api, 'p', lambda rows: None, state, max_pages=2, sorts=['new'])
        self.assertEqual(api.calls, [('new', None), ('new', 'old')])
        self.assertEqual(state['p:new']['cursorId'], 'older')

    def test_failed_write_does_not_advance_cursor(self):
        state = {}
        api = FakeApi({('new', None): page([1], 'next')})
        def save(rows):
            raise RuntimeError('db failed')
        with self.assertRaises(RuntimeError):
            harvest_reviews(api, 'p', save, state, sorts=['new'])
        self.assertEqual(state, {})

    def test_login_limit_stops_without_bypass(self):
        api = FakeApi({('new', None): page([1], 'next', login=True)})
        report = harvest_reviews(api, 'p', lambda rows: None, {}, sorts=['new'])
        self.assertEqual(len(api.calls), 1)
        self.assertEqual(report['sorts']['new']['stop'], 'login_required')

    def test_repeated_cursor_cannot_loop_forever(self):
        api = FakeApi({('new', None): page([1], 'next'), ('new', 'next'): page([1], 'next')})
        report = harvest_reviews(api, 'p', lambda rows: None, {}, sorts=['new'])
        self.assertEqual(len(api.calls), 2)
        self.assertEqual(report['sorts']['new']['stop'], 'repeated_cursor')

    def test_malformed_page_is_not_successful_end(self):
        api = FakeApi({('new', None): page([], 'next')})
        with self.assertRaises(SourceError):
            harvest_reviews(api, 'p', lambda rows: None, {}, sorts=['new'])

    def test_source_product_id_preserved(self):
        review = normalize_review(raw(1, goodsDto={'goodsNumber': 'variant'}), 'main')
        self.assertEqual(review['product_id'], 'variant')
        self.assertTrue(review['created_at'].endswith('+09:00'))
        self.assertIsNone(review['author'])

    def test_invalid_rating_is_rejected(self):
        with self.assertRaises(SourceError):
            normalize_review(raw(1, reviewScore=9), 'p')

class CatalogTests(unittest.TestCase):
    def test_mens_flag_not_brand_guess(self):
        detail = {'menCategoryFlag': True, 'standardCategory': {'lowerCategoryName': '쿠션'}}
        self.assertTrue(is_target(detail))
        self.assertFalse(is_target({**detail, 'menCategoryFlag': False}))
        self.assertFalse(is_target({'menCategoryFlag': True, 'standardCategory': {'lowerCategoryName': '샴푸'}}))

    def test_missing_stats_price_not_zeroed(self):
        product = product_from_detail('p', {'goodsNumber': 'p', 'goodsName': '테스트 쿠션'})
        self.assertNotIn('price', product)
        self.assertNotIn('review_count', product)
        self.assertNotIn('ingredients_raw', product)

    def test_ingredients_different_formulations_are_not_combined(self):
        data = [{'name': '전성분', 'content': '정제수, 글리세린, 나이아신아마이드'}, {'name': '전성분', 'content': '정제수, 글리세린, 향료, 에탄올'}]
        self.assertIsNone(parse_ingredients(data))

class ProfileTests(unittest.TestCase):
    def test_unknown_attributes_stay_null(self):
        p = build_profile({'id': 'p'}, [{'id': str(i), 'content': '배송이 빨라요', 'rating': 5} for i in range(5)])
        self.assertIsNone(p['coverage_score'])
        self.assertIsNone(p['compat_sensitive'])
        self.assertIsNone(p['ingredient_level'])

    def test_negative_review_is_not_a_benefit(self):
        reviews = [{'id': str(i), 'content': '여드름이 생겼어요. 모공이 안 가려져요.', 'rating': 1, 'skin_type': '지성', 'skin_trouble': '여드름,모공'} for i in range(10)]
        p = build_profile({'id': 'p'}, reviews)
        self.assertEqual(p['suitable_concerns'], [])
        self.assertEqual(p['suitable_skin_types'], [])

    def test_just_having_concern_is_not_a_benefit(self):
        p = build_profile({'id': 'p'}, [{'id': str(i), 'content': '저는 여드름 피부입니다', 'skin_trouble': '여드름', 'rating': 5} for i in range(5)])
        self.assertEqual(p['suitable_concerns'], [])

    def test_negation_does_not_become_positive(self):
        self.assertIsNone(extract_attributes({'content': '커버력이 좋지 않아요'})['coverage'])

    def test_mixed_attribute_stays_unknown(self):
        self.assertIsNone(extract_attributes({'content': '커버력이 좋아요. 하지만 커버력이 부족해요'})['coverage'])

    def test_explicit_positive_evidence(self):
        p = build_profile({'id': 'p'}, [{'id': str(i), 'content': '모공을 잘 커버해줘요. 지속력이 좋아요', 'rating': 5} for i in range(5)])
        self.assertIn('pore', p['suitable_concerns'])
        self.assertEqual(p['longevity_score'], 4)

    def test_shade_ambiguity_never_invents_number(self):
        for name in ['샌드베이지', '앰버베이지', '베이지', '1호', '21호+23호', '221호', '21ml']:
            self.assertIsNone(get_shade_from_option(name), name)
        for name in ['21호', '21N1', '23 내추럴', '25호 기획']:
            self.assertIsNotNone(get_shade_from_option(name), name)

    def test_source_options_override_old_reviews(self):
        p = build_profile({'id': 'p', 'source_options': [{'name': '23호', 'sold_out': False}, {'name': '25호', 'sold_out': True}]}, [{'id': '1', 'option_name': '21호'}])
        self.assertEqual(p['suitable_shades'], ['23'])

    def test_duplicate_ids_do_not_inflate_evidence(self):
        r = {'id': '1', 'content': '커버력이 좋아요', 'rating': 5}
        p = build_profile({'id': 'p'}, [r, r, r])
        self.assertEqual(p['profile_metadata']['analyzed_count'], 1)
        self.assertIsNone(p['coverage_score'])

    def test_edits_invalidate_fingerprint(self):
        a = input_hash({'id': 'p'}, [{'id': 'r', 'content': 'a'}])
        self.assertNotEqual(a, input_hash({'id': 'p'}, [{'id': 'r', 'content': 'b'}]))

class PaginationTests(unittest.TestCase):
    def test_reads_beyond_server_row_cap(self):
        rows = [{'id': str(i).zfill(4)} for i in range(1205)]
        class Query:
            def __init__(self): self.last = ''
            def select(self, *a): return self
            def order(self, *a): return self
            def limit(self, *a): return self
            def gt(self, key, last): self.last = last; return self
            def execute(self): return SimpleNamespace(data=[r for r in rows if r['id'] > self.last][:250])
        db = SimpleNamespace(table=lambda table: Query())
        self.assertEqual(len(list(read_all(db, 'reviews'))), 1205)

if __name__ == '__main__':
    unittest.main()
