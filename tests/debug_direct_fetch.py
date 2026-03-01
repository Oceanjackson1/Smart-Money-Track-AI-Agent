"""
直接通过浏览器 fetch 调用已知和候选 API 端点，发现全部可用端点
"""
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("direct")

from playwright.async_api import async_playwright


async def browser_fetch(page, url):
    """在浏览器内执行 fetch"""
    return await page.evaluate("""async (url) => {
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

    # Step 1: WAF
    logger.info("Step 1: 通过 WAF...")
    await page.goto("https://www.binance.com/zh-CN/smart-money", wait_until="networkidle", timeout=60000)
    await page.wait_for_timeout(5000)
    logger.info("WAF done")

    # Step 2: 获取交易员列表
    logger.info("\nStep 2: 获取交易员列表...")
    base = "https://www.binance.com"

    result = await browser_fetch(page,
        f"{base}/bapi/futures/v1/friendly/future/smart-money/top-trader/list?page=1&rows=10&timeRange=30D&rankingType=PNL&onlyShowSharingPosition=false&order=DESC"
    )
    data = result.get("data", {})
    rows = data.get("data", {}).get("rows", []) if data else []
    logger.info(f"  status={result.get('status')}, code={data.get('code') if data else '?'}")
    logger.info(f"  total={data.get('data', {}).get('total') if data else '?'}, rows={len(rows)}")

    if rows:
        # 打印完整第一个交易员数据
        logger.info(f"\n  首个交易员完整数据:")
        logger.info(json.dumps(rows[0], ensure_ascii=False, indent=2))

    # 使用 onlyShowSharingPosition=true 筛选
    logger.info("\nStep 2b: 获取公开仓位的交易员...")
    result2 = await browser_fetch(page,
        f"{base}/bapi/futures/v1/friendly/future/smart-money/top-trader/list?page=1&rows=10&timeRange=30D&rankingType=PNL&onlyShowSharingPosition=true&order=DESC"
    )
    data2 = result2.get("data", {})
    rows2 = data2.get("data", {}).get("rows", []) if data2 else []
    logger.info(f"  公开仓位交易员: total={data2.get('data', {}).get('total') if data2 else '?'}, rows={len(rows2)}")

    if rows2:
        logger.info(f"  首个公开仓位交易员:")
        logger.info(json.dumps(rows2[0], ensure_ascii=False, indent=2))

    # 选一个有公开仓位的交易员
    test_tid = rows2[0].get("topTraderId") if rows2 else (rows[0].get("topTraderId") if rows else None)
    if not test_tid:
        logger.error("无交易员 ID")
        await browser.close()
        await pw.stop()
        return

    logger.info(f"\n使用交易员 ID: {test_tid}")

    # Step 3: Profile
    logger.info("\nStep 3: 获取交易员 Profile...")
    profile = await browser_fetch(page,
        f"{base}/bapi/asset/v1/friendly/future/smart-money/profile?topTraderId={test_tid}"
    )
    pdata = profile.get("data", {})
    if pdata and pdata.get("data"):
        pd = pdata["data"]
        logger.info(f"  Profile 完整数据:")
        logger.info(json.dumps(pd, ensure_ascii=False, indent=2))
    else:
        logger.info(f"  Profile: status={profile.get('status')}, data={json.dumps(pdata, ensure_ascii=False)[:500]}")

    # Step 4: 尝试所有可能的端点
    logger.info("\nStep 4: 探测所有可能的仓位/操作端点...")
    candidates = [
        # /bapi/asset/v1 路径
        ("GET", f"/bapi/asset/v1/friendly/future/smart-money/profile/position?topTraderId={test_tid}"),
        ("GET", f"/bapi/asset/v1/friendly/future/smart-money/profile/position-list?topTraderId={test_tid}"),
        ("GET", f"/bapi/asset/v1/friendly/future/smart-money/profile/current-position?topTraderId={test_tid}"),
        ("GET", f"/bapi/asset/v1/friendly/future/smart-money/profile/position-history?topTraderId={test_tid}&page=1&rows=10"),
        ("GET", f"/bapi/asset/v1/friendly/future/smart-money/profile/latest-operation?topTraderId={test_tid}&page=1&rows=10"),
        ("GET", f"/bapi/asset/v1/friendly/future/smart-money/profile/latest-record?topTraderId={test_tid}&page=1&rows=10"),
        ("GET", f"/bapi/asset/v1/friendly/future/smart-money/profile/operation-history?topTraderId={test_tid}&page=1&rows=10"),
        # /bapi/futures/v1 路径
        ("GET", f"/bapi/futures/v1/friendly/future/smart-money/top-trader/position?topTraderId={test_tid}"),
        ("GET", f"/bapi/futures/v1/friendly/future/smart-money/top-trader/position-list?topTraderId={test_tid}"),
        ("GET", f"/bapi/futures/v1/friendly/future/smart-money/top-trader/position-history?topTraderId={test_tid}&page=1&rows=10"),
        ("GET", f"/bapi/futures/v1/friendly/future/smart-money/top-trader/latest-operation?topTraderId={test_tid}&page=1&rows=10"),
        ("GET", f"/bapi/futures/v1/friendly/future/smart-money/top-trader/operation?topTraderId={test_tid}&page=1&rows=10"),
        # /bapi/futures/v2 路径
        ("GET", f"/bapi/futures/v2/friendly/future/smart-money/top-trader/position?topTraderId={test_tid}"),
        # 可能使用 traderId 而非 topTraderId
        ("GET", f"/bapi/asset/v1/friendly/future/smart-money/profile/position?traderId={test_tid}"),
        ("GET", f"/bapi/futures/v1/friendly/future/smart-money/top-trader/position?traderId={test_tid}"),
        # 可能用 encryptedUid
        ("GET", f"/bapi/asset/v1/friendly/future/smart-money/profile/position?encryptedUid={test_tid}"),
    ]

    for method, path in candidates:
        url = f"{base}{path}"
        result = await browser_fetch(page, url)
        status = result.get("status", 0)
        resp_data = result.get("data")
        code = resp_data.get("code", "?") if resp_data else "?"
        msg = resp_data.get("message", "") if resp_data else ""
        inner = resp_data.get("data") if resp_data else None

        # 判断是否有效
        is_valid = status == 200 and code == "000000"
        marker = "OK" if is_valid else f"  "

        preview = ""
        if inner is not None:
            if isinstance(inner, dict):
                preview = f"dict keys={list(inner.keys())[:8]}"
            elif isinstance(inner, list):
                preview = f"list[{len(inner)}]"
            elif inner is None:
                preview = "null"
            else:
                preview = str(type(inner).__name__)

        short_path = path.split("?")[0]
        logger.info(f"  [{marker}] [{status}] {short_path} -> code={code}, data={preview}, msg={msg}")

        # 如果找到有效的端点，打印完整数据
        if is_valid and inner:
            logger.info(f"    >>> 完整数据: {json.dumps(inner, ensure_ascii=False)[:800]}")

    # Step 5: 导航到 profile 页面，用网络拦截补全未发现的端点
    logger.info("\nStep 5: 导航到 profile 页面拦截网络请求...")
    new_captured = []

    async def on_resp(response):
        url = response.url
        if "smart-money" in url and "bapi" in url and "i18n" not in url:
            try:
                body = await response.json()
                new_captured.append({"url": url, "status": response.status, "body": body})
                logger.info(f"  [NET] {response.status} {url}")
            except:
                pass

    page.on("response", on_resp)

    profile_page = f"https://www.binance.com/zh-CN/smart-money/profile/{test_tid}"
    logger.info(f"  导航到: {profile_page}")
    await page.goto(profile_page, wait_until="networkidle", timeout=60000)
    await page.wait_for_timeout(8000)

    # 截图
    await page.screenshot(path="/tmp/smart_money_profile.png")

    # 点击各个 tab
    for tab_text in ["当前仓位", "仓位历史", "最新操作记录"]:
        try:
            tab = page.get_by_text(tab_text, exact=True).first
            if await tab.is_visible():
                await tab.click()
                await page.wait_for_timeout(3000)
                logger.info(f"  点击了 '{tab_text}' Tab")
        except Exception as e:
            logger.debug(f"  Tab '{tab_text}' 不可见: {e}")

    logger.info(f"\n  网络拦截到 {len(new_captured)} 个 smart-money API 响应:")
    for c in new_captured:
        inner = c["body"].get("data") if c["body"] else None
        preview = ""
        if inner is not None:
            if isinstance(inner, dict):
                preview = f"dict keys={list(inner.keys())[:10]}"
            elif isinstance(inner, list):
                preview = f"list[{len(inner)}]"
        logger.info(f"  [{c['status']}] {c['url']}")
        logger.info(f"    data={preview}, body={json.dumps(c['body'], ensure_ascii=False)[:600]}")

    await browser.close()
    await pw.stop()


asyncio.run(main())
