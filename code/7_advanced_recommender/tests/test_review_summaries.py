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


if __name__ == '__main__':
    unittest.main()
