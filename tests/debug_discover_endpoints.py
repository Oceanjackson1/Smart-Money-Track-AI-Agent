"""
发现所有真实 API 端点：
1. 获取交易员列表
2. 找到一个公开仓位的交易员
3. 导航到其 profile 页面
4. 捕获仓位、操作记录等 API 端点
"""
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("discover")

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

    # 收集 smart-money 相关响应
    captured = []

    async def on_response(response):
        url = response.url
        if "smart-money" in url and "bapi" in url:
            status = response.status
            try:
                body = await response.json()
                body_str = json.dumps(body, ensure_ascii=False)[:1500]
            except:
                body_str = "(non-JSON)"
            captured.append({"url": url, "status": status, "body": body_str})
            logger.info(f"[CAPTURED] {status} {url}")

    page.on("response", on_response)

    # Step 1: 导航到主页获取 trader list
    logger.info("Step 1: 导航到主页...")
    await page.goto("https://www.binance.com/zh-CN/smart-money", wait_until="networkidle", timeout=60000)
    await page.wait_for_timeout(5000)

    # Step 2: 从 trader list 响应中找到公开仓位的交易员
    logger.info("Step 2: 分析交易员列表，寻找公开仓位的交易员...")
    target_id = None
    for resp in captured:
        if "top-trader/list" in resp["url"] and resp["status"] == 200:
            try:
                body = json.loads(resp["body"])
                rows = body.get("data", {}).get("rows", [])
                logger.info(f"  交易员列表共 {len(rows)} 人")
                for row in rows:
                    tid = row.get("topTraderId", "")
                    name = row.get("traderName", "")
                    logger.info(f"  - {name} (ID: {tid}), keys: {list(row.keys())}")
                # 先记住所有 ID，后面通过 profile 检查
                if rows:
                    target_id = rows[0].get("topTraderId", "")
            except Exception as e:
                logger.error(f"解析失败: {e}")

    if not target_id:
        logger.error("未找到任何交易员，退出")
        await browser.close()
        await pw.stop()
        return

    # Step 3: 逐个检查 profile 找到公开仓位的交易员
    logger.info("Step 3: 逐个检查交易员 profile...")
    sharing_trader_id = None

    # 获取更多交易员（翻页）
    all_trader_ids = []
    for resp in captured:
        if "top-trader/list" in resp["url"] and resp["status"] == 200:
            try:
                body = json.loads(resp["body"])
                rows = body.get("data", {}).get("rows", [])
                all_trader_ids = [r.get("topTraderId") for r in rows if r.get("topTraderId")]
            except:
                pass

    for tid in all_trader_ids:
        profile_url = f"https://www.binance.com/bapi/asset/v1/friendly/future/smart-money/profile?topTraderId={tid}"
        result = await page.evaluate("""async (url) => {
            try {
                const resp = await fetch(url);
                return await resp.json();
            } catch(e) {
                return {error: e.message};
            }
        }""", profile_url)

        data = result.get("data", {}) if isinstance(result, dict) else {}
        sharing_pos = data.get("sharingPosition", False)
        sharing_hist = data.get("sharingPositionHistory", False)
        sharing_ops = data.get("sharingLatestRecord", False)
        name = data.get("traderName", "?")
        logger.info(f"  {name} (ID: {tid}): position={sharing_pos}, history={sharing_hist}, ops={sharing_ops}")

        if sharing_pos or sharing_hist or sharing_ops:
            sharing_trader_id = tid
            logger.info(f"  >>> 找到公开数据的交易员: {name} (ID: {tid})")
            break

    if not sharing_trader_id:
        logger.warning("前10名均未公开仓位，尝试获取更多交易员...")
        # 翻到 page 2-5
        for pg in range(2, 6):
            list_url = f"https://www.binance.com/bapi/futures/v1/friendly/future/smart-money/top-trader/list?page={pg}&rows=10&timeRange=30D&rankingType=PNL&onlyShowSharingPosition=true&order=DESC"
            result = await page.evaluate("""async (url) => {
                try {
                    const resp = await fetch(url);
                    return await resp.json();
                } catch(e) {
                    return {error: e.message};
                }
            }""", list_url)
            rows = result.get("data", {}).get("rows", []) if isinstance(result, dict) else []
            for row in rows:
                tid = row.get("topTraderId", "")
                name = row.get("traderName", "?")
                if not tid:
                    continue
                # 检查 profile
                profile_url = f"https://www.binance.com/bapi/asset/v1/friendly/future/smart-money/profile?topTraderId={tid}"
                profile = await page.evaluate("""async (url) => {
                    try {
                        const resp = await fetch(url);
                        return await resp.json();
                    } catch(e) {
                        return {error: e.message};
                    }
                }""", profile_url)
                pdata = profile.get("data", {}) if isinstance(profile, dict) else {}
                sp = pdata.get("sharingPosition", False)
                sh = pdata.get("sharingPositionHistory", False)
                so = pdata.get("sharingLatestRecord", False)
                logger.info(f"  {name} (ID: {tid}): pos={sp}, hist={sh}, ops={so}")
                if sp or sh or so:
                    sharing_trader_id = tid
                    logger.info(f"  >>> 找到: {name}")
                    break
            if sharing_trader_id:
                break

    if not sharing_trader_id:
        # 最后尝试：用 onlyShowSharingPosition=true 直接筛选
        logger.warning("仍未找到，使用 onlyShowSharingPosition=true 筛选...")
        list_url = "https://www.binance.com/bapi/futures/v1/friendly/future/smart-money/top-trader/list?page=1&rows=10&timeRange=30D&rankingType=PNL&onlyShowSharingPosition=true&order=DESC"
        result = await page.evaluate("""async (url) => {
            try {
                const resp = await fetch(url);
                return await resp.json();
            } catch(e) {
                return {error: e.message};
            }
        }""", list_url)
        rows = result.get("data", {}).get("rows", []) if isinstance(result, dict) else []
        if rows:
            sharing_trader_id = rows[0].get("topTraderId", "")
            logger.info(f"  筛选到: {rows[0].get('traderName')} (ID: {sharing_trader_id})")

    # Step 4: 导航到该交易员 profile 页面，捕获仓位/操作 API
    if sharing_trader_id:
        logger.info(f"\nStep 4: 导航到交易员 profile 页面 (ID: {sharing_trader_id})...")
        captured.clear()
        profile_page_url = f"https://www.binance.com/zh-CN/smart-money/profile/{sharing_trader_id}"
        await page.goto(profile_page_url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(8000)

        logger.info(f"  profile 页面捕获到 {len(captured)} 个 smart-money 相关响应")

        # 尝试点击 Tab 触发更多请求
        for tab_text in ["当前仓位", "仓位历史", "最新操作", "Position", "History", "Operation"]:
            try:
                tab = page.get_by_text(tab_text, exact=False).first
                if await tab.is_visible():
                    pre = len(captured)
                    await tab.click()
                    await page.wait_for_timeout(3000)
                    logger.info(f"  点击 '{tab_text}' 后新增 {len(captured) - pre} 个请求")
            except:
                pass

    # Step 5: 同时尝试直接 fetch 可能的端点
    logger.info("\nStep 5: 尝试直接 fetch 可能的端点...")
    test_tid = sharing_trader_id or target_id
    candidate_urls = [
        # 基于 /bapi/asset/v1/ 路径
        f"https://www.binance.com/bapi/asset/v1/friendly/future/smart-money/profile/position?topTraderId={test_tid}",
        f"https://www.binance.com/bapi/asset/v1/friendly/future/smart-money/profile/position-history?topTraderId={test_tid}&page=1&rows=10",
        f"https://www.binance.com/bapi/asset/v1/friendly/future/smart-money/profile/latest-operation?topTraderId={test_tid}&page=1&rows=10",
        f"https://www.binance.com/bapi/asset/v1/friendly/future/smart-money/profile/operation?topTraderId={test_tid}&page=1&rows=10",
        f"https://www.binance.com/bapi/asset/v1/friendly/future/smart-money/profile/current-position?topTraderId={test_tid}",
        # 基于 /bapi/futures/v1/ 路径
        f"https://www.binance.com/bapi/futures/v1/friendly/future/smart-money/top-trader/position?topTraderId={test_tid}",
        f"https://www.binance.com/bapi/futures/v1/friendly/future/smart-money/top-trader/position-history?topTraderId={test_tid}&page=1&rows=10",
        f"https://www.binance.com/bapi/futures/v1/friendly/future/smart-money/top-trader/operation?topTraderId={test_tid}&page=1&rows=10",
        f"https://www.binance.com/bapi/futures/v1/friendly/future/smart-money/top-trader/latest-operation?topTraderId={test_tid}&page=1&rows=10",
        # 可能的 POST 端点 (老版 API)
    ]

    for url in candidate_urls:
        result = await page.evaluate("""async (url) => {
            try {
                const resp = await fetch(url);
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
        code = data.get("code", "?") if data else "?"
        msg = data.get("message", "") if data else ""
        success = data.get("success", "") if data else ""
        # 提取关键信息
        data_preview = ""
        if data and data.get("data"):
            inner = data["data"]
            if isinstance(inner, dict):
                data_preview = f"keys={list(inner.keys())[:8]}"
            elif isinstance(inner, list):
                data_preview = f"list[{len(inner)}]"

        path = url.split("binance.com")[1].split("?")[0]
        logger.info(f"  [{status}] {path} -> code={code}, msg={msg}, {data_preview}")

    # 汇总
    logger.info("\n" + "=" * 60)
    logger.info("所有捕获到的 smart-money 相关 API:")
    logger.info("=" * 60)
    for resp in captured:
        logger.info(f"\n  [{resp['status']}] {resp['url']}")
        logger.info(f"  Body: {resp['body'][:500]}")

    await browser.close()
    await pw.stop()


asyncio.run(main())
