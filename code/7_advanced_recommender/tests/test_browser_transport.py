import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scraper.browser import BrowserSession
from scraper.crawler import AccessLimited, OliveYoung, RateLimited, SourceError


class BrowserTransportTests(unittest.IsolatedAsyncioTestCase):
    def make_api(self, status=200, body=None, headers=None):
        page = MagicMock()
        page.evaluate = AsyncMock(return_value={
            'status': status, 'headers': headers or {},
            'text': json.dumps(body if body is not None else {'code': 200, 'data': {'ok': True}}),
        })
        session = BrowserSession(page, asyncio.get_running_loop())
        return OliveYoung(delay=0, session=session), page

    async def test_request_body_survives_thread_bridge(self):
        api, page = self.make_api()
        payload = {'goodsNumber': 'A000000184127', 'cursorId': 42, 'itemNumberList': ['1']}
        result = await asyncio.to_thread(api.json, 'POST', 'https://m.oliveyoung.co.kr/review/api/v2/reviews/cursor', json=payload)
        self.assertEqual(result, {'ok': True})
        sent = page.evaluate.call_args.args[1]
        self.assertEqual(sent['payload'], payload)
        self.assertNotIn('origin', sent['headers'])
        self.assertNotIn('referer', sent['headers'])

    async def test_query_params_and_html_survive(self):
        api, page = self.make_api()
        page.evaluate.return_value['text'] = '<html>상품</html>'
        response = await asyncio.to_thread(api.request, 'GET', 'https://www.oliveyoung.co.kr/catalog', params={'pageIdx': 2})
        self.assertEqual(response.text, '<html>상품</html>')
        self.assertTrue(page.evaluate.call_args.args[1]['url'].endswith('?pageIdx=2'))

    async def test_access_denied_remains_access_denied(self):
        api, page = self.make_api(status=403)
        with self.assertRaises(AccessLimited):
            await asyncio.to_thread(api.json, 'POST', 'https://m.oliveyoung.co.kr/review/api/v2/reviews/cursor', json={})
        self.assertEqual(page.evaluate.await_count, 1)

    async def test_long_retry_after_stops_without_retry(self):
        api, page = self.make_api(status=429, headers={'retry-after': '120'})
        with self.assertRaises(RateLimited):
            await asyncio.to_thread(api.json, 'GET', 'https://www.oliveyoung.co.kr/')
        self.assertEqual(page.evaluate.await_count, 1)

    async def test_browser_failure_is_not_empty_data(self):
        api, page = self.make_api()
        page.evaluate.side_effect = RuntimeError('browser disconnected')
        with self.assertRaises(SourceError):
            await asyncio.to_thread(api.json, 'GET', 'https://www.oliveyoung.co.kr/')
        page.remove_listener.assert_called_once()

    async def test_retry_after_hidden_by_cors_is_still_honored(self):
        api, page = self.make_api(status=429)
        response = MagicMock()
        response.url = 'https://m.oliveyoung.co.kr/review/api/v2/reviews/cursor'
        response.request.method = 'POST'
        response.all_headers = AsyncMock(return_value={'retry-after': '120'})

        async def evaluate(*args):
            page.on.call_args.args[1](response)
            return {'status': 429, 'headers': {}, 'text': '{}'}

        page.evaluate.side_effect = evaluate
        with self.assertRaises(RateLimited):
            await asyncio.to_thread(api.json, 'POST', response.url, json={})
        self.assertEqual(page.evaluate.await_count, 1)
        page.remove_listener.assert_called_once()


if __name__ == '__main__':
    unittest.main()
