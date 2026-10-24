import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.profiles import build_profile
from pipeline.audit_recommendations import audit


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{'id': str(i), 'product_id': 'p', 'content': '커버력이 좋아요. 잡티를 잘 가려줘요', 'rating': 5} for i in range(3)]
        base = {'id': 'p', 'name': '커버 로션'}
        self.product = {**base, **build_profile(base, self.rows)}

    def test_valid_claims_trace_to_actual_rows(self):
        self.assertEqual(audit([self.product], self.rows)['errors'], [])

    def test_other_products_review_cannot_back_a_claim(self):
        damaged = copy.deepcopy(self.product)
        damaged['profile_metadata']['evidence_review_ids']['coverage'][0] = 'foreign'
        rows = self.rows + [{'id': 'foreign', 'product_id': 'other', 'content': '커버력이 좋아요', 'rating': 5}]
        issues = [e['issue'] for e in audit([damaged], rows)['errors']]
        self.assertIn('missing_or_foreign_evidence:coverage:foreign', issues)
        self.assertIn('orphan_review', issues)

    def test_null_and_analyzed_counts_cannot_be_fabricated(self):
        damaged = copy.deepcopy(self.product)
        damaged['longevity_score'] = 4
        damaged['profile_metadata']['analyzed_count'] = 200
        issues = [e['issue'] for e in audit([damaged], self.rows)['errors']]
        self.assertIn('analyzed_count_mismatch', issues)
        self.assertIn('claim_under_three:longevity', issues)
        self.assertIn('recalculation_mismatch:longevity_score', issues)
