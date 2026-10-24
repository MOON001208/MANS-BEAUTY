import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.profiles import build_profile, extract_attributes


class WearTests(unittest.TestCase):
    def extract(self, text, key):
        return extract_attributes({'content': text, 'rating': 5})['wear'][key]

    def test_explicit_cosmetic_naturalness(self):
        for text in ['화장한 티가 안 나요', '바른티도 별로 안나는데 좋아요', '티 나지 않아요', '자연스러워서 좋네요', '원래 제 피부 같아요']:
            with self.subTest(text=text):
                self.assertTrue(self.extract(text, 'naturalness')['positive'])
                self.assertFalse(self.extract(text, 'naturalness')['negative'])

    def test_unnaturalness_and_visible_makeup_are_negative(self):
        for text in ['너무 부자연스러워요', '부자연스러운 느낌이에요', '자연스럽지 않아요', '화장한 티가 너무 나요']:
            with self.subTest(text=text):
                self.assertFalse(self.extract(text, 'naturalness')['positive'])
                self.assertTrue(self.extract(text, 'naturalness')['negative'])

    def test_observed_double_polarity_and_context_regressions(self):
        positive = [('색깔이 부자연스럽지 않아서 너무 좋았어요', 'naturalness'),
                    ('목주름에 절대 안끼는 톤업크림은 난생 처음이라고요', 'smoothness'),
                    ('들뜨거나 뭉침이 적어서 사용하기 편했고', 'smoothness')]
        for text, key in positive:
            with self.subTest(text=text):
                result = self.extract(text, key)
                self.assertTrue(result['positive']); self.assertFalse(result['negative'])
        unknown = [('남성용 톤업크림이 더 자연스러워야 한다고 생각하는데요', 'naturalness'),
                   ('부담스럽고 너무 화장한 티가 나서 부담스러울까봐', 'naturalness'),
                   ('손에 묻지 않는 깔끔함', 'transfer_resistance'),
                   ('건조하거나 각질이 들뜨는 피부인데', 'smoothness'),
                   ('요즘 피부화장이 들뜨고 무너져서 바꿔봤는데', 'smoothness'),
                   ('특히 다른 쿠션들 사용하면 코에 뭉치는게 심했는데', 'smoothness'),
                   ('코 옆에 끼거나 눈 밑 주름에 뭉치는 현상도 거의 느끼지 못했어요', 'smoothness')]
        unknown += [('비비크림 같은 메이크업 제품을 바르면 너무 화장한 티가 나서 싫긴 한데', 'naturalness'),
                    ('이거 안 묻어난다는 건 거짓말이에요', 'transfer_resistance'),
                    ('들뜨면 남자들은 더더욱이나 싫어하자나요', 'smoothness'),
                    ('너무 화장한 티가 나서 남자용으로 구매해봤어요', 'naturalness')]
        for text, key in unknown:
            with self.subTest(text=text):
                self.assertEqual(self.extract(text, key), {'positive': [], 'negative': []})

    def test_spots_and_product_names_are_not_naturalness(self):
        for text in ['잡티가 안 나요', '오브제 내추럴 커버 로션', '자연스러운 커버를 원했기 때문에 구매했어요']:
            self.assertEqual(self.extract(text, 'naturalness'), {'positive': [], 'negative': []})

    def test_future_condition_and_previous_product_are_not_observations(self):
        for text, key in [('들뜨지 않기를 바랄뿐입니다', 'smoothness'), ('많이 바르면 화장한 티가 나요', 'naturalness'),
                          ('기존에 쓰던 제품은 마스크에 묻어나와요', 'transfer_resistance')]:
            self.assertEqual(self.extract(text, key), {'positive': [], 'negative': []})

    def test_transfer_polarity(self):
        for text in ['마스크에도 잘 묻지 않고 좋아요', '마스크에 안 묻어요', '묻어나는감이 적어서 만족스럽습니다', '묻어나는게 하나도 없습니다']:
            with self.subTest(text=text):
                value = self.extract(text, 'transfer_resistance')
                self.assertTrue(value['positive']); self.assertFalse(value['negative'])
        for text in ['마스크 쓰면 엄청 묻어나와요', '옷에 묻어요', '묻어남이 좀 있는 편 같아요']:
            with self.subTest(text=text):
                self.assertTrue(self.extract(text, 'transfer_resistance')['negative'])

    def test_double_negation_is_unknown(self):
        for text in ['안 묻는 건 아니에요', '묻어남이 전혀 없는 건 또 아니고', '화장한 티가 안 나지는 않아요']:
            for key in ['transfer_resistance', 'naturalness']:
                self.assertEqual(self.extract(text, key), {'positive': [], 'negative': []})

    def test_creasing_is_distinct_from_skin_colour(self):
        for text in ['모공 끼임현상이 없어서 좋아요', '대충 펴발라도 뭉침없이 잘 발려요', '팔자 주름에 심하게 끼지않아서 좋았어요', '피부에서 들뜨지 않아요']:
            with self.subTest(text=text):
                self.assertTrue(self.extract(text, 'smoothness')['positive'])
                self.assertFalse(self.extract(text, 'smoothness')['negative'])
        self.assertFalse(self.extract('하얗게 피부톤이 뜨지 않아요', 'smoothness')['positive'])
        self.assertTrue(self.extract('모공 끼임이 있어요', 'smoothness')['negative'])

    def test_mixed_review_never_becomes_a_definite_score(self):
        text = '처음에는 묻지 않아요. 시간이 지나면 마스크에 묻어나와요'
        reviews = [{'id': str(i), 'content': text} for i in range(4)]
        wear = build_profile({'id': 'p'}, reviews)['profile_metadata']['wear_attributes']['transfer_resistance']
        self.assertIsNone(wear['score'])
        self.assertEqual(wear['evidence_count'], 0)
        self.assertEqual(wear['mixed_count'], 4)

    def test_three_unique_reviews_and_option_boundaries(self):
        reviews = [{'id': str(i), 'option_name': '1호', 'content': '자연스러워요'} for i in range(3)]
        reviews += [reviews[0], {'id': 'different', 'option_name': '2호', 'content': '화장한 티가 나요'}]
        meta = build_profile({'id': 'p'}, reviews)['profile_metadata']
        self.assertEqual(meta['wear_attributes']['naturalness']['evidence_count'], 4)
        self.assertEqual(meta['option_wear']['1호']['attributes']['naturalness']['score'], 4)
        self.assertIsNone(meta['option_wear']['2호']['attributes']['naturalness']['score'])
        self.assertEqual(meta['option_wear']['2호']['attributes']['naturalness']['negative_review_ids'], ['different'])
