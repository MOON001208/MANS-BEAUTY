import copy
import sys
from collections import Counter
from unittest import mock
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scraper.crawler import harvest_reviews, normalize_review, is_target, parse_ingredients, product_from_detail, SourceError
from pipeline import profiles
from pipeline.shade_mapping import mapping_statements, summarise
from pipeline.profiles import build_profile, extract_attributes, get_shade_from_option, input_hash, shade_lineup
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
        detail = {'menCategoryFlag': True,
                  'standardCategory': {'middleCategoryName': '베이스 메이크업', 'lowerCategoryName': '쿠션'}}
        self.assertTrue(is_target(detail))
        self.assertFalse(is_target({**detail, 'menCategoryFlag': False}))
        self.assertFalse(is_target({'menCategoryFlag': True,
                                    'standardCategory': {'middleCategoryName': '헤어케어', 'lowerCategoryName': '샴푸'}}))

    def test_every_base_makeup_kind_is_collected(self):
        # A name-keyword filter dropped these; the category keeps them in.
        for kind in ['컨실러', '파우더', '메이크업 베이스/프라이머', 'BB/CC', '파운데이션']:
            detail = {'menCategoryFlag': True,
                      'standardCategory': {'middleCategoryName': '베이스 메이크업', 'lowerCategoryName': kind}}
            self.assertTrue(is_target(detail), kind)

    def test_other_makeup_families_are_not_collected(self):
        for middle in ['립 메이크업', '아이 메이크업']:
            detail = {'menCategoryFlag': True, 'standardCategory': {'middleCategoryName': middle}}
            self.assertFalse(is_target(detail), middle)
        # A product already stored stays in scope so its data keeps refreshing.
        self.assertTrue(is_target({'menCategoryFlag': False, 'standardCategory': {}}, known=True))

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

    def test_lineup_orders_brand_numbering_without_claiming_a_cushion_shade(self):
        lineup = shade_lineup(Counter({'[본품+10ml 증정] 02 내추럴베이지': 213, '[본품] 01 라이트베이지': 39}))
        self.assertEqual(lineup['basis'], 'number')
        self.assertEqual([o['label'] for o in lineup['options']], ['01 라이트베이지', '02 내추럴베이지'])
        self.assertEqual([o['position'] for o in lineup['options']], [0.0, 1.0])
        # The brand's own numbering must never be reported as a 21/23/25 shade.
        self.assertIsNone(get_shade_from_option('01 라이트베이지'))

    def test_lineup_orders_colour_names_only_when_each_is_a_distinct_brightness(self):
        ordered = shade_lineup(Counter({'매치업 샌드': 5, '매치업 베이지': 7, '매치업 탄': 2}))
        self.assertEqual([o['label'] for o in ordered['options']], ['매치업 베이지', '매치업 샌드', '매치업 탄'])
        # Salmon and green are tint purposes, not a light-to-dark range.
        self.assertIsNone(shade_lineup(Counter({'살몬 베이지': 4, '그린 베이지': 3})))
        # Amber is the deeper of the two golden tones, so the pair does order.
        amber = shade_lineup(Counter({'앰버베이지': 3, '샌드 베이지': 6}))
        self.assertEqual([o['label'] for o in amber['options']], ['샌드 베이지', '앰버베이지'])

    def test_numbering_alone_is_not_a_shade(self):
        # 01/02/03 here number product variants, so no tone order may be claimed.
        self.assertIsNone(shade_lineup(Counter({'01 코어썸': 9, '02 네추럴썸': 7, '03 체인지썸': 4})))

    def test_packaging_variants_of_one_shade_share_a_rung(self):
        lineup = shade_lineup(Counter({'[본품]1호': 20, '본품 1호': 9, '[본품]2호': 19, '본품 2호': 12}))
        self.assertEqual([o['position'] for o in lineup['options']], [0.0, 1.0])
        self.assertEqual([o['label'] for o in lineup['options']], ['1호', '2호'])

    def test_lineup_rejects_volume_and_bundle_variants(self):
        self.assertIsNone(shade_lineup(Counter({'트루 톤 로션 오리지널': 8, '트루 톤 로션 오리지널+10ml 증정기획': 4})))
        self.assertIsNone(shade_lineup(Counter({'[단품]55ml 스킨톤 필터로션': 3, '[기획]55ml+10ml 스킨톤 필터로션': 2})))

    def test_lineup_needs_at_least_two_distinct_shades(self):
        self.assertIsNone(shade_lineup(Counter({'1호': 5})))
        # Packaging differences collapse to one shade, which offers no choice.
        self.assertIsNone(shade_lineup(Counter({'[본품] 1호': 5, '[기획] 1호': 3})))

    def test_sold_out_catalog_options_stay_out_of_the_lineup(self):
        product = {'id': 'p', 'source_options': [
            {'name': '1호', 'sold_out': False}, {'name': '2호', 'sold_out': True}]}
        self.assertIsNone(build_profile(product, [])['profile_metadata']['shade_lineup'])

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

    def test_metadata_shape_change_invalidates_fingerprint(self):
        # A stored profile missing newly added metadata must not be skipped as unchanged.
        product, reviews = {'id': 'p'}, [{'id': 'r', 'content': 'a'}]
        stored = input_hash(product, reviews)
        with mock.patch.object(profiles, 'METADATA_REVISION', profiles.METADATA_REVISION + 1):
            self.assertNotEqual(stored, profiles.input_hash(product, reviews))

    def test_suitable_concern_names_its_evidence_reviews(self):
        reviews = [{'id': str(i), 'content': '모공을 잘 가려줘요', 'rating': 5} for i in range(4)]
        p = build_profile({'id': 'p'}, reviews)
        self.assertIn('pore', p['suitable_concerns'])
        self.assertEqual(p['profile_metadata']['concern_evidence_ids']['pore'], ['0', '1', '2', '3'])

    def test_concern_evidence_is_capped_and_never_from_negative_reviews(self):
        good = [{'id': 'g%d' % i, 'content': '모공을 잘 가려줘요', 'rating': 5} for i in range(9)]
        bad = [{'id': 'b1', 'content': '모공이 더 심해졌어요', 'rating': 1}]
        ids = build_profile({'id': 'p'}, good + bad)['profile_metadata']['concern_evidence_ids']['pore']
        self.assertEqual(len(ids), 5)
        self.assertNotIn('b1', ids)

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


class ShadeMappingTests(unittest.TestCase):
    def test_self_description_is_not_a_mapping(self):
        # The writer's own shade says nothing about which option this product is.
        self.assertEqual(mapping_statements('저는 23호를 쓰는데 노란끼가 빠졌어요'), [])
        self.assertEqual(mapping_statements('23~25호 톤의 어두운 피부톤이에요'), [])

    def test_stated_mapping_is_extracted(self):
        self.assertEqual(mapping_statements('3호 제프리(25호)가 어둡고, 2호 라이언(23호)는'),
                         [(3, 25), (2, 23)])
        self.assertEqual(mapping_statements('22-23호 분들은 2호로 가시면 됩니다'), [(2, 23)])

    def test_cushion_shade_is_not_read_as_a_brand_shade(self):
        # 21호 contains a 1 followed by 호; it must not also count as brand 1호.
        self.assertEqual(mapping_statements('21호 쓰는 사람입니다'), [])

    def test_median_survives_neighbouring_disagreement(self):
        summary = summarise({1: [21, 21, 22, 21, 19, 23], 2: [23, 23, 24, 23, 22]})
        self.assertEqual(summary[1]['shade'], '21')
        self.assertEqual(summary[2]['shade'], '23')

    def test_thin_or_indistinguishable_evidence_is_refused(self):
        self.assertIsNone(summarise({1: [21, 21], 2: [23] * 6}))
        # Both options landing on one shade cannot tell a buyer them apart.
        self.assertIsNone(summarise({1: [23] * 6, 2: [23] * 6}))
        # A single rung states no range.
        self.assertIsNone(summarise({2: [23] * 9}))

    def test_order_must_not_invert(self):
        # A lower brand number resolving darker than a higher one is incoherent.
        self.assertIsNone(summarise({1: [25] * 6, 2: [21] * 6}))
