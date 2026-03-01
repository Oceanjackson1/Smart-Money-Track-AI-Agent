"""
提取 profile 页面的 SSR 嵌入数据（__NEXT_DATA__）
"""
import asyncio
import json
import logging
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ssr")

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
    await page.goto("https://www.binance.com/zh-CN/smart-money", wait_until="networkidle", timeout=60000)
    await page.wait_for_timeout(5000)

    trader_id = "4808778158325714688"
    logger.info(f"导航到 profile 页面: {trader_id}")
    await page.goto(
        f"https://www.binance.com/zh-CN/smart-money/profile/{trader_id}",
        wait_until="networkidle",
        timeout=60000
    )
    await page.wait_for_timeout(5000)

    # 提取 __NEXT_DATA__
    next_data = await page.evaluate("""() => {
        const el = document.getElementById('__NEXT_DATA__');
        if (el) return el.textContent;
        return null;
    }""")

    if next_data:
        data = json.loads(next_data)
        # 保存完整数据
        with open("/tmp/next_data.json", "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"__NEXT_DATA__ 已保存到 /tmp/next_data.json ({len(next_data)} chars)")

        # 搜索 position 相关的 key
        def find_keys(obj, path="", target_keys=None):
            if target_keys is None:
                target_keys = ["position", "history", "operation", "record", "symbol", "entryPrice", "leverage"]
            results = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    current_path = f"{path}.{k}" if path else k
                    for tk in target_keys:
                        if tk.lower() in k.lower():
                            results.append((current_path, type(v).__name__, str(v)[:200]))
                    results.extend(find_keys(v, current_path, target_keys))
            elif isinstance(obj, list) and len(obj) > 0:
                results.extend(find_keys(obj[0], f"{path}[0]", target_keys))
            return results

        results = find_keys(data)
        logger.info(f"\n找到 {len(results)} 个 position/operation 相关 key:")
        for path, typ, preview in results:
            logger.info(f"  {path} ({typ}): {preview}")
    else:
        logger.info("未找到 __NEXT_DATA__")

    # 也检查 window.__remixContext 或其他全局变量
    other_data = await page.evaluate("""() => {
        const results = {};
        // 检查常见的 SSR 数据注入点
        const scripts = document.querySelectorAll('script');
        for (const s of scripts) {
            const text = s.textContent;
            if (text && (text.includes('position') || text.includes('Position')) && text.length > 100) {
                // 截取一部分
                const idx = text.toLowerCase().indexOf('position');
                results[`script_${scripts.length}`] = text.substring(Math.max(0, idx - 50), idx + 200);
            }
        }
        return results;
    }""")

    if other_data:
        logger.info(f"\n在其他 script 标签中找到 position 相关内容:")
        for k, v in other_data.items():
            logger.info(f"  {k}: {v[:300]}")

    # 直接在页面上搜索仓位数据
    logger.info("\n直接获取页面显示的仓位数据...")
    visible_text = await page.evaluate("""() => {
        // 获取仓位 tab 的内容
        const tables = document.querySelectorAll('table');
        const result = [];
        for (const t of tables) {
            result.push({
                headers: Array.from(t.querySelectorAll('th')).map(th => th.textContent.trim()),
                rows: Array.from(t.querySelectorAll('tbody tr')).slice(0, 3).map(tr =>
                    Array.from(tr.querySelectorAll('td')).map(td => td.textContent.trim())
                )
            });
        }
        return result;
    }""")

    if visible_text:
        logger.info(f"找到 {len(visible_text)} 个表格:")
        for i, t in enumerate(visible_text):
            logger.info(f"  表格 #{i}: headers={t['headers']}")
            for j, row in enumerate(t['rows']):
                logger.info(f"    row #{j}: {row}")

    await browser.close()
    await pw.stop()


asyncio.run(main())
