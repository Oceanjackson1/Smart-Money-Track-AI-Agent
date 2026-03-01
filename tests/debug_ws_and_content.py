"""
检查 WebSocket 连接和页面实际渲染内容
"""
import asyncio
import json
import logging
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ws")

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

    # 拦截 WebSocket
    ws_messages = []
    page.on("websocket", lambda ws: logger.info(f"WebSocket opened: {ws.url}"))

    # 拦截所有请求 (包括 XHR)
    all_requests = []

    async def on_request(request):
        url = request.url
        resource_type = request.resource_type
        if resource_type in ["xhr", "fetch"] and "binance.com" in url:
            method = request.method
            all_requests.append({"url": url, "method": method, "type": resource_type})
            if "position" in url.lower() or "operation" in url.lower() or "record" in url.lower():
                logger.info(f"[!!!] {method} {url}")

    page.on("request", on_request)

    # WAF
    await page.goto("https://www.binance.com/zh-CN/smart-money", wait_until="networkidle", timeout=60000)
    await page.wait_for_timeout(5000)

    trader_id = "4808778158325714688"
    logger.info(f"\n导航到 profile 页面: {trader_id}")
    all_requests.clear()

    await page.goto(
        f"https://www.binance.com/zh-CN/smart-money/profile/{trader_id}",
        wait_until="networkidle",
        timeout=60000
    )
    await page.wait_for_timeout(8000)

    # 检查 WebSocket
    logger.info("\nXHR/fetch 请求汇总:")
    for r in all_requests:
        logger.info(f"  [{r['type']}] [{r['method']}] {r['url'][:200]}")

    # 检查页面实际内容 - 获取仓位区域的文本
    logger.info("\n检查仓位区域的文本内容...")

    content = await page.evaluate("""() => {
        const body = document.body.innerText;
        // 找包含 "仓位" 附近的文本
        const lines = body.split('\\n').filter(l => l.trim());
        const positionSection = [];
        let inSection = false;
        for (const line of lines) {
            if (line.includes('仓位') || line.includes('Position') || line.includes('操作记录')) {
                inSection = true;
            }
            if (inSection) {
                positionSection.push(line.trim());
                if (positionSection.length > 30) break;
            }
        }
        return {
            positionSection,
            allText: body.substring(0, 3000)
        };
    }""")

    logger.info(f"仓位区域文本:")
    for line in content.get("positionSection", []):
        logger.info(f"  | {line}")

    # 搜索 JS 源码中的 API URL
    logger.info("\n搜索页面 JS 中的 smart-money API URL 模式...")
    api_patterns = await page.evaluate("""() => {
        const scripts = document.querySelectorAll('script[src]');
        const srcs = Array.from(scripts).map(s => s.src).filter(s => s.includes('chunk') || s.includes('smart'));
        return srcs;
    }""")

    logger.info(f"发现 {len(api_patterns)} 个可能相关的 JS 文件:")
    for src in api_patterns[:5]:
        logger.info(f"  {src}")

    # 直接在浏览器用 fetch 尝试 POST 方式调用
    logger.info("\n尝试 POST 方式调用可能的端点...")
    post_candidates = [
        ("/bapi/futures/v1/public/future/smart-money/getPositionList", {"traderId": trader_id, "tradeType": "PERPETUAL"}),
        ("/bapi/futures/v1/friendly/future/smart-money/getPositionList", {"traderId": trader_id, "tradeType": "PERPETUAL"}),
        ("/bapi/asset/v1/friendly/future/smart-money/getPositionList", {"traderId": trader_id, "tradeType": "PERPETUAL"}),
        ("/bapi/futures/v1/public/future/smart-money/getTraderPosition", {"traderId": trader_id}),
        ("/bapi/futures/v1/friendly/future/smart-money/top-trader/position", {"topTraderId": trader_id}),
        ("/bapi/asset/v1/friendly/future/smart-money/profile/position", {"topTraderId": trader_id}),
        ("/bapi/futures/v1/public/future/smart-money/getPositionHistory", {"traderId": trader_id, "pageIndex": 1, "pageSize": 10}),
        ("/bapi/futures/v1/public/future/smart-money/getLatestOperation", {"traderId": trader_id, "pageIndex": 1, "pageSize": 10}),
        ("/bapi/smart-money/v1/public/smart-money/getPositionList", {"traderId": trader_id, "tradeType": "PERPETUAL"}),
        ("/bapi/smart-money/v1/public/smart-money/getPositionHistory", {"traderId": trader_id, "pageIndex": 1, "pageSize": 10}),
        ("/bapi/smart-money/v1/public/smart-money/getLatestOperation", {"traderId": trader_id, "pageIndex": 1, "pageSize": 10}),
        ("/bapi/smart-money/v1/public/smart-money/getTraderProfile", {"traderId": trader_id}),
    ]

    for path, body in post_candidates:
        url = f"https://www.binance.com{path}"
        result = await page.evaluate("""async ([url, body]) => {
            try {
                const resp = await fetch(url, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'clienttype': 'web'},
                    body: JSON.stringify(body)
                });
                const status = resp.status;
                let data = null;
                try { data = await resp.json(); } catch(e) {}
                return {status, data};
            } catch(e) {
                return {status: 0, error: e.message};
            }
        }""", [url, body])

        status = result.get("status", 0)
        data = result.get("data")
        code = data.get("code") if data else "?"
        msg = data.get("message", "") if data else ""
        inner = data.get("data") if data else None

        marker = "OK" if status == 200 and str(code) == "000000" else "  "
        preview = ""
        if inner is not None:
            if isinstance(inner, dict):
                preview = f"dict keys={list(inner.keys())[:8]}"
            elif isinstance(inner, list):
                preview = f"list[{len(inner)}]"
                if inner and isinstance(inner[0], dict):
                    preview += f" keys={list(inner[0].keys())[:6]}"
            else:
                preview = str(type(inner).__name__)

        logger.info(f"  [{marker}] [{status}] POST {path}")
        logger.info(f"    code={code}, msg={msg}, data={preview}")
        if marker == "OK" and inner:
            logger.info(f"    >>> {json.dumps(inner, ensure_ascii=False)[:600]}")

    await browser.close()
    await pw.stop()


asyncio.run(main())
