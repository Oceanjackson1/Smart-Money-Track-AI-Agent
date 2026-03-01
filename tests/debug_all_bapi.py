"""
拦截 profile 页面的所有 bapi 请求（不限 smart-money）
"""
import asyncio
import json
import logging
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("allbapi")

from playwright.async_api import async_playwright


async def main():
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

    # WAF
    logger.info("通过 WAF...")
    await page.goto("https://www.binance.com/zh-CN/smart-money", wait_until="networkidle", timeout=60000)
    await page.wait_for_timeout(5000)

    # 拦截所有 bapi 请求 (排除 analytics)
    captured = []
    skip_patterns = ["saasexch", "sa.gif", "pda/v1", "google-analytics", "bnbstatic"]

    async def on_request(request):
        url = request.url
        if any(p in url for p in skip_patterns):
            return
        if "bapi" in url or "api" in url:
            method = request.method
            try:
                post_data = request.post_data
            except:
                post_data = None
            # 只记录，不打印太多
            captured.append({"url": url, "method": method, "post_data": post_data, "type": "req"})

    async def on_response(response):
        url = response.url
        if any(p in url for p in skip_patterns):
            return
        if "bapi" in url:
            status = response.status
            try:
                body = await response.json()
            except:
                body = None
            captured.append({"url": url, "status": status, "body": body, "type": "resp"})

    page.on("request", on_request)
    page.on("response", on_response)

    # 公开仓位交易员 ID
    trader_id = "4808778158325714688"

    # 导航到 profile 页面
    logger.info(f"导航到 profile 页面: {trader_id}")
    captured.clear()
    await page.goto(
        f"https://www.binance.com/zh-CN/smart-money/profile/{trader_id}",
        wait_until="networkidle",
        timeout=60000
    )
    await page.wait_for_timeout(8000)

    logger.info(f"初始加载捕获 {len(captured)} 个请求/响应")

    # 截图看页面结构
    await page.screenshot(path="/tmp/profile_initial.png", full_page=True)

    # 获取页面上所有可点击的 tab 和按钮
    tabs_info = await page.evaluate("""() => {
        const tabs = document.querySelectorAll('[role="tab"]');
        return Array.from(tabs).map((t, i) => ({
            index: i,
            text: t.textContent.trim().substring(0, 30),
            visible: t.offsetParent !== null,
            rect: t.getBoundingClientRect()
        }));
    }""")
    logger.info(f"\n页面上的 Tab 元素:")
    for t in tabs_info:
        logger.info(f"  #{t['index']}: '{t['text']}' visible={t['visible']} rect=({t['rect']['x']:.0f},{t['rect']['y']:.0f})")

    # 点击每个 tab
    for tab_info in tabs_info:
        text = tab_info["text"]
        if not tab_info["visible"]:
            continue
        if text in ["顶级交易员", "聪明钱信号", "我的订阅"]:
            continue  # 跳过导航 tab

        try:
            pre_count = len(captured)
            tab_elements = await page.query_selector_all('[role="tab"]')
            idx = tab_info["index"]
            if idx < len(tab_elements):
                await tab_elements[idx].click()
                await page.wait_for_timeout(5000)
                new_count = len(captured) - pre_count
                logger.info(f"\n点击 Tab '{text}' -> 新增 {new_count} 个请求/响应")

                # 截图
                safe_name = text.replace("/", "_")[:10]
                await page.screenshot(path=f"/tmp/profile_tab_{safe_name}.png")
        except Exception as e:
            logger.debug(f"点击 Tab '{text}' 失败: {e}")

    # 汇总所有捕获的 bapi 响应
    logger.info("\n" + "=" * 80)
    logger.info("所有捕获到的 bapi API 响应:")
    logger.info("=" * 80)

    seen = set()
    for c in captured:
        if c["type"] != "resp":
            continue
        url = c["url"]
        path = url.split("?")[0]
        if path in seen:
            continue
        seen.add(path)

        status = c["status"]
        body = c.get("body")
        code = body.get("code") if body else "?"
        inner = body.get("data") if body else None

        preview = ""
        if inner is not None:
            if isinstance(inner, dict):
                preview = f"keys={list(inner.keys())[:10]}"
                # 如果有 rows/list/data，展示结构
                for k in ["rows", "list", "data", "items"]:
                    if k in inner and isinstance(inner[k], list):
                        preview += f", {k}[{len(inner[k])}]"
                        if inner[k]:
                            preview += f", first_keys={list(inner[k][0].keys())[:8]}" if isinstance(inner[k][0], dict) else ""
            elif isinstance(inner, list):
                preview = f"list[{len(inner)}]"
                if inner and isinstance(inner[0], dict):
                    preview += f", first_keys={list(inner[0].keys())[:8]}"

        logger.info(f"\n  [{status}] {path}")
        logger.info(f"    code={code}, data={preview}")
        if inner and isinstance(inner, (dict, list)):
            logger.info(f"    Full data: {json.dumps(inner, ensure_ascii=False)[:600]}")

    # 也输出请求（看看有没有 POST 请求带了参数）
    logger.info("\n" + "=" * 80)
    logger.info("所有请求 URL (去重):")
    logger.info("=" * 80)
    req_seen = set()
    for c in captured:
        if c["type"] != "req":
            continue
        url = c["url"]
        path = url.split("?")[0]
        if path in req_seen:
            continue
        req_seen.add(path)
        method = c.get("method", "?")
        logger.info(f"  [{method}] {url[:200]}")
        if c.get("post_data"):
            logger.info(f"    Body: {c['post_data'][:200]}")

    await browser.close()
    await pw.stop()


asyncio.run(main())
