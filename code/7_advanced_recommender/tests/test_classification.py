import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.audit_recommendations import audit
from pipeline.classification import (
    classify_product,
    evaluate_recommendation_eligibility,
    infer_static_product_type,
    primary_product_name,
    verified_seller_formulation,
)
from pipeline.profiles import build_profile, input_hash
from scraper.crawler import product_from_detail


def rev(rid, content, option_name=''):
    return {'id': str(rid), 'product_id': 'p', 'content': content, 'rating': 5, 'option_name': option_name}


class FormulationClassificationTests(unittest.TestCase):
    def test_obge_pro_14g_with_gift_30ml_is_stick_not_liquid(self):
        product = {
            'id': 'A000000258285',
            'name': '[1등파데 리뉴얼] 오브제 내추럴 커버 파운데이션 PRO 14g 단품/기획 (+올인원 30ml 증정)',
            'profile_metadata': {'source_category': '파운데이션'},
            'source_options': [
                {'name': '[기획] 프로 1호 (+올인원 30ml)', 'sold_out': False},
                {'name': '[단품] 프로 1호', 'sold_out': False},
            ],
        }
        # Gift volume (+올인원 30ml 증정) must never trigger liquid classification.
        self.assertEqual(infer_static_product_type(product['name'], '파운데이션'), 'foundation_unknown')
        reviews = [
            rev(1, '스틱형으로 쓰기도 편하고 그립감이 좋아요'),
            rev(2, '스틱파데라서 편하게 베이스하기 좋아요'),
            rev(3, '상단을 돌려서 꺼내 쓰는 고체 스틱이라 손에 안 묻어요'),
        ]
        profile = build_profile(product, reviews)
        self.assertEqual(profile['product_type'], 'stick')
        self.assertEqual(profile['profile_metadata']['formulation']['status'], 'confirmed')
        self.assertEqual(profile['profile_metadata']['formulation']['basis'], 'reviews')
        self.assertEqual(profile['profile_metadata']['formulation']['evidence_review_ids'], ['1', '2', '3'])
        self.assertTrue(profile['profile_metadata']['recommendation_eligibility']['eligible'])

    def test_beready_blue_foundation_35ml_is_liquid(self):
        product = {
            'id': 'A000000178092',
            'name': '[남성파데1위] 비레디 블루 파운데이션 35ml',
            'profile_metadata': {'source_category': '파운데이션'},
            'source_options': [{'name': '2호', 'sold_out': False}],
        }
        reviews = [
            rev(1, '펌핑 두번 정도만 써도 얼굴 전체에 잘 발려요'),
            rev(2, '가격이 오른 대신 펌프식이라 편하네요'),
            rev(3, '스틱같은건 매트해보여서 액체 재질로 구매해봤어요'),
        ]
        profile = build_profile(product, reviews)
        self.assertEqual(profile['product_type'], 'liquid')
        self.assertEqual(profile['profile_metadata']['formulation']['status'], 'confirmed')
        self.assertEqual(profile['profile_metadata']['formulation']['basis'], 'reviews')
        self.assertTrue(profile['profile_metadata']['recommendation_eligibility']['eligible'])

    def test_builtin_brush_alone_never_classifies_liquid_bottle_as_stick(self):
        # Liquid bottles can also have built-in/rear brushes (e.g. 라끌랑 203000);
        # tool-only mentions must not count as solid stick formulation evidence.
        product = {
            'id': 'p_brush_only',
            'name': '테스트 커버 파운데이션 30ml',
            'profile_metadata': {'source_category': '파운데이션'},
        }
        reviews = [
            rev(1, '내장 브러쉬가 있어서 펴바르기 편해요'),
            rev(2, '뒤에 달린 브러쉬가 부드러워서 좋아요'),
            rev(3, '일체형 브러시라 손에 안 묻어요'),
            rev(4, '하단에 브러시가 내장되어 있어서 편해요'),
        ]
        profile = build_profile(product, reviews)
        self.assertEqual(profile['product_type'], 'foundation_unknown')
        self.assertEqual(profile['profile_metadata']['formulation']['counts'], {'stick': 0, 'liquid': 0, 'mixed': 0})

    def test_verified_seller_formulations_resolve_four_audited_skus_with_sources(self):
        cases = [
            ('A000000203000', '라끌랑 올데이 픽싱 커버 파운데이션 30ml (1호/2호) 2종 택1', None, 'liquid'),
            ('A000000210307', '듀이셀 트루빔 파운데이션 12g 기획(+토너패드 20매)', '파운데이션', 'stick'),
            ('A000000222827', '[1위파데] 그라펜 팁 스케치 멀티 커버 파운데이션 20ml 기획 (+팩클렌저 30ml)', '파운데이션', 'liquid'),
            ('A000000224891', '[첫구매전용] 그라펜 팁 스케치 멀티 커버 파운데이션 20ml (2종 택1)', '파운데이션', 'liquid'),
        ]
        for pid, name, sc, expected in cases:
            with self.subTest(pid=pid):
                product = {
                    'id': pid,
                    'name': name,
                    'category': '쿠션/파운데이션',
                    'product_type': 'cushion',
                    'profile_metadata': {'source_category': sc},
                }
                profile = build_profile(product, [])
                form = profile['profile_metadata']['formulation']
                self.assertEqual(profile['product_type'], expected)
                self.assertEqual(form['status'], 'confirmed')
                self.assertEqual(form['basis'], 'seller_verified')
                self.assertTrue(form['source_url'].startswith('https://image.oliveyoung.co.kr/'))
                self.assertTrue(form['verified_fact'])
                self.assertTrue(profile['profile_metadata']['recommendation_eligibility']['eligible'])
                self.assertEqual(input_hash(product, []), input_hash({**product, **profile}, []))

    def test_verified_seller_formulation_requires_matching_primary_name(self):
        # If Olive Young changes the product behind an existing SKU ID, the verified
        # record must not silently apply to a different product.
        self.assertIsNone(verified_seller_formulation('A000000203000', '라끌랑 다른 신제품 파운데이션 15g'))
        changed = {
            'id': 'A000000203000',
            'name': '라끌랑 다른 신제품 파운데이션 15g',
            'profile_metadata': {'source_category': '파운데이션'},
        }
        profile = build_profile(changed, [])
        self.assertEqual(profile['product_type'], 'foundation_unknown')
        self.assertEqual(profile['profile_metadata']['formulation']['basis'], 'insufficient_evidence')

    def test_gift_volume_promo_and_puff_never_guess_formulation(self):
        cases = [
            ('[피부착붙컬러] 그라펜 매치업 파운데이션 40ml 23 샌드 기획 (+엣지컷 퍼프)', '파운데이션'),
            ('[1등파데] 오브제 내추럴 커버 파운데이션 단품/기획(+클렌징폼 50ml)', '파운데이션'),
            ('테스트 파운데이션 12g 기획(+토너패드 20매)', '파운데이션'),
            ('테스트 멀티 커버 파운데이션 20ml (2종 택1)', '파운데이션'),
        ]
        for name, sc in cases:
            with self.subTest(name=name):
                self.assertEqual(infer_static_product_type(name, sc), 'foundation_unknown')
                profile = build_profile({'id': 'p_unverified', 'name': name, 'profile_metadata': {'source_category': sc}}, [])
                self.assertEqual(profile['product_type'], 'foundation_unknown')
                self.assertEqual(profile['profile_metadata']['formulation']['status'], 'unconfirmed')
                self.assertEqual(profile['profile_metadata']['formulation']['basis'], 'insufficient_evidence')

    def test_insufficient_review_evidence_stays_foundation_unknown(self):
        product = {
            'id': 'p_thin_reviews',
            'name': '테스트 트루빔 파운데이션 12g 기획(+토너패드 20매)',
            'profile_metadata': {'source_category': '파운데이션'},
        }
        reviews = [
            rev(1, '스틱이라 편해요'),
            rev(2, '고체 제형이라 묻어나지 않아요'),
        ]
        profile = build_profile(product, reviews)
        self.assertEqual(profile['product_type'], 'foundation_unknown')
        self.assertEqual(profile['profile_metadata']['formulation']['basis'], 'insufficient_evidence')
        self.assertTrue(profile['profile_metadata']['recommendation_eligibility']['eligible'])

    def test_mixed_stick_and_liquid_reviews_stay_foundation_unknown(self):
        product = {
            'id': 'p_mixed_reviews',
            'name': '테스트 하이브리드 파운데이션 20ml 기획 (+팩클렌저 30ml)',
            'profile_metadata': {'source_category': '파운데이션'},
        }
        reviews = [
            rev(1, '스틱형으로 돌려서 나오는 파데라서 편해요'),
            rev(2, '스틱 형태라 쓱쓱 발라주기 좋아요'),
            rev(3, '스틱형이라 휴대성이 좋아요'),
            rev(4, '액체 제형이라 촉촉하게 발려요'),
            rev(5, '리퀴드 파데라서 밀착이 좋아요'),
            rev(6, '액체형 커버 파운데이션이라 부드러워요'),
        ]
        profile = build_profile(product, reviews)
        self.assertEqual(profile['product_type'], 'foundation_unknown')
        self.assertEqual(profile['profile_metadata']['formulation']['basis'], 'mixed_evidence')
        self.assertTrue(profile['profile_metadata']['recommendation_eligibility']['eligible'])

    def test_conflicting_main_ml_and_stick_reviews_fixes_stale_cushion(self):
        product = {
            'id': 'p_conflict_ml',
            'name': '테스트 올데이 픽싱 커버 파운데이션 30ml (1호/2호) 2종 택1',
            'category': '쿠션/파운데이션',
            'product_type': 'cushion',
            'profile_metadata': {'source_category': None},
        }
        reviews = [
            rev(1, '스틱이기에 중간에 수정해주면 좋아요'),
            rev(2, '스틱이라 휴대성이 편해요'),
            rev(3, '특히 스틱 타입이라 들고 다니기 편해요'),
        ]
        profile = build_profile(product, reviews)
        self.assertEqual(profile['product_type'], 'foundation_unknown')
        self.assertEqual(profile['profile_metadata']['formulation']['basis'], 'conflicting_evidence')
        self.assertTrue(profile['profile_metadata']['recommendation_eligibility']['eligible'])

    def test_comparison_youtube_and_lipstick_do_not_create_false_evidence(self):
        product = {
            'id': 'p',
            'name': '테스트 커버 파운데이션',
            'profile_metadata': {'source_category': '파운데이션'},
        }
        reviews = [
            rev(1, '유튜브 광고 보고 구매했어요. 립스틱이랑 같이 샀어요.'),
            rev(2, '기존에 쓰던 스틱 파운데이션보다 촉촉해요. 묽지 않아요.'),
            rev(3, '타사 리퀴드 파운데이션보다 밀착력이 좋고 펌프식이 아니라 아쉬워요.'),
            rev(4, '유튜브에서 추천해서 샀는데 흘러내리지 않아요.'),
        ]
        profile = build_profile(product, reviews)
        self.assertEqual(profile['product_type'], 'foundation_unknown')
        self.assertEqual(profile['profile_metadata']['formulation']['counts'], {'stick': 0, 'liquid': 0, 'mixed': 0})

    def test_products_only_refresh_preserves_review_confirmed_and_uses_seller_verified(self):
        existing = {
            'id': 'A000000258285',
            'name': '[1등파데 리뉴얼] 오브제 내추럴 커버 파운데이션 PRO 14g 단품/기획 (+올인원 30ml 증정)',
            'product_type': 'stick',
            'profile_metadata': {
                'source_category': '파운데이션',
                'formulation': {'status': 'confirmed', 'basis': 'reviews', 'evidence_review_ids': ['1', '2', '3']},
            },
        }
        detail = {
            'goodsNumber': 'A000000258285',
            'goodsName': existing['name'],
            'standardCategory': {'lowerCategoryName': '파운데이션'},
        }
        refreshed = product_from_detail('A000000258285', detail, existing)
        self.assertEqual(refreshed['product_type'], 'stick')

        verified_detail = {
            'goodsNumber': 'A000000210307',
            'goodsName': '듀이셀 트루빔 파운데이션 12g 기획(+토너패드 20매)',
            'standardCategory': {'lowerCategoryName': '파운데이션'},
        }
        self.assertEqual(product_from_detail('A000000210307', verified_detail)['product_type'], 'stick')

    def test_primary_product_name_keeps_spf_and_one_plus_one(self):
        self.assertIn('SPF50+PA+++', primary_product_name('오브제 퍼펙트 옴므 쿠션 15g (SPF50+PA+++)'))
        self.assertIn('1+1', primary_product_name('비레디 트루 톤 로션 33ml 1+1 기획'))
        self.assertNotIn('30ml', primary_product_name('오브제 내추럴 커버 파운데이션 PRO 14g 단품/기획 (+올인원 30ml 증정)'))


class EligibilityAndMixedSetTests(unittest.TestCase):
    def test_single_product_promos_and_simple_gifts_are_preserved(self):
        promos = [
            ('[1등파데 리뉴얼] 오브제 내추럴 커버 파운데이션 PRO 14g 단품/기획 (+올인원 30ml 증정)', '파운데이션'),
            ('[1등파데] 오브제 내추럴 커버 파운데이션 단품/기획(+클렌징폼 50ml)', '파운데이션'),
            ('[피부착붙컬러] 그라펜 매치업 파운데이션 40ml 23 샌드 기획 (+엣지컷 퍼프)', '파운데이션'),
            ('듀이셀 트루빔 파운데이션 12g 기획(+토너패드 20매)', '파운데이션'),
            ('[1위파데] 그라펜 팁 스케치 멀티 커버 파운데이션 20ml 기획 (+팩클렌저 30ml)', '파운데이션'),
            ('다슈 맨즈 톤 컨트롤 커버로션 65ml 기획 (+클렌징오일 20ml) 2종', 'BB/CC'),
            ('[덱스PICK/1등 커버로션] 오브제 내추럴 커버 로션 50g 단품/기획(+미니어처 10ml)', 'BB/CC'),
            ('[모공&잡티 완벽커버] 미닉 미니멀 커버 로션 40ml 단품/기획세트', 'BB/CC'),
            ('비레디 트루 톤 로션 33ml 1+1 기획 2종 택1 (오리지널/에어리)', 'BB/CC'),
            ('[임수빈 PICK] 비레디 트루톤 로션 40ml + 20ml 추가증정 기획', 'BB/CC'),
            ('[하나로 끝내는] 원오브뎀 드 뗑 톤 로션 50ml 기획(+톤 로션 10ml)', 'BB/CC'),
            ('[OY단독/밀착쿠션] 정샘물 맨 슬림핏 누더 쿠션 (본품+리필)', '쿠션'),
            ('아이오페 맨 올데이 퍼펙트 톤업 올인원 120ml 기획(+30ml)', '올인원'),
        ]
        for name, sc in promos:
            with self.subTest(name=name):
                _, _, elig = classify_product({'id': 'p', 'name': name, 'profile_metadata': {'source_category': sc}}, [])
                self.assertTrue(elig['eligible'], elig)
                self.assertIsNone(elig['exclusion_reason'])

    def test_mixed_sets_are_excluded(self):
        mixed = [
            ('A000000249713', '[기프트패키지] [맨즈선물NO.1] 오브제 베스트커버 2종 기획 (커버 로션+무드체인지 레드립밤)', 'BB/CC'),
            ('A000000249714', '[기프트패키지] [맨즈 메이크업 NO.1] 오브제 보송커버 2종 기획 (파운데이션 2호 + 오일 컨트롤 피니셔)', '파운데이션'),
            ('A000000249774', '[기프트세트] 다슈 맨즈 톤 컨트롤 로션 02 뉴트럴 베이지 + 다슈 맨즈 워터 스냅 컬러 립밤 4g', 'BB/CC'),
            ('A000000249778', '[기프트세트] 다슈 맨즈 멀티 커버 스틱 파운데이션 2호 + 다슈 맨즈 컬러체인지 립밤 (쿨레드)', '파운데이션'),
            ('A000000182290', '다슈 맨즈 멀티 커버 스틱 파운데이션 12g 뉴트럴베이지 기획(+아이브로우 펜슬 네추럴그레이', '파운데이션'),
        ]
        for pid, name, sc in mixed:
            with self.subTest(pid=pid):
                ptype, _, elig = classify_product({'id': pid, 'name': name, 'profile_metadata': {'source_category': sc}}, [])
                self.assertFalse(elig['eligible'])
                self.assertEqual(elig['exclusion_reason'], 'mixed_set')
                if pid == 'A000000249714':
                    self.assertEqual(ptype, 'foundation_unknown')

    def test_lip_primary_products_are_excluded(self):
        by_category = {'id': 'p', 'name': '남성 생기 밤', 'profile_metadata': {'source_category': '립 메이크업'}}
        ptype, _, elig = classify_product(by_category, [])
        self.assertEqual(ptype, 'lip')
        self.assertFalse(elig['eligible'])
        self.assertEqual(elig['exclusion_reason'], 'lip_primary')

        by_name = {'id': 'p', 'name': '오브제 무드체인지 레드립밤 3g'}
        ptype2, _, elig2 = classify_product(by_name, [])
        self.assertEqual(ptype2, 'lip')
        self.assertFalse(elig2['eligible'])
        self.assertEqual(elig2['exclusion_reason'], 'lip_primary')

    def test_lip_contaminated_review_pool_is_excluded_while_minor_lip_promo_is_preserved(self):
        contaminated_product = {
            'id': 'A000000204828',
            'name': '듀이셀 큐라톤즈 모이스처 40ml 기획',
            'profile_metadata': {'source_category': 'BB/CC'},
        }
        contaminated_reviews = [
            rev(i, '남자 립밤으로 구매했는데 입술 발색이 자연스러워요', '01 코어썸') for i in range(6)
        ] + [
            rev(i + 10, '톤업 로션처럼 부드럽게 발려요', '큐라톤즈 본품') for i in range(4)
        ]
        profile = build_profile(contaminated_product, contaminated_reviews)
        elig = profile['profile_metadata']['recommendation_eligibility']
        self.assertFalse(elig['eligible'])
        self.assertEqual(elig['exclusion_reason'], 'lip_contaminated_reviews')
        self.assertTrue(len(elig['evidence_review_ids']) >= 5)

        cushion = {
            'id': 'A000000212063',
            'name': '[맨즈 1위 쿠션] 비레디 블루 쿠션',
            'profile_metadata': {'source_category': '쿠션'},
            'source_options': [{'name': '[본품]2호', 'sold_out': False}],
        }
        cushion_reviews = [rev(0, '사은품 생기 립밤도 잘 써요')] + [
            rev(i + 1, '쿠션 커버력이 자연스러워요') for i in range(19)
        ]
        cushion_elig = build_profile(cushion, cushion_reviews)['profile_metadata']['recommendation_eligibility']
        self.assertTrue(cushion_elig['eligible'])

    def test_standalone_options_with_one_promo_option_remain_eligible(self):
        product = {
            'id': 'A000000229158',
            'name': '[누적판매 26만개] 다슈 맨즈 멀티 커버 스틱 파운데이션',
            'profile_metadata': {'source_category': '파운데이션'},
            'source_options': [
                {'name': '파운데이션 1호', 'sold_out': False},
                {'name': '파운데이션 2호+아이브로우 펜슬', 'sold_out': False},
            ],
        }
        elig = evaluate_recommendation_eligibility(product, [], resolved_type='stick')
        self.assertTrue(elig['eligible'])

    def test_input_hash_idempotent_and_audit_verifies_new_evidence_ids(self):
        product = {
            'id': 'p',
            'name': '오브제 내추럴 커버 파운데이션 PRO 14g 단품/기획 (+올인원 30ml 증정)',
            'profile_metadata': {'source_category': '파운데이션'},
        }
        reviews = [
            rev(1, '스틱형이라 편해요'),
            rev(2, '스틱파데라 휴대하기 좋아요'),
            rev(3, '고체 스틱이라 손에 안 묻어요'),
        ]
        profile = build_profile(product, reviews)
        merged = {**product, **profile}
        self.assertEqual(input_hash(product, reviews), input_hash(merged, reviews))
        self.assertEqual(audit([merged], reviews)['errors'], [])

        damaged = copy.deepcopy(merged)
        damaged['profile_metadata']['formulation']['evidence_review_ids'][0] = 'foreign'
        issues = [e['issue'] for e in audit([damaged], reviews)['errors']]
        self.assertIn('missing_or_foreign_evidence:formulation:foreign', issues)


if __name__ == '__main__':
    unittest.main()
