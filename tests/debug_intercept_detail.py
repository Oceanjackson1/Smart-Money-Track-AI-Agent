"""
调试脚本：捕获交易员详情页的 API 端点
导航到 Smart Money 页面 → 点击第一个交易员 → 分别点击仓位/历史/操作 Tab
"""
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("debug_detail")

from playwright.async_api import async_playwright


async def main():
    logger.info("启动浏览器，捕获交易员详情页的 API 端点...")

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

    # 收集所有 API 请求和响应
    all_requests = []
    all_responses = []

    async def on_response(response):
        url = response.url
        if "bapi" in url or "smart-money" in url:
            status = response.status
            try:
                body = await response.json()
                body_str = json.dumps(body, ensure_ascii=False)[:800]
            except:
                body_str = "(non-JSON)"
            all_responses.append({
                "url": url,
                "status": status,
                "body": body_str,
            })
            logger.info(f"[RESP] {status} {url}")

    async def on_request(request):
        url = request.url
        if "bapi" in url or "smart-money" in url:
            method = request.method
            try:
                post_data = request.post_data
            except:
                post_data = None
            all_requests.append({
                "url": url,
                "method": method,
                "post_data": post_data,
            })
            logger.info(f"[REQ] {method} {url}")
            if post_data:
                logger.info(f"  Body: {post_data[:300]}")

    page.on("response", on_response)
    page.on("request", on_request)

    # Step 1: 导航到主页
    logger.info("=" * 60)
    logger.info("Step 1: 导航到 Smart Money 主页")
    logger.info("=" * 60)
    await page.goto("https://www.binance.com/zh-CN/smart-money", wait_until="networkidle", timeout=60000)
    await page.wait_for_timeout(5000)

    logger.info(f"\n主页捕获到 {len(all_requests)} 个请求")

    # Step 2: 找到并点击第一个交易员
    logger.info("")
    logger.info("=" * 60)
    logger.info("Step 2: 点击第一个交易员进入详情页")
    logger.info("=" * 60)

    # 截图看看当前页面布局
    await page.screenshot(path="/tmp/smart_money_main.png")
    logger.info("主页截图保存到 /tmp/smart_money_main.png")

    # 尝试找到交易员链接
    # 常见选择器：表格行的链接、card 链接等
    trader_links = await page.query_selector_all('a[href*="smart-money/trader"]')
    if not trader_links:
        trader_links = await page.query_selector_all('a[href*="smart-money"]')
    if not trader_links:
        # 尝试获取页面所有链接
        all_links = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a')).map(a => ({
                href: a.href,
                text: a.textContent.trim().substring(0, 50)
            })).filter(l => l.href.includes('smart-money') || l.href.includes('trader'));
        }""")
        logger.info(f"页面中 smart-money/trader 相关链接: {json.dumps(all_links, ensure_ascii=False)[:1000]}")

    if trader_links:
        href = await trader_links[0].get_attribute("href")
        logger.info(f"找到交易员链接: {href}")

        # 记录点击前的请求数
        pre_click_count = len(all_requests)

        await trader_links[0].click()
        await page.wait_for_timeout(5000)
        await page.wait_for_load_state("networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        logger.info(f"点击后新增 {len(all_requests) - pre_click_count} 个请求")
        await page.screenshot(path="/tmp/smart_money_detail.png")
        logger.info("详情页截图保存到 /tmp/smart_money_detail.png")
    else:
        logger.warning("未找到交易员链接，尝试通过 URL 直接访问...")
        # 如果从主页 API 响应中能找到 traderId，直接构造 URL
        for resp in all_responses:
            if "top-trader/list" in resp["url"] and resp["status"] == 200:
                try:
                    body = json.loads(resp["body"][:800])
                    rows = body.get("data", {}).get("rows", [])
                    if rows:
                        tid = rows[0].get("topTraderId", "")
                        if tid:
                            detail_url = f"https://www.binance.com/zh-CN/smart-money/trader?traderId={tid}"
                            logger.info(f"直接导航到: {detail_url}")
                            pre_count = len(all_requests)
                            await page.goto(detail_url, wait_until="networkidle", timeout=60000)
                            await page.wait_for_timeout(5000)
                            logger.info(f"详情页新增 {len(all_requests) - pre_count} 个请求")
                            await page.screenshot(path="/tmp/smart_money_detail.png")
                            break
                except:
                    pass

    # Step 3: 尝试点击各个 Tab (仓位/历史/操作)
    logger.info("")
    logger.info("=" * 60)
    logger.info("Step 3: 尝试切换 Tab 查看不同数据")
    logger.info("=" * 60)

    tabs = await page.evaluate("""() => {
        const tabs = document.querySelectorAll('[role="tab"], .tab, button');
        return Array.from(tabs).map(t => ({
            text: t.textContent.trim().substring(0, 30),
            tag: t.tagName,
            role: t.getAttribute('role'),
        }));
    }""")
    logger.info(f"页面 Tab/Button 元素: {json.dumps(tabs, ensure_ascii=False)[:1000]}")

    for tab_text in ["历史", "History", "操作", "Operation", "仓位", "Position"]:
        try:
            tab = page.get_by_text(tab_text, exact=False).first
            if tab:
                pre_count = len(all_requests)
                await tab.click()
                await page.wait_for_timeout(3000)
                new_count = len(all_requests) - pre_count
                if new_count > 0:
                    logger.info(f"点击 '{tab_text}' Tab 后新增 {new_count} 个请求")
        except Exception as e:
            logger.debug(f"Tab '{tab_text}' 点击失败: {e}")

    # 最终汇总
    logger.info("")
    logger.info("=" * 60)
    logger.info(f"总计捕获 {len(all_requests)} 个请求, {len(all_responses)} 个响应")
    logger.info("=" * 60)

    # 去重打印所有唯一的 API endpoint
    seen_urls = set()
    for req in all_requests:
        # 提取 path 部分 (去掉 query string 中的动态参数)
        url = req["url"]
        path = url.split("?")[0] if "?" in url else url
        if path not in seen_urls:
            seen_urls.add(path)
            logger.info(f"\n  [{req['method']}] {url}")
            if req["post_data"]:
                logger.info(f"    Body: {req['post_data'][:300]}")

    logger.info("")
    logger.info("=" * 60)
    logger.info("所有响应详情:")
    logger.info("=" * 60)
    for i, resp in enumerate(all_responses):
        logger.info(f"\n--- 响应 #{i+1} ---")
        logger.info(f"  URL: {resp['url']}")
        logger.info(f"  Status: {resp['status']}")
        logger.info(f"  Body: {resp['body'][:500]}")

    await browser.close()
    await pw.stop()


asyncio.run(main())
