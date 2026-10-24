import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.profiles import extract_attributes


class ConcernEvidenceTests(unittest.TestCase):
    def test_future_purchase_and_previous_product_are_not_current_effects(self):
        future = '다음에는 파운데이션을 구매해서 커버력이 좋은 제품을 구매하려고 합니다'
        self.assertIsNone(extract_attributes({'content': future, 'rating': 5})['coverage'])
        previous = '기존에 스틱으로된 커버밤을 써왔었는데 아무래도 커버밤은 좀 두껍게 발리는 경향이 있었어요'
        self.assertIsNone(extract_attributes({'content': previous, 'rating': 5})['lightweight'])
        comparison = '기존에 쓰던 것보다 커버력이 좋아요'
        self.assertEqual(extract_attributes({'content': comparison, 'rating': 5})['coverage'], 4)
    def test_real_insufficient_coverage_is_not_a_benefit(self):
        result = extract_attributes({'content': '대신 완벽한 잡티커버에는 조금 부족할수는 있을 것이에요', 'rating': 5})
        self.assertNotIn('spots', result['positive_concerns'])

    def test_real_conditional_wrinkle_creasing_is_not_a_benefit(self):
        result = extract_attributes({'content': '커버력이 뛰어나면 뜨거나 주름사이에 끼일 수 있으니', 'rating': 5})
        self.assertNotIn('wrinkle', result['positive_concerns'])
        self.assertIsNone(result['coverage'])
        hypothetical = extract_attributes({'content': '잡티 커버가 좋으면 구매할 거예요', 'rating': 5})
        self.assertNotIn('spots', hypothetical['positive_concerns'])

    def test_self_introduction_and_product_name_are_not_effects(self):
        result = extract_attributes({'content': '저는 여드름 피부라서 커버로션을 구매했어요', 'rating': 5})
        self.assertNotIn('acne', result['positive_concerns'])

    def test_explicit_local_coverage_and_improvement_still_count(self):
        for text, concern in [('모공을 잘 가려줘요', 'pore'), ('잡티 커버가 좋아요', 'spots'),
                              ('홍조가 진정이 돼요', 'redness'), ('여드름 흉터 커버가 잘 됩니다', 'acne')]:
            with self.subTest(text=text):
                self.assertIn(concern, extract_attributes({'content': text, 'rating': 5})['positive_concerns'])

    def test_negated_local_effect_is_not_positive(self):
        self.assertNotIn('pore', extract_attributes({'content': '모공이 잘 가려지지 않아요', 'rating': 5})['positive_concerns'])

    def test_existing_skin_history_does_not_become_product_adversity(self):
        text = '제 피부타입은 복합성, 트러블(예민한피부라 가끔 올라옴), 모공넓음'
        self.assertEqual(extract_attributes({'content': text, 'rating': 5})['negative_concerns'], [])

    def test_absence_of_flare_is_not_negative(self):
        text = '예민한 피부인데 트러블 올라오는거도 없었고 잘 바르고 다녀요'
        self.assertNotIn('acne', extract_attributes({'content': text, 'rating': 5})['negative_concerns'])

    def test_explicit_post_use_flare_survives_skin_introduction(self):
        text = '지성피부라 마음에 들었어요 다만 저는 사용 후 트러블이 많이 올라왔어요'
        self.assertIn('acne', extract_attributes({'content': text, 'rating': 2})['negative_concerns'])


if __name__ == '__main__':
    unittest.main()
