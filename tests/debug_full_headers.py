"""
用浏览器完整 headers 调用 POST 端点
"""
import asyncio
import json
import logging
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("headers")

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

    # 从页面获取 cookies 和必要的 token
    cookies = await context.cookies()
    cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
    logger.info(f"获取到 {len(cookies)} 个 cookies")

    # 获取 csrftoken 和 bnc-uuid
    csrf = ""
    bnc_uuid = ""
    for c in cookies:
        if c["name"] == "csrftoken":
            csrf = c["value"]
        if c["name"] == "bnc-uuid":
            bnc_uuid = c["value"]

    logger.info(f"csrftoken: {csrf[:20]}...")
    logger.info(f"bnc-uuid: {bnc_uuid}")

    trader_id = "4808778158325714688"

    # 方式 1: 在浏览器内 fetch，用 page 自带的 cookie 和完整 headers
    logger.info("\n方式 1: 浏览器内 fetch + 完整 headers")

    endpoints = [
        ("getTraderList", {"rankingType": "PNL", "timeRange": "30D", "pageIndex": 1, "pageSize": 5}),
        ("getPositionList", {"traderId": trader_id, "tradeType": "PERPETUAL"}),
        ("getPositionHistory", {"traderId": trader_id, "pageIndex": 1, "pageSize": 5}),
        ("getLatestOperation", {"traderId": trader_id, "pageIndex": 1, "pageSize": 5}),
        ("getTraderProfile", {"traderId": trader_id, "rankingType": "PNL", "timeRange": "30D"}),
    ]

    for endpoint, body in endpoints:
        url = f"https://www.binance.com/bapi/smart-money/v1/public/smart-money/{endpoint}"
        result = await page.evaluate("""async ([url, body]) => {
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
                const text = await resp.text();
                let data = null;
                try { data = JSON.parse(text); } catch(e) {}
                return {status, data, textPreview: text.substring(0, 500)};
            } catch(e) {
                return {status: 0, error: e.message};
            }
        }""", [url, body])

        status = result.get("status", 0)
        data = result.get("data")
        text = result.get("textPreview", "")

        if data:
            code = data.get("code", "?")
            msg = data.get("message", "")
            inner = data.get("data")
            preview = ""
            if inner is not None:
                if isinstance(inner, dict):
                    preview = f"dict keys={list(inner.keys())[:8]}"
                elif isinstance(inner, list):
                    preview = f"list[{len(inner)}]"
                    if inner and isinstance(inner[0], dict):
                        preview += f" keys={list(inner[0].keys())[:6]}"
            marker = "OK" if str(code) == "000000" else "  "
            logger.info(f"  [{marker}] [{status}] {endpoint} -> code={code}, msg={msg}, data={preview}")
            if marker == "OK" and inner:
                logger.info(f"    >>> {json.dumps(inner, ensure_ascii=False)[:800]}")
        else:
            logger.info(f"  [  ] [{status}] {endpoint} -> text={text[:200]}")

    # 方式 2: 尝试新的 GET API 路径获取仓位（基于 topTraderId）
    logger.info("\n方式 2: 尝试 GET API 路径 (带 topTraderId)")
    get_endpoints = [
        f"/bapi/asset/v1/friendly/future/smart-money/profile/position-list?topTraderId={trader_id}",
        f"/bapi/asset/v1/friendly/future/smart-money/profile/positions?topTraderId={trader_id}",
        f"/bapi/asset/v1/friendly/future/smart-money/profile/current-positions?topTraderId={trader_id}",
        f"/bapi/asset/v1/friendly/future/smart-money/top-trader/positions?topTraderId={trader_id}",
        f"/bapi/futures/v1/friendly/future/smart-money/position/list?topTraderId={trader_id}",
        f"/bapi/futures/v1/friendly/future/smart-money/position?topTraderId={trader_id}",
        f"/bapi/futures/v1/friendly/future/smart-money/positions?topTraderId={trader_id}",
    ]

    for path in get_endpoints:
        url = f"https://www.binance.com{path}"
        result = await page.evaluate("""async (url) => {
            try {
                const resp = await fetch(url, {credentials: 'include'});
                const status = resp.status;
                let data = null;
                try { data = await resp.json(); } catch(e) {}
                return {status, data};
            } catch(e) {
                return {status: 0, error: e.message};
            }
        }""", url)

        status = result.get("status", 0)
        data = result.get("data")
        code = data.get("code") if data else "?"
        short = path.split("?")[0]
        is_ok = status == 200 and str(code) == "000000"
        marker = "OK" if is_ok else "  "
        logger.info(f"  [{marker}] [{status}] {short} code={code}")
        if is_ok:
            inner = data.get("data")
            logger.info(f"    >>> {json.dumps(inner, ensure_ascii=False)[:500]}")

    await browser.close()
    await pw.stop()


asyncio.run(main())
