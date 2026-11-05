"""Optional Crawl4AI transport for the existing synchronous collector.

The worker thread retains ingestion, delay, cursor and access-limit handling.
Only HTTP transport runs on the browser's event loop.
"""
from __future__ import annotations

import asyncio
import json
import os
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

from dotenv import dotenv_values

from shared import CACHE, ROOT


@dataclass
class BrowserResponse:
    status_code: int
    headers: dict
    text: str

    def json(self):
        return json.loads(self.text)


class BrowserSession:
    def __init__(self, page, loop, use_saved_login=False):
        self.page, self.loop = page, loop
        self.use_saved_login = use_saved_login

    async def fetch(self, method, url, headers, timeout, params=None, json=None):
        from scraper.crawler import REVIEW_ROOT

        if params:
            url += ('&' if '?' in url else '?') + urlencode(params)
        # Chromium supplies cookies. The mobile review API is cross-origin.
        credentials = 'include' if self.use_saved_login and url.startswith(REVIEW_ROOT + '/') else 'same-origin'
        sent_headers = {'accept': headers.get('accept', 'application/json')}
        if json is not None:
            sent_headers['content-type'] = 'application/json'
        responses = []

        def observe(response):
            if response.url == url and response.request.method == method:
                responses.append(response)

        self.page.on('response', observe)
        try:
            value = await self.page.evaluate("""async ({method, url, headers, payload, timeout, credentials}) => {
            const response = await fetch(url, {
                method, headers, credentials,
                body: payload === null ? undefined : JSON.stringify(payload),
                signal: AbortSignal.timeout(timeout)
            });
            return {status: response.status, headers: Object.fromEntries(response.headers),
                    text: await response.text()};
            }""", {'method': method, 'url': url, 'headers': sent_headers,
                   'payload': json, 'timeout': int(timeout * 1000), 'credentials': credentials})
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
    from scraper.crawler import AccessLimited, SITE, SourceError
    os.environ.setdefault('CRAWL4_AI_BASE_DIRECTORY', str(CACHE / 'crawl4ai'))
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
    except ImportError:
        raise SourceError('requirements-crawl4ai.txt와 Playwright Chromium 설치가 필요합니다.') from None

    profile_dir = os.getenv('OLIVEYOUNG_BROWSER_PROFILE') or dotenv_values(ROOT / '.env').get('OLIVEYOUNG_BROWSER_PROFILE')
    browser_options = {'headless': True, 'verbose': False}
    if profile_dir:
        storage_state = Path(profile_dir).expanduser() / 'storage_state.json'
        if not storage_state.is_file():
            raise SourceError('올리브영 프로필의 storage_state.json이 없습니다. 로그인 후 q로 저장해 주세요.')
        browser_options['storage_state'] = str(storage_state)
        print('저장된 올리브영 브라우저 상태를 사용합니다.', flush=True)

    state = {}

    async def remember_page(page, **kwargs):
        state['page'] = page
        return page

    async with AsyncWebCrawler(config=BrowserConfig(**browser_options)) as crawler:
        crawler.crawler_strategy.set_hook('on_page_context_created', remember_page)
        pid = (args.product or [None])[0]
        # Crawl4AI reports the root URL's 301 even after following it to a 200.
        url = f'{SITE}/store/main/main.do'
        if pid:
            url = f'{SITE}/store/goods/getGoodsDetail.do?' + urlencode({'goodsNo': pid})
        result = await crawler.arun(url=url, config=CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS, session_id='oliveyoung-collection',
            page_timeout=45000, delay_before_return_html=5))
        if result.status_code in (401, 403):
            raise AccessLimited(f'브라우저 페이지 접근 제한 HTTP {result.status_code}')
        if not result.success or result.status_code != 200 or 'page' not in state:
            raise SourceError('브라우저 상품 페이지를 열지 못했습니다.')
        session = BrowserSession(state['page'], asyncio.get_running_loop(), use_saved_login=bool(profile_dir))
        return await asyncio.to_thread(collect, args, session=session)


def run_browser(args, collect):
    return asyncio.run(_run_browser(args, collect))
