"""Optional anonymous Crawl4AI transport for the existing synchronous collector.

The worker thread retains ingestion, delay, cursor and access-limit handling.
Only HTTP transport runs on the browser's event loop. No persisted login profile.
"""
from __future__ import annotations

import asyncio
import json
import os
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from urllib.parse import urlencode

from shared import CACHE


@dataclass
class BrowserResponse:
    status_code: int
    headers: dict
    text: str

    def json(self):
        return json.loads(self.text)


class BrowserSession:
    def __init__(self, page, loop):
        self.page, self.loop = page, loop

    async def fetch(self, method, url, headers, timeout, params=None, json=None):
        if params:
            url += ('&' if '?' in url else '?') + urlencode(params)
        # Origin/Referer are set by Chromium. Never inject credentials or cookies.
        sent_headers = {'accept': headers.get('accept', 'application/json')}
        if json is not None:
            sent_headers['content-type'] = 'application/json'
        responses = []

        def observe(response):
            if response.url == url and response.request.method == method:
                responses.append(response)

        self.page.on('response', observe)
        try:
            value = await self.page.evaluate("""async ({method, url, headers, payload, timeout}) => {
            const response = await fetch(url, {
                method, headers,
                body: payload === null ? undefined : JSON.stringify(payload),
                signal: AbortSignal.timeout(timeout)
            });
            return {status: response.status, headers: Object.fromEntries(response.headers),
                    text: await response.text()};
            }""", {'method': method, 'url': url, 'headers': sent_headers,
                   'payload': json, 'timeout': int(timeout * 1000)})
            # Cross-origin fetch can hide Retry-After from JavaScript. Read the
            # actual browser response headers so long server waits remain binding.
            response_headers = await responses[-1].all_headers() if responses else value['headers']
            return BrowserResponse(value['status'], {k.title(): v for k, v in response_headers.items()}, value['text'])
        finally:
            self.page.remove_listener('response', observe)

    def request(self, method, url, headers, timeout=30, **kwargs):
        from scraper.crawler import SourceError
        future = asyncio.run_coroutine_threadsafe(
            self.fetch(method, url, headers, timeout, **kwargs), self.loop)
        try:
            return future.result(timeout=timeout + 5)
        except FutureTimeout:
            future.cancel()
            raise SourceError('브라우저 요청 시간 초과') from None
        except Exception:
            raise SourceError('브라우저 네트워크 요청 실패') from None


async def _run_browser(args, collect):
    from scraper.crawler import AccessLimited, SourceError
    os.environ.setdefault('CRAWL4_AI_BASE_DIRECTORY', str(CACHE / 'crawl4ai'))
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
    except ImportError:
        raise SourceError('requirements-crawl4ai.txt와 Playwright Chromium 설치가 필요합니다.') from None
    state = {}

    async def remember_page(page, **kwargs):
        state['page'] = page
        return page

    async with AsyncWebCrawler(config=BrowserConfig(headless=True, verbose=False)) as crawler:
        crawler.crawler_strategy.set_hook('on_page_context_created', remember_page)
        pid = (args.product or [None])[0]
        url = 'https://www.oliveyoung.co.kr/'
        if pid:
            url += 'store/goods/getGoodsDetail.do?' + urlencode({'goodsNo': pid})
        result = await crawler.arun(url=url, config=CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS, session_id='anonymous-collection',
            page_timeout=45000, delay_before_return_html=5))
        if result.status_code in (401, 403):
            raise AccessLimited(f'브라우저 페이지 접근 제한 HTTP {result.status_code}')
        if not result.success or result.status_code != 200 or 'page' not in state:
            raise SourceError('브라우저 상품 페이지를 열지 못했습니다.')
        session = BrowserSession(state['page'], asyncio.get_running_loop())
        return await asyncio.to_thread(collect, args, session=session)


def run_browser(args, collect):
    return asyncio.run(_run_browser(args, collect))
