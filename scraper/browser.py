import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from config import settings

logger = logging.getLogger(__name__)


class BrowserManager:
    """管理 Playwright 浏览器实例，负责获取 WAF Token 并在浏览器内发起 API 请求。"""

    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._token_obtained_at: float = 0
        self._lock = asyncio.Lock()

    async def start(self):
        """启动浏览器并访问 Binance 页面通过 WAF Challenge。"""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        await self._init_page()
        logger.info("BrowserManager started, WAF challenge passed")

    async def stop(self):
        """关闭浏览器和 Playwright。"""
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("BrowserManager stopped")

    async def _init_page(self):
        """创建新的浏览器上下文并访问 Binance Smart Money 页面以通过 WAF。"""
        if self._context:
            await self._context.close()

        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )

        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)

        self._page = await self._context.new_page()
        url = f"{settings.BINANCE_BASE_URL}{settings.SMART_MONEY_PAGE}"
        logger.info(f"Navigating to {url} for WAF challenge...")

        await self._page.goto(url, wait_until="networkidle", timeout=60000)
        await self._page.wait_for_timeout(5000)
        self._token_obtained_at = time.time()

        cookies = await self._context.cookies()
        logger.info(f"WAF challenge done, obtained {len(cookies)} cookies")

    def _is_session_expired(self) -> bool:
        elapsed = time.time() - self._token_obtained_at
        return elapsed > settings.WAF_TOKEN_REFRESH_MINUTES * 60

    async def _ensure_page(self):
        """确保页面会话有效，过期则重新初始化。"""
        if self._is_session_expired() or self._page is None:
            logger.info("Browser session expired, re-initializing...")
            await self._init_page()

    async def get(self, url: str) -> Dict[str, Any]:
        """在浏览器内通过 JS fetch() 发起 GET 请求。

        Returns:
            {"status": int, "data": dict | None}
        """
        async with self._lock:
            await self._ensure_page()

        js_code = """
        async (url) => {
            try {
                const resp = await fetch(url, {
                    method: 'GET',
                    credentials: 'include',
                });
                const status = resp.status;
                let data = null;
                try {
                    data = await resp.json();
                } catch(e) {
                    data = { parseError: e.message };
                }
                return { status, data };
            } catch(e) {
                return { status: 0, data: null, error: e.message };
            }
        }
        """
        result = await self._page.evaluate(js_code, url)
        return result

    async def fetch(self, url: str, payload: dict) -> Dict[str, Any]:
        """在浏览器内通过 JS fetch() 发起 POST 请求。

        Returns:
            {"status": int, "data": dict | None}
        """
        async with self._lock:
            await self._ensure_page()

        js_code = """
        async ([url, body]) => {
            try {
                const resp = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'clienttype': 'web',
                        'lang': 'zh-CN',
                    },
                    body: JSON.stringify(body),
                    credentials: 'include',
                });
                const status = resp.status;
                let data = null;
                try {
                    data = await resp.json();
                } catch(e) {
                    data = { parseError: e.message };
                }
                return { status, data };
            } catch(e) {
                return { status: 0, data: null, error: e.message };
            }
        }
        """
        result = await self._page.evaluate(js_code, [url, payload])
        return result

    async def force_refresh(self):
        """强制刷新浏览器会话。"""
        async with self._lock:
            await self._init_page()


# 全局单例
browser_manager = BrowserManager()
