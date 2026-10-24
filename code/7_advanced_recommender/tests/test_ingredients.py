import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scraper.ingredients import ingredient_listing, ingredient_patch
from pipeline.profiles import build_profile, input_hash, VERSION


def article(*items):
    return {'articleInfoList': [{'title': '화장품', 'items': list(items)}]}


class IngredientTests(unittest.TestCase):
    def test_verified_source_images_are_preserved_without_text_confirmation(self):
        product = {'id': 'p', 'profile_metadata': {}}
        patch, source = ingredient_patch(product, article({'title': '전성분', 'content': '상세페이지 참조'}),
            images=[{'label': '전성분 표', 'url': 'https://image.oliveyoung.co.kr/formula.jpg'}])
        self.assertEqual(source['status'], 'image_only')
        self.assertEqual(len(source['images']), 1)
        self.assertNotIn('ingredients_raw', patch)
        self.assertIsNone(build_profile({**product, **patch}, [])['ingredient_level'])
        refreshed, same = ingredient_patch({**product, **patch}, article({'title': '전성분', 'content': '상세페이지 참조'}), checked_at='later')
        self.assertEqual(same['images'], source['images'])
        self.assertEqual(same['checked_at'], source['checked_at'])
        self.assertEqual(same['status'], 'image_only')
    def test_shade_and_bundle_sections_are_preserved(self):
        data = article({'title': '화장품법에 따라 기재해야 하는 모든 성분',
                        'content': '[1호] 정제수, 글리세린<br>[3호] 정제수, 실리카'})
        listing = ingredient_listing(data, 'p')
        self.assertEqual(listing['status'], 'collected')
        self.assertEqual(len(listing['entries']), 1)
        self.assertIn('[1호]', listing['entries'][0]['text'])
        self.assertIn('\n[3호]', listing['entries'][0]['text'])

    def test_distinct_formulas_remain_distinct_entries(self):
        data = {'articleInfoList': [
            {'title': '본품', 'items': [{'title': '전성분', 'content': '정제수, 글리세린'}]},
            {'title': '증정품', 'items': [{'title': '전성분', 'content': '실리카, 마이카'}]},
        ]}
        result = ingredient_listing(data, 'p')
        self.assertEqual(len(result['entries']), 2)
        self.assertIn('본품', result['entries'][0]['label'])
        self.assertIn('증정품', result['entries'][1]['label'])

    def test_reference_and_caution_text_are_not_ingredient_lists(self):
        data = article({'title': '모든 성분', 'content': '상품 상세페이지 참조'},
                       {'title': '성분 사용시 주의사항', 'content': '붉은 반점, 자극, 가려움 시 중단'})
        result = ingredient_listing(data, 'p')
        self.assertEqual(result['status'], 'reference_only')
        self.assertEqual(result['entries'], [])
        self.assertEqual(len(result['references']), 1)

    def test_single_component_and_nul_are_supported(self):
        result = ingredient_listing(article({'title': '전성분', 'content': '실리카\x00'}), 'p')
        self.assertEqual(result['entries'][0]['text'], '실리카')

    def test_partial_listing_keeps_reference_for_unverified_component(self):
        result = ingredient_listing(article({'title': '전성분', 'content': '정제수, 글리세린'},
                                            {'title': '모든 성분', 'content': '상세페이지 참조'}), 'p')
        self.assertEqual(result['status'], 'partial')

    def test_ingestion_metadata_survives_profile_rebuild_without_version_change(self):
        product = {'id': 'p', 'profile_metadata': {'source_category': '파운데이션', 'version': VERSION}}
        patch, source = ingredient_patch(product, article({'title': '전성분', 'content': '정제수, 글리세린'}))
        updated = {**product, **patch}
        profile = build_profile(updated, [])
        self.assertEqual(profile['profile_metadata']['ingredient_source'], source)
        self.assertEqual(profile['profile_metadata']['source_category'], '파운데이션')
        self.assertEqual(profile['profile_metadata']['version'], VERSION)
        self.assertEqual(profile['ingredient_level'], '성분 확인')

    def test_reference_does_not_delete_old_text_or_claim_current_confirmation(self):
        product = {'id': 'p', 'ingredients_raw': '기존 성분', 'profile_metadata': {}}
        patch, _ = ingredient_patch(product, article({'title': '전성분', 'content': '상세페이지 참조'}))
        self.assertNotIn('ingredients_raw', patch)
        self.assertIsNone(build_profile({**product, **patch}, [])['ingredient_level'])

    def test_hash_tracks_listing_changes_but_not_check_time(self):
        product = {'id': 'p', 'profile_metadata': {}}
        patch, _ = ingredient_patch(product, article({'title': '전성분', 'content': '정제수, 글리세린'}))
        a = {**product, **patch}
        b = copy.deepcopy(a)
        b['profile_metadata']['ingredient_source']['checked_at'] = 'later'
        self.assertEqual(input_hash(a, []), input_hash(b, []))
        b['profile_metadata']['ingredient_source']['entries'][0]['text'] = '실리카'
        self.assertNotEqual(input_hash(a, []), input_hash(b, []))

    def test_unavailable_source_preserves_historical_text_without_confirmation(self):
        product = {'id': 'p', 'ingredients_raw': '기존 성분', 'profile_metadata': {}}
        patch, source = ingredient_patch(product, {}, unavailable=True)
        self.assertEqual(source['status'], 'unavailable')
        self.assertNotIn('ingredients_raw', patch)
        self.assertIsNone(build_profile({**product, **patch}, [])['ingredient_level'])


if __name__ == '__main__':
    unittest.main()
