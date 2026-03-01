"""
调试脚本：拦截 Binance Smart Money 页面的真实网络请求
目的：找到页面实际使用的 API 端点和请求格式
"""
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("debug")

from playwright.async_api import async_playwright


async def main():
    logger.info("启动浏览器，拦截 Binance Smart Money 页面的 API 请求...")

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
    )
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1920, "height": 1080},
        locale="zh-CN",
    )
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)

    page = await context.new_page()

    # 收集所有 API 请求
    api_requests = []
    api_responses = []

    async def on_response(response):
        url = response.url
        # 只关注 bapi 或 smart-money 相关
        if "bapi" in url or "smart-money" in url or "leaderboard" in url:
            status = response.status
            try:
                body = await response.json()
                body_preview = json.dumps(body, ensure_ascii=False)[:500]
            except:
                body_preview = "(non-JSON)"

            api_responses.append({
                "url": url,
                "status": status,
                "body_preview": body_preview,
            })
            logger.info(f"  [API Response] {status} {url}")
            logger.info(f"    Body: {body_preview[:200]}")

    page.on("response", on_response)

    async def on_request(request):
        url = request.url
        if "bapi" in url or "smart-money" in url or "leaderboard" in url:
            method = request.method
            headers = request.headers
            try:
                post_data = request.post_data
            except:
                post_data = None
            api_requests.append({
                "url": url,
                "method": method,
                "post_data": post_data,
                "headers": {k: v for k, v in headers.items() if k in [
                    "content-type", "clienttype", "lang", "csrftoken",
                    "x-trace-id", "x-ui-request-trace", "fvideo-id", "bnc-uuid",
                    "cookie",
                ]},
            })
            logger.info(f"  [API Request] {method} {url}")
            if post_data:
                logger.info(f"    PostData: {post_data[:200]}")
            # 打印关键 headers
            for k in ["csrftoken", "x-trace-id", "fvideo-id", "bnc-uuid"]:
                if k in headers:
                    logger.info(f"    Header {k}: {headers[k][:50]}")

    page.on("request", on_request)

    logger.info("导航到 Smart Money 页面...")
    await page.goto("https://www.binance.com/zh-CN/smart-money", wait_until="networkidle", timeout=60000)
    await page.wait_for_timeout(8000)

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"捕获到 {len(api_requests)} 个 API 请求, {len(api_responses)} 个响应")
    logger.info("=" * 60)

    for i, req in enumerate(api_requests):
        logger.info(f"\n--- 请求 #{i+1} ---")
        logger.info(f"  URL: {req['url']}")
        logger.info(f"  Method: {req['method']}")
        if req['post_data']:
            logger.info(f"  PostData: {req['post_data'][:300]}")
        if req['headers']:
            logger.info(f"  Key Headers: {json.dumps(req['headers'], indent=2)}")

    for i, resp in enumerate(api_responses):
        logger.info(f"\n--- 响应 #{i+1} ---")
        logger.info(f"  URL: {resp['url']}")
        logger.info(f"  Status: {resp['status']}")
        logger.info(f"  Body: {resp['body_preview'][:300]}")

    await browser.close()
    await pw.stop()


asyncio.run(main())
