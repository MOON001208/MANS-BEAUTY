"""Operational gates must distinguish a proven check from a skipped/failed one."""
import base64
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ops
from pipeline.profiles import VERSION


def http_error(status, code):
    return HTTPError('https://example.invalid', status, 'test', {},
                     io.BytesIO(json.dumps({'code': code}).encode()))


class OpsTests(unittest.TestCase):
    def check(self, action, *args):
        checks = ops.Checks()
        output = io.StringIO()
        with redirect_stdout(output):
            action(*args, checks)
        return checks.failed, output.getvalue()

    def test_missing_web_dependencies_fails_verification(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(ops, 'WEB', Path(folder)), \
                patch.object(ops, '_run'):
            failed, _ = self.check(ops.verify)
        self.assertEqual(failed, 1)

    def test_only_explicit_permission_denial_passes_author_check(self):
        outcomes = [([], 1), (http_error(403, '42501'), 0),
                    (http_error(401, '42501'), 0), (http_error(401, 'PGRST301'), 1),
                    (http_error(403, 'other'), 1),
                    (http_error(500, 'XX000'), 1), (http_error(400, '42703'), 1),
                    (URLError('offline'), 1), (TimeoutError(), 1)]
        for result, expected in outcomes:
            with self.subTest(result=result), patch.object(ops, '_get', side_effect=[[], [], result]):
                failed, _ = self.check(ops._public_access, 'https://example.invalid', 'public-fixture')
                self.assertEqual(failed, expected)

    def test_missing_or_invalid_public_key_fails(self):
        self.assertEqual(self.check(ops._public_access, 'unused', None)[0], 1)
        with patch.object(ops, '_get', side_effect=http_error(401, 'invalid')) as get:
            self.assertEqual(self.check(ops._public_access, 'unused', 'bad')[0], 1)
            self.assertEqual(get.call_count, 1)

    def test_public_review_content_must_remain_readable(self):
        with patch.object(ops, '_get', side_effect=[[], http_error(403, '42501')]):
            self.assertEqual(self.check(ops._public_access, 'unused', 'public-fixture')[0], 1)

    def test_crosscheck_does_not_claim_to_review_an_empty_diff(self):
        with patch.object(ops.subprocess, 'run') as run, patch.object(ops.shutil, 'which') as which:
            run.return_value.returncode = 0
            with redirect_stdout(io.StringIO()) as output:
                ops.crosscheck(ops.Checks(), 'origin/main')
            self.assertIn('비교 변경 없음', output.getvalue())
            which.assert_not_called()
            self.assertEqual(run.call_count, 1)

    def test_server_key_detection_decodes_role_without_rejecting_public_jwt(self):
        for role, expected in [('anon', False), ('service_role', True)]:
            payload = base64.urlsafe_b64encode(json.dumps({'role': role}).encode()).decode().rstrip('=')
            self.assertEqual(ops._contains_server_key(f'eyJhbGciOiJIUzI1NiJ9.{payload}.signature'), expected)
        self.assertFalse(ops._contains_server_key('function refuses_service_role() {}'))
        self.assertTrue(ops._contains_server_key('sb_secret_test_fixture_only'))

    def test_live_scan_checks_linked_javascript_not_just_html(self):
        html = b'<link rel="preload" as="script" href="/chunk.js"><script src="/chunk.js"></script>'
        for javascript, expected in [(b'const safe = true;', 0), (b'sb_secret_test_fixture_only', 1)]:
            with self.subTest(javascript=javascript), patch.object(
                    ops.urllib.request, 'urlopen', side_effect=[io.BytesIO(html), io.BytesIO(javascript)]) as fetch:
                self.assertEqual(self.check(ops._site_health)[0], expected)
                self.assertEqual(fetch.call_count, 2)

    def test_unreadable_javascript_cannot_pass_scan(self):
        with patch.object(ops.urllib.request, 'urlopen', side_effect=[
                io.BytesIO(b'<script src="/chunk.js"></script>'), URLError('offline')]):
            self.assertEqual(self.check(ops._site_health)[0], 1)

    def test_environment_supports_quoted_values_and_ci_overrides(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            web = root / 'web'
            web.mkdir()
            (root / '.env').write_text('SUPABASE_URL="https://file.invalid"\n', encoding='utf-8')
            with patch.object(ops, 'ROOT', root), patch.object(ops, 'WEB', web), patch.dict(
                    os.environ, {'NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY': 'sb_publishable_fixture'}, clear=True):
                env = ops._env()
                self.assertEqual(env['SUPABASE_URL'], 'https://file.invalid')
                self.assertEqual(env['NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY'], 'sb_publishable_fixture')
                with patch.dict(os.environ, {'SUPABASE_URL': 'https://ci.invalid'}):
                    self.assertEqual(ops._env()['SUPABASE_URL'], 'https://ci.invalid')

    def test_status_counts_union_of_explicit_and_relative_shades_including_sold_out(self):
        products = [
            {'id': 'both', 'suitable_shades': ['21'], 'profile_metadata': {
                'version': VERSION, 'shade_lineup': {'options': [{'sold_out': False}]}}},
            {'id': 'explicit', 'suitable_shades': ['23'], 'profile_metadata': {'version': VERSION}},
            {'id': 'sold', 'profile_metadata': {
                'version': VERSION, 'shade_lineup': {'options': [{'sold_out': True}]}}},
        ]
        with patch.object(ops, '_env', return_value={'SUPABASE_URL': 'url', 'SUPABASE_SECRET_KEY': 'fixture'}), \
                patch.object(ops, '_get', side_effect=[products, []]):
            failed, output = self.check(ops.status)
        self.assertEqual(failed, 0)
        self.assertIn('3/3 (100%)', output)

    def test_status_network_failure_is_a_failed_gate_without_traceback(self):
        with patch.object(ops, '_env', return_value={'SUPABASE_URL': 'url', 'SUPABASE_SECRET_KEY': 'fixture'}), \
                patch.object(ops, '_get', side_effect=URLError('offline')):
            failed, output = self.check(ops.status)
        self.assertEqual(failed, 1)
        self.assertNotIn('Traceback', output)
