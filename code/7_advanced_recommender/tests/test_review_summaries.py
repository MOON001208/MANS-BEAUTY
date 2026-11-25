import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.profiles import VERSION
from pipeline.review_summaries import build_summary_product, evidence_specs, summary_source


def review(rid, content, **extra):
    return {'id': rid, 'product_id': 'p1', 'content': content, 'option_name': '옵션 A', **extra}


class ReviewSummaryTests(unittest.TestCase):
    def setUp(self):
        self.product = {'id': 'p1', 'profile_metadata': {
            'version': VERSION, 'input_hash': 'current-input',
            'evidence_review_ids': {'coverage': ['1', '2', '3']},
            'evidence_counts': {'coverage': 30},
        }}
        self.reviews = [review('1', '커버력이 좋아요.'), review('2', '커버력이 아쉬워요.'),
                        review('3', '모공이 잘 가려져요.', author='private author')]

    def test_sources_classified_from_raw_not_rating_or_name_and_no_author(self):
        result = build_summary_product(self.product, self.reviews)
        entry = result['attributes']['coverage']
        self.assertEqual(entry['totalEvidenceCount'], 30)
        self.assertEqual([s['polarity'] for s in entry['sources']], ['positive', 'negative', 'positive'])
        self.assertNotIn('author', json.dumps(result))
        for source, original in zip(entry['sources'], self.reviews):
            self.assertEqual(source['sha256'], hashlib.sha256(original['content'].encode()).hexdigest())
            self.assertTrue(all(text in original['content'] for text in source['excerpts']))

    def test_missing_or_foreign_original_fails_closed(self):
        with self.assertRaises(ValueError):
            build_summary_product(self.product, self.reviews[:2])
        with self.assertRaises(ValueError):
            build_summary_product(self.product, [*self.reviews[:2], {**self.reviews[2], 'product_id': 'p2'}])

    def test_self_introduction_and_purchase_intention_are_not_summary_claims(self):
        for text in ['저는 여드름 피부입니다.', '커버력이 좋다고 해서 구매했어요.', '커버력이 좋으면 좋겠어요.']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                summary_source('p1', 'coverage', review('1', text))

    def test_mixed_and_negative_preserved_and_option_scope_checked(self):
        source = summary_source('p1', 'naturalness', review('1', '자연스러워요. 그런데 화장 티가 많이 나요.'), '옵션 A')
        self.assertEqual(source['polarity'], 'mixed')
        self.assertEqual(len(source['excerpts']), 2)
        self.assertEqual(summary_source('p1', 'naturalness', review('2', '부자연스러워요.'))['polarity'], 'negative')
        with self.assertRaises(ValueError):
            summary_source('p1', 'naturalness', review('1', '자연스러워요.'), '옵션 B')

    def test_wear_sample_preserves_more_than_five_sources_and_mixed(self):
        meta = {'wear_attributes': {'naturalness': {'evidence_count': 10, 'mixed_count': 3,
                'positive_review_ids': list(map(str, range(5))),
                'negative_review_ids': list(map(str, range(5, 10))),
                'mixed_review_ids': ['10', '11', '12']}}}
        spec = next(spec for spec in evidence_specs(meta) if spec[1] == 'naturalness')
        self.assertEqual(len(spec[2]), 13)
        self.assertEqual(spec[3], 13)

    def test_normalized_or_truncated_text_is_not_quoted_as_original(self):
        original = review('1', '자연스러워요  그리고 화장 티가 안 나요')
        source = summary_source('p1', 'naturalness', original)
        self.assertTrue(all(text in original['content'] for text in source['excerpts']))
        self.assertFalse(any('요 그리고' in text for text in source['excerpts']))

    def test_quoted_review_does_not_become_observed_use_summary(self):
        source = summary_source('p1', 'transfer_resistance', review('9837783',
            '마스크에 묻는다는 리뷰가 많던데 일회용말고 천?이라고 하나 검은색 다회용을 사서 그런진 몰라도 나는 거의 안 묻어났음.'))
        self.assertFalse(source['semantic_verified'])

    def test_clause_starting_with_particle_is_not_an_out_of_context_quote(self):
        source = summary_source('p1', 'coverage', review('18578499',
            '촉촉한게 괜찮은거같아요 양 조절 잘해서 바르면 자연스럽게 톤업되고 여드름자국?은 잘 커버는 안되욤! 그냥 톤업'))
        self.assertEqual(source['polarity'], 'negative')
        self.assertEqual(source['excerpts'], [])

    def test_independent_audit_original_boundaries_fail_closed_without_score_changes(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures/review_summary_boundaries.json').read_text(encoding='utf-8'))
        for item in fixture['cases']:
            with self.subTest(rid=item['id'], key=item['key']):
                source = summary_source(item['product_id'], item['key'], item)
                self.assertEqual(source['semantic_verified'], item['semantic_verified'])
                self.assertTrue(all(text in item['content'] for text in source['excerpts']))

    def test_negated_bad_expressions_cannot_become_negative_summary_claims(self):
        cases = [('lightweight', '두껍게 발리지 않으며 자연스러운 피부표현 가능합니다.'),
                 ('lightweight', '두껍게 발리지 않고 좋아요.'),
                 ('smoothness', '뭉치는 느낌은 거의 없었던 것 같아요.'),
                 ('smoothness', '들뜨는 느낌도 없어서 딱 좋더라고요.')]
        for key, text in cases:
            with self.subTest(key=key, text=text):
                source = summary_source('p1', key, review('1', text))
                self.assertFalse(source['semantic_verified'])

    def test_unbalanced_parentheses_and_leading_particles_are_not_quotations(self):
        for text in ['(커버력이 좋아요.', '까지 커버력이 좋아요.', ')이라서 커버력이 좋아요.']:
            with self.subTest(text=text):
                self.assertEqual(summary_source('p1', 'coverage', review('1', text))['excerpts'], [])

    def test_conditional_fixer_advice_is_not_observed_product_longevity(self):
        source = summary_source('p1', 'longevity', review('1',
            '픽서미스트등으로 마무리하시면 조금더 오래유지가 됩니다.'))
        self.assertFalse(source['semantic_verified'])

    def test_general_conditions_worry_other_owners_and_powder_prep_are_held(self):
        cases = [
            ('naturalness', '보통 엄청 진한 색이면 티나서 안쓰게되는데 ㄹㅇ 자연스러워서 자주 쓰게됨'),
            ('naturalness', '남친도 티안나면 안쓸거같았는데 자연스러워요.'),
            ('naturalness', '톤 안 맞으면 티 많이 나요.'),
            ('naturalness', '남친 매번 제껄루 쓰면 너무 티나서 하나 사줬는데 자연스러워요.'),
            ('transfer_resistance', '바르고 파우더 처리후 휴지를 갖다대면 신기하게 묻어나는게 하나도 없습니다. 마찰이 생길 때는 다 지워지네요.'),
            ('transfer_resistance', '원래 스틱으로 된 제품을 사용했었습니다. 묻어나는게 좀 있었고 이번 쿠션은 덜 묻어요.'),
            ('transfer_resistance', '기존 쿠션을 쓰던 때는 마스크에 묻어나요. 이건 안 묻어요.'),
        ]
        for key, text in cases:
            with self.subTest(key=key, text=text):
                self.assertFalse(summary_source('p1', key, review('1', text))['semantic_verified'])
        for key, text in [('naturalness', '제가 써보니 자연스러워요.'),
                          ('naturalness', '바른 뒤 화장 티가 많이 나요.'),
                          ('transfer_resistance', '마스크에 거의 안 묻어났어요.')]:
            with self.subTest(direct_control=text):
                self.assertTrue(summary_source('p1', key, review('1', text))['semantic_verified'])

    def test_context_variants_and_direct_observation_controls(self):
        cases = [
            ('lightweight', '두껍게 발린다는 느낌도 안들고 좋아요.', False),
            ('smoothness', '안 뭉치고 좋대여.', False),
            ('smoothness', '들뜨거나 그런 건 못 느꼈고요.', False),
            ('smoothness', '뭉침이 심하지 않고 좋아요.', False),
            ('longevity', '클렌징 티슈로 쉽게 지워져요.', False),
            ('transfer_resistance', '묻어나는 것도 생각보다 없고 좋아요.', False),
            ('transfer_resistance', '용기가 분해되더니 옷에 다 묻어나요.', False),
            ('lightweight', '가벼운 느낌을 원해서 사 줬는데 좋아요.', False),
            ('longevity', '금방 무너지는 게 가장 고민이었습니다.', False),
            ('lightweight', '제형이 무거워요.', True),
            ('smoothness', '들뜨고 뭉치고 불편해요.', True),
            ('smoothness', '주름에 끼어요.', True),
            ('longevity', '금방 지워져요.', True),
            ('longevity', '하루 종일 유지돼요.', True),
            ('transfer_resistance', '마스크에 묻어나와서 아쉬워요.', True),
        ]
        for key, text, expected in cases:
            with self.subTest(key=key, text=text):
                self.assertEqual(summary_source('p1', key, review('1', text))['semantic_verified'], expected)


if __name__ == '__main__':
    unittest.main()
