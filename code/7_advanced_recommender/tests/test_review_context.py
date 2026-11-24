"""Synthetic regressions for original Korean clauses, not human-labelled reviews."""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import profiles
from pipeline.profiles import build_profile, extract_attributes, input_hash
from pipeline.wear import review_clauses


class ReviewContextTests(unittest.TestCase):
    def extract(self, text, rating=5):
        return extract_attributes({'content': text, 'rating': rating})

    def wear(self, text, key):
        return self.extract(text)['wear'][key]

    def test_short_smoothness_endings(self):
        for text in ['잘 안떠요', '안떠요', '기초 바르면 안 떠요']:
            with self.subTest(text=text):
                value = self.wear(text, 'smoothness')
                self.assertTrue(value['positive'])
                self.assertFalse(value['negative'])

    def test_short_smoothness_does_not_claim_a_colour_match(self):
        self.assertFalse(self.wear('피부톤이 하얗게 안떠요', 'smoothness')['positive'])

    def test_short_naturalness_endings(self):
        for text in ['거의 티가 안남', '티가 안 납니다', '화장한 티도 안남']:
            with self.subTest(text=text):
                value = self.wear(text, 'naturalness')
                self.assertTrue(value['positive'])
                self.assertFalse(value['negative'])

    def test_spot_name_is_not_short_naturalness(self):
        self.assertFalse(self.wear('잡티가 안남', 'naturalness')['positive'])

    def test_transfer_noun_without_particle(self):
        for text in ['묻어남 없고 좋아요', '묻어남 없이 잘 써요', '옷에 묻어남이 전혀 없네요']:
            with self.subTest(text=text):
                value = self.wear(text, 'transfer_resistance')
                self.assertTrue(value['positive'])
                self.assertFalse(value['negative'])

    def test_application_pickup_is_not_transfer(self):
        for tool in ['퍼프', '스펀지', '브러시']:
            with self.subTest(tool=tool):
                self.assertEqual(self.wear(f'{tool}에 적당히 묻어나오구요', 'transfer_resistance'),
                                 {'positive': [], 'negative': []})

    def test_application_and_mask_transfer_in_one_clause(self):
        value = self.wear('퍼프에 적당히 묻어나오구요 마스크에는 많이 묻어나요', 'transfer_resistance')
        self.assertTrue(value['negative'])
        self.assertFalse(value['positive'])

    def test_application_and_no_mask_transfer_in_one_clause(self):
        value = self.wear('퍼프에 잘 묻어나오고 마스크에는 안 묻어요', 'transfer_resistance')
        self.assertTrue(value['positive'])
        self.assertFalse(value['negative'])

    def test_separate_actual_transfer_survives_application(self):
        value = self.wear('퍼프에 묻어나와요. 옷에 묻어나고 불편해요', 'transfer_resistance')
        self.assertTrue(value['negative'])
        self.assertTrue(all('옷에' in text for text in value['negative']))

    def test_reported_promise_and_actual_negative(self):
        text = '마스크에 안묻어난다고했는데\n다. 묻어나고 별로에요'
        value = self.wear(text, 'transfer_resistance')
        self.assertFalse(value['positive'])
        self.assertEqual(value['negative'], ['묻어나고 별로에요'])

    def test_quotation_is_preserved_until_its_guard(self):
        parts = review_clauses('안 묻어난다고 했는데 마스크에 묻어나요')
        self.assertIn('안 묻어난다고 했는데', parts)
        self.assertFalse(self.wear('안 묻어난다고 했는데', 'transfer_resistance')['positive'])

    def test_reported_longevity_and_actual_negative(self):
        result = self.extract('지속력이 좋다고 했는데 지속력이 좋지 않아요')
        self.assertEqual(result['longevity'], 2)
        self.assertEqual(result['evidence']['longevity']['positive'], [])

    def test_explicit_new_conclusion_after_reported_subjective_clause(self):
        # Original cache review 48173438, now diagnostic rather than held out.
        text = ('피부에 많이 겉도는 편입니다 컬러캡슐이 함유되었다고 하는데 '
                '마치 톤업한 것처럼 밝아지는 듯이 발색이 돼서 자연스럽게 사용하긴 '
                '어렵다고 느껴지네요 그리고 무엇보다 너무 많이 묻어납니다....')
        value = self.wear(text, 'transfer_resistance')
        self.assertEqual(value['positive'], [])
        self.assertEqual(value['negative'], ['그리고 무엇보다 너무 많이 묻어납니다'])

    def test_new_observed_positive_does_not_inherit_quoted_ingredient_claim(self):
        value = self.wear('성분이 들어있다고 해요 그리고 무엇보다 마스크에 안 묻어요', 'transfer_resistance')
        self.assertTrue(value['positive'])
        self.assertFalse(value['negative'])

    def test_new_reported_clause_stays_unobserved(self):
        value = self.wear('마스크에 안 묻는다고 해요 그리고 티가 안 난다고 합니다', 'naturalness')
        self.assertEqual(value, {'positive': [], 'negative': []})

    def test_conjunction_inside_reported_content_does_not_release_a_claim(self):
        value = self.wear('마스크에 안 묻어요 그리고 티가 안 난다고 했어요', 'transfer_resistance')
        self.assertEqual(value, {'positive': [], 'negative': []})

    def test_old_product_subject_survives_new_conclusion_marker(self):
        value = self.wear('예전 제품은 안 묻는다고 해요 그리고 마스크에 많이 묻어나요', 'transfer_resistance')
        self.assertEqual(value, {'positive': [], 'negative': []})

    def test_existing_line_break_is_not_treated_as_a_new_conclusion_marker(self):
        result = self.extract('얼굴에 묻어남 없고\n진짜 자연스럽게 홍조를 가려주니까 좋아요')
        self.assertIn('redness', result['positive_concerns'])
        self.assertTrue(result['wear']['transfer_resistance']['positive'])

    def test_expected_transfer_does_not_become_observed(self):
        result = self.wear('묻어나는게 있을텐데 퍼프로 펴바르면 그런것도 별로 없네요', 'transfer_resistance')
        self.assertEqual(result, {'positive': [], 'negative': []})

    def test_explicit_conclusion_survives_expected_transfer(self):
        result = self.wear('마스크에 묻어나는게 있을텐데 실제로 마스크에 묻어남 없이 썼어요', 'transfer_resistance')
        self.assertTrue(result['positive'])
        self.assertFalse(result['negative'])

    def test_general_background_does_not_become_product_longevity(self):
        result = self.extract('더운 날씨에 금방 무너지는 화장에는 살짝 매트한감이 있어야 하는데')
        self.assertIsNone(result['longevity'])
        self.assertFalse(result['evidence']['longevity']['negative'])

    def test_current_product_conclusion_after_general_background(self):
        result = self.extract('더운 날씨에 금방 무너지는 화장에는 매트한감이 있어야 하는데 이 제품은 지속력도 오래가서 좋아요')
        self.assertEqual(result['longevity'], 4)
        self.assertFalse(result['evidence']['longevity']['negative'])

    def test_explicit_bad_longevity(self):
        self.assertEqual(self.extract('지속력이 좋지 않아요')['longevity'], 2)

    def test_other_negation_does_not_erase_transfer(self):
        result = self.extract('마스크 쓰면 묻어서 지속력이 좋지 않아요')
        self.assertEqual(result['longevity'], 2)
        self.assertTrue(result['wear']['transfer_resistance']['negative'])

    def test_missing_compound_symptoms_are_not_bad_wear(self):
        for text in ['들뜨거나 기름이 번들번들했던 증상이 나타나지 않아서 좋아요',
                     '막 들뜨거나 그런 거 없이 부드럽게 발려요']:
            with self.subTest(text=text):
                self.assertFalse(self.wear(text, 'smoothness')['negative'])

    def test_not_bad_longevity_is_not_negative(self):
        self.assertIsNone(self.extract('지속력도 나쁘지 않아서 재구매할 거 같아요')['longevity'])

    def test_negated_creasing_judgement_is_not_bad(self):
        self.assertFalse(self.wear('들뜨는 건 아니에요', 'smoothness')['negative'])

    def test_colour_conditional_then_current_naturalness(self):
        result = self.wear('색상이 밝으면 화장한 티가 나서 부자연스러운데 이 쿠션은 티가 나지않아요', 'naturalness')
        self.assertTrue(result['positive'])
        self.assertFalse(result['negative'])

    def test_concern_list_retains_its_shared_predicate(self):
        result = self.extract('모공, 홍조도 커버돼서 만족해요')
        self.assertIn('pore', result['positive_concerns'])
        self.assertIn('redness', result['positive_concerns'])

    def test_independent_negation_before_comma_does_not_erase_longevity(self):
        result = self.extract('이 제품은 들뜨지도 않고, 지속력도 오래가서 좋아요')
        self.assertEqual(result['longevity'], 4)

    def test_clause_ending_is_not_cut_out_of_a_product_noun(self):
        text = '남자분들은 파운데이션처럼 뭉침없이 발려서 좋아요'
        self.assertEqual(review_clauses(text), [text])
        self.assertEqual(self.wear(text, 'smoothness')['positive'], [text])

    def test_explicit_redness_coverage(self):
        self.assertIn('redness', self.extract('홍조를 가려주어서 좋아요')['positive_concerns'])

    def test_usage_inside_skin_introduction_preserves_flare(self):
        result = self.extract('여드름 피부가 쓰니까 피부가 뒤집어졋음', rating=3)
        self.assertIn('acne', result['negative_concerns'])
        self.assertNotIn('acne', result['positive_concerns'])

    def test_self_introduction_remains_neutral(self):
        result = self.extract('저는 여드름 피부입니다')
        self.assertEqual(result['positive_concerns'], [])
        self.assertEqual(result['negative_concerns'], [])

    def test_negated_flare_is_not_adversity(self):
        result = self.extract('여드름 피부가 쓰니까 피부가 뒤집어지는 일은 없어요')
        self.assertEqual(result['negative_concerns'], [])

    def test_usage_does_not_attach_another_concerns_flare_to_skin_introduction(self):
        result = self.extract('여드름 피부가 쓰니까 홍조가 더 심해졌어요', rating=2)
        self.assertNotIn('acne', result['negative_concerns'])
        self.assertIn('redness', result['negative_concerns'])

    def test_old_product_subject_does_not_disappear_at_clause_boundary(self):
        result = self.extract('기존에 커버밤을 써왔었는데 아무래도 커버밤은 두껍게 발리는 편이었어요')
        self.assertIsNone(result['lightweight'])

    def test_current_product_after_explicit_subject_switch(self):
        result = self.wear('기존 제품은 마스크에 묻어나는데 이 제품은 마스크에 묻어남 없어요', 'transfer_resistance')
        self.assertTrue(result['positive'])
        self.assertFalse(result['negative'])

    def test_future_condition_remains_unknown(self):
        result = self.extract('지속력이 좋지 않으면 구매하지 않을 거예요')
        self.assertIsNone(result['longevity'])
        self.assertFalse(self.wear('많이 바르면 화장한 티가 나요', 'naturalness')['negative'])

    def test_three_unique_ids_and_raw_evidence_are_preserved(self):
        text = '얼굴에 묻어남 없고 좋아요'
        reviews = [{'id': str(i), 'content': text} for i in range(3)]
        self.assertEqual(self.wear(text, 'transfer_resistance')['positive'], [text])
        meta = build_profile({'id': 'p'}, reviews[:2] * 3)['profile_metadata']
        self.assertEqual(meta['wear_attributes']['transfer_resistance']['evidence_count'], 2)
        self.assertIsNone(meta['wear_attributes']['transfer_resistance']['score'])
        meta = build_profile({'id': 'p'}, reviews + reviews)['profile_metadata']
        self.assertEqual(meta['wear_attributes']['transfer_resistance']['score'], 4)
        self.assertEqual(meta['wear_attributes']['transfer_resistance']['positive_review_ids'], ['0', '1', '2'])

    def test_version_change_invalidates_hash_without_shape_change(self):
        self.assertEqual(profiles.VERSION, 'rules-ko-v4')
        self.assertEqual(profiles.METADATA_REVISION, 9)
        before = input_hash({'id': 'p'}, [])
        with mock.patch.object(profiles, 'VERSION', 'rules-ko-v3'):
            self.assertNotEqual(input_hash({'id': 'p'}, []), before)


if __name__ == '__main__':
    unittest.main()
