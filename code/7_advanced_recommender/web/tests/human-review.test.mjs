import test from 'node:test';
import assert from 'node:assert/strict';
import { summarizeResponses, createStudy } from '../scripts/human-review.mjs';

// Synthetic unit fixtures only. Never exported as actual human labels.
const study = { study_id: 'unit-test-only', cases: [
  { id: 'a', same_order: false, mapping: { left: 'baseline', right: 'current' } },
  { id: 'b', same_order: true, mapping: { left: 'current', right: 'baseline' } },
] };
const response = answers => ({ study_id: study.study_id, response_id: 'test-only', human_confirmed: true, completed_at: '2026-10-24', answers });

test('no responses means awaiting real human review, not a successful quality score', () => {
  const result = summarizeResponses(study, []);
  assert.equal(result.status, 'awaiting_human_review');
  assert.equal(result.submitted_case_responses, 0);
  assert.equal(result.totals.current, 0);
});

test('blind left/right assignments are decoded and identical lists cannot establish a winner', () => {
  const result = summarizeResponses(study, [response([{ case_id: 'a', choice: 'right' }, { case_id: 'b', choice: 'left' }])]);
  assert.equal(result.totals.current, 1);
  assert.equal(result.totals.identical_order, 1);
});

test('re-exporting the same response cannot inflate human labels', () => {
  const r = response([{ case_id: 'a', choice: 'left' }]);
  const result = summarizeResponses(study, [r, { ...r, completed_at: '2026-10-25', answers: [{ case_id: 'a', choice: 'tie' }] }]);
  assert.equal(result.submitted_case_responses, 1);
  assert.equal(result.totals.tie, 1);
});

test('wrong study, non-human, unknown case and duplicate case are rejected', () => {
  for (const r of [ { ...response([]), study_id: 'other' }, { ...response([]), human_confirmed: false },
    response([{ case_id: 'x', choice: 'left' }]), response([{ case_id: 'a', choice: 'fake' }]),
    response([{ case_id: 'a', choice: 'left' }, { case_id: 'a', choice: 'right' }]) ]) {
    assert.throws(() => summarizeResponses(study, [r]));
  }
});

test('baseline and new data must describe the same catalog before a comparison is prepared', () => {
  assert.throws(() => createStudy({ products: [{ id: 'new' }] }, { catalog_ids: ['old'] }, { errors: [] }), /같은 자료/);
});
