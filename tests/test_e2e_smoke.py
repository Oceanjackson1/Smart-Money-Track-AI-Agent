"""
端到端冒烟测试 —— 验证真实 Binance Smart Money API 调用链路

分为 4 个阶段逐级验证：
  Phase 1: Playwright 浏览器启动 + WAF 通过
  Phase 2: 真实 API 调用 (getTraderList) — 通过浏览器内 fetch()
  Phase 3: 交易员仓位 + 操作记录获取
  Phase 4: 数据库写入 + 变化检测

运行方式:
  source venv/bin/activate
  python tests/test_e2e_smoke.py
"""
import asyncio
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("e2e")

results = []


def record(phase, name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append((phase, name, status, detail))
    icon = "\u2713" if passed else "\u2717"
    logger.info(f"  [{icon}] {name}: {detail}" if detail else f"  [{icon}] {name}")


# ══════════════════════════════════════════════════════
# Phase 1: Playwright + WAF
# ══════════════════════════════════════════════════════
async def phase1_browser():
    logger.info("=" * 60)
    logger.info("Phase 1: Playwright 浏览器启动 + WAF 通过")
    logger.info("=" * 60)

    from scraper.browser import BrowserManager

    bm = BrowserManager()

    try:
        await bm.start()
        record("P1", "浏览器启动 + WAF Challenge", True)
    except Exception as e:
        record("P1", "浏览器启动 + WAF Challenge", False, str(e))
        return None

    # Test 1.2: 页面存在
    has_page = bm._page is not None
    record("P1", "浏览器页面创建", has_page)

    # Test 1.3: 会话时间戳记录
    has_ts = bm._token_obtained_at > 0
    record("P1", "会话时间戳", has_ts, f"obtained_at={bm._token_obtained_at:.0f}")

    # Test 1.4: 过期判断
    not_expired = not bm._is_session_expired()
    record("P1", "会话未过期 (刚获取)", not_expired)

    # Test 1.5: fetch 方法可用
    has_fetch = hasattr(bm, 'fetch') and callable(bm.fetch)
    record("P1", "fetch() 方法可用", has_fetch)

    return bm


# ══════════════════════════════════════════════════════
# Phase 2: getTraderList
# ══════════════════════════════════════════════════════
async def phase2_trader_list(bm):
    logger.info("")
    logger.info("=" * 60)
    logger.info("Phase 2: 真实 API 调用 — 获取交易员排行榜 (浏览器内 fetch)")
    logger.info("=" * 60)

    from scraper.api_client import BinanceSmartMoneyClient
    import scraper.api_client as api_mod

    client = BinanceSmartMoneyClient()
    original_bm = api_mod.browser_manager
    api_mod.browser_manager = bm

    try:
        traders = await client.get_trader_list(page_size=5)
        has_data = traders is not None and len(traders) > 0
        record("P2", "getTraderList 调用", has_data,
               f"获取到 {len(traders)} 个交易员" if has_data else "返回空或 None")

        if has_data:
            t = traders[0]
            logger.info(f"    首个交易员原始数据 keys: {list(t.keys())}")

            has_id = "topTraderId" in t
            record("P2", "交易员 ID 字段", has_id,
                   f"topTraderId={t.get('topTraderId')}")

            has_name = "traderName" in t
            record("P2", "traderName 字段", has_name, f"traderName={t.get('traderName')}")

            has_status = "positionStatus" in t
            record("P2", "positionStatus 字段", has_status, f"value={t.get('positionStatus')}")

            shared_trader = None
            for tr in traders:
                if tr.get("positionStatus") == "IN_POSITION":
                    shared_trader = tr
                    break
            if shared_trader:
                record("P2", "找到公开仓位的交易员", True,
                       f"{shared_trader.get('traderName')} (ID: {shared_trader.get('topTraderId')})")
            else:
                record("P2", "找到公开仓位的交易员", False, "前5名均未公开仓位")
    except Exception as e:
        record("P2", "getTraderList 调用", False, str(e))
        traders = None

    api_mod.browser_manager = original_bm
    return traders


# ══════════════════════════════════════════════════════
# Phase 3: 交易员详情 + 仓位 + 操作
# ══════════════════════════════════════════════════════
async def phase3_trader_detail(bm, traders):
    logger.info("")
    logger.info("=" * 60)
    logger.info("Phase 3: 交易员仓位 + 操作记录获取")
    logger.info("=" * 60)

    if not traders:
        record("P3", "跳过 (无交易员数据)", False, "Phase 2 未获取到数据")
        return

    from scraper.api_client import BinanceSmartMoneyClient
    import scraper.api_client as api_mod

    client = BinanceSmartMoneyClient()
    original_bm = api_mod.browser_manager
    api_mod.browser_manager = bm

    # 找一个公开仓位的交易员
    target = None
    for t in traders:
        if t.get("positionStatus") == "IN_POSITION":
            target = t
            break
    if not target:
        target = traders[0]

    trader_id = str(target.get("topTraderId", ""))
    trader_name = target.get("traderName", "Unknown")
    logger.info(f"  目标交易员: {trader_name} (ID: {trader_id})")

    # Test 3.1: getTraderProfile
    try:
        profile = await client.get_trader_profile(trader_id)
        has_profile = profile is not None
        record("P3", "getTraderProfile", has_profile,
               f"keys={list(profile.keys())[:8]}" if has_profile else "None")
    except Exception as e:
        record("P3", "getTraderProfile", False, str(e))

    # Test 3.2: getChartData
    try:
        chart = await client.get_chart_data(trader_id)
        has_chart = chart is not None
        record("P3", "getChartData", has_chart,
               f"keys={list(chart.keys())}" if has_chart else "None")
    except Exception as e:
        record("P3", "getChartData", False, str(e))

    # Test 3.3: getPositionList (需要登录，预期返回空列表)
    try:
        positions = await client.get_position_list(trader_id)
        is_empty = isinstance(positions, list) and len(positions) == 0
        record("P3", "getPositionList (需登录)", is_empty,
               "返回空列表 (预期行为，需要 Binance 登录)")
    except Exception as e:
        record("P3", "getPositionList", False, str(e))

    # Test 3.4: getPositionHistory (需要登录，预期返回空列表)
    try:
        history = await client.get_position_history(trader_id)
        is_empty = isinstance(history, list) and len(history) == 0
        record("P3", "getPositionHistory (需登录)", is_empty,
               "返回空列表 (预期行为，需要 Binance 登录)")
    except Exception as e:
        record("P3", "getPositionHistory", False, str(e))

    # Test 3.5: getLatestOperations (需要登录，预期返回空列表)
    try:
        ops = await client.get_latest_operations(trader_id)
        is_empty = isinstance(ops, list) and len(ops) == 0
        record("P3", "getLatestOperations (需登录)", is_empty,
               "返回空列表 (预期行为，需要 Binance 登录)")
    except Exception as e:
        record("P3", "getLatestOperations", False, str(e))

    api_mod.browser_manager = original_bm


# ══════════════════════════════════════════════════════
# Phase 4: DB 写入
# ══════════════════════════════════════════════════════
async def phase4_db_integration(traders):
    logger.info("")
    logger.info("=" * 60)
    logger.info("Phase 4: 数据库写入 + 读取验证")
    logger.info("=" * 60)

    if not traders:
        record("P4", "跳过 (无交易员数据)", False)
        return

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from db.database import Base
    from db.models import Trader
    from scraper.tasks import _upsert_trader

    db_path = "/tmp/e2e_test_smart_money.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    record("P4", "测试数据库创建", True)

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        count = 0
        for t in traders[:3]:
            tid = str(t.get("topTraderId", ""))
            if tid:
                await _upsert_trader(session, tid, t)
                count += 1
        await session.commit()
    record("P4", "交易员写入", count > 0, f"写入 {count} 个")

    async with Session() as session:
        result = await session.execute(select(Trader))
        db_traders = result.scalars().all()
        record("P4", "交易员读取", len(db_traders) == count,
               f"DB 中有 {len(db_traders)} 个")
        if db_traders:
            t = db_traders[0]
            record("P4", "数据完整性", bool(t.trader_id and t.nick_name),
                   f"id={t.trader_id}, name={t.nick_name}")

    await engine.dispose()
    if os.path.exists(db_path):
        os.remove(db_path)


# ══════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════
async def main():
    start = time.time()
    logger.info("Binance Smart Money E2E 冒烟测试开始")
    logger.info("")

    bm = await phase1_browser()
    if bm is None:
        print_summary()
        return

    traders = await phase2_trader_list(bm)
    await phase3_trader_detail(bm, traders)
    await phase4_db_integration(traders)

    await bm.stop()
    print_summary(time.time() - start)


def print_summary(elapsed=0):
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)

    passed = sum(1 for _, _, s, _ in results if s == "PASS")
    failed = sum(1 for _, _, s, _ in results if s == "FAIL")

    current_phase = ""
    for phase, name, status, detail in results:
        if phase != current_phase:
            current_phase = phase
            logger.info(f"\n  -- {phase} --")
        icon = "\u2713" if status == "PASS" else "\u2717"
        line = f"    [{icon}] {name}"
        if detail:
            line += f" -- {detail}"
        logger.info(line)

    logger.info("")
    logger.info(f"  总计: {passed + failed} 项 | 通过: {passed} | 失败: {failed}")
    if elapsed:
        logger.info(f"  耗时: {elapsed:.1f}s")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
