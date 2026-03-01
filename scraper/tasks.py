import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.database import async_session
from db.models import Operation, Position, PositionHistory, Trader
from pusher.webhook import webhook_pusher
from pusher.ws_manager import ws_manager
from scraper.api_client import api_client
from telegram_bot.alert_bridge import telegram_alert_bridge

logger = logging.getLogger(__name__)


def _build_event(event_type: str, trader: Trader, data: dict) -> dict:
    """构造推送事件消息。"""
    return {
        "event": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trader": {
            "traderId": trader.trader_id,
            "nickName": trader.nick_name,
            "rank": trader.rank,
        },
        "data": data,
    }


async def _push_event(event: dict, trader_id: str):
    """同时推送到 Webhook、WebSocket 和 Telegram。"""
    await webhook_pusher.push(event)
    await ws_manager.broadcast(event, trader_id=trader_id)
    await telegram_alert_bridge.push(event, trader_id)


# ── 高频任务：每 5 分钟 ──

async def poll_positions():
    """轮询所有监控交易员的当前仓位和最新操作。"""
    logger.info("=== Position polling started ===")

    async with async_session() as session:
        # 获取排行榜
        traders_data = await api_client.get_trader_list(
            page_size=settings.TOP_TRADERS_COUNT
        )
        if not traders_data:
            logger.warning("Failed to fetch trader list")
            return

        for t in traders_data:
            trader_id = str(t.get("topTraderId", ""))
            if not trader_id:
                continue

            # 更新/创建交易员记录
            trader = await _upsert_trader(session, trader_id, t)

            if not trader.position_shared:
                continue

            # 抓取当前仓位 (需要登录，当前返回空)
            await _poll_trader_positions(session, trader)

            # 抓取最新操作 (需要登录，当前返回空)
            await _poll_trader_operations(session, trader)

        await session.commit()

    logger.info("=== Position polling completed ===")


async def _upsert_trader(session: AsyncSession, trader_id: str, data: dict) -> Trader:
    """创建或更新交易员记录。"""
    result = await session.execute(
        select(Trader).where(Trader.trader_id == trader_id)
    )
    trader = result.scalar_one_or_none()

    if trader is None:
        trader = Trader(trader_id=trader_id)
        session.add(trader)

    # 新 API 字段: traderName, avatarUrl, subscribers, pnl, roi, positionStatus
    trader.nick_name = data.get("traderName", data.get("accountName", trader.nick_name))
    trader.user_photo_url = data.get("avatarUrl", trader.user_photo_url)
    trader.follower_count = data.get("subscribers", trader.follower_count)
    trader.pnl = data.get("pnl", trader.pnl)
    trader.roi = data.get("roi", trader.roi)
    trader.rank = data.get("rank", trader.rank)
    # positionStatus: "IN_POSITION" / "PRIVATE_POSITION" / etc.
    pos_status = data.get("positionStatus", "")
    if pos_status:
        trader.position_shared = pos_status == "IN_POSITION"
    elif "sharingPosition" in data:
        trader.position_shared = data.get("sharingPosition", trader.position_shared)

    await session.flush()
    return trader


async def _poll_trader_positions(session: AsyncSession, trader: Trader):
    """检测交易员仓位变化并推送。"""
    positions = await api_client.get_position_list(trader.trader_id)
    if positions is None:
        return

    # 获取 DB 中该交易员的最新仓位快照
    result = await session.execute(
        select(Position)
        .where(Position.trader_id == trader.trader_id)
        .order_by(Position.snapshot_at.desc())
    )
    old_positions = {p.symbol: p for p in result.scalars().all()}
    new_symbols = set()

    for pos in positions:
        symbol = pos.get("symbol", "")
        if not symbol:
            continue
        new_symbols.add(symbol)

        amount = pos.get("amount", 0)
        side = "LONG" if amount and float(amount) > 0 else "SHORT"
        pos_data = {
            "symbol": symbol,
            "side": side,
            "entryPrice": pos.get("entryPrice"),
            "markPrice": pos.get("markPrice"),
            "leverage": pos.get("leverage"),
            "amount": amount,
            "pnl": pos.get("pnl"),
            "roe": pos.get("roe"),
        }

        if symbol not in old_positions:
            # 新开仓
            event = _build_event("position_opened", trader, pos_data)
            await _push_event(event, trader.trader_id)
            logger.info(f"[{trader.nick_name}] New position: {symbol} {side}")
        else:
            old = old_positions[symbol]
            # 检测仓位变化（amount 变化超过 1%）
            old_amt = old.amount or 0
            new_amt = float(amount) if amount else 0
            if old_amt and abs(new_amt - old_amt) / abs(old_amt) > 0.01:
                event = _build_event("position_updated", trader, pos_data)
                await _push_event(event, trader.trader_id)
                logger.info(f"[{trader.nick_name}] Position updated: {symbol}")

        # 写入新的仓位快照
        new_pos = Position(
            trader_id=trader.trader_id,
            symbol=symbol,
            entry_price=pos.get("entryPrice"),
            mark_price=pos.get("markPrice"),
            pnl=pos.get("pnl"),
            roe=pos.get("roe"),
            amount=float(amount) if amount else None,
            leverage=pos.get("leverage"),
            update_time=pos.get("updateTimeStamp"),
        )
        session.add(new_pos)

    # 检测平仓（旧有但新无）
    for symbol, old_pos in old_positions.items():
        if symbol not in new_symbols:
            event = _build_event("position_closed", trader, {
                "symbol": symbol,
                "side": "LONG" if (old_pos.amount or 0) > 0 else "SHORT",
                "lastPnl": old_pos.pnl,
                "lastRoe": old_pos.roe,
            })
            await _push_event(event, trader.trader_id)
            logger.info(f"[{trader.nick_name}] Position closed: {symbol}")


async def _poll_trader_operations(session: AsyncSession, trader: Trader):
    """检测新操作记录并推送。"""
    operations = await api_client.get_latest_operations(trader.trader_id)
    if not operations:
        return

    # 获取该交易员最新的已记录 timestamp
    result = await session.execute(
        select(Operation.timestamp)
        .where(Operation.trader_id == trader.trader_id)
        .order_by(Operation.timestamp.desc())
        .limit(1)
    )
    last_ts = result.scalar_one_or_none() or 0

    for op in operations:
        ts = op.get("timestamp", op.get("time", 0))
        if ts and ts <= last_ts:
            continue  # 已记录过

        symbol = op.get("symbol", "")
        op_record = Operation(
            trader_id=trader.trader_id,
            symbol=symbol,
            action=op.get("action", op.get("type")),
            side=op.get("side"),
            amount=op.get("amount"),
            price=op.get("price"),
            timestamp=ts,
            raw_data=json.dumps(op, ensure_ascii=False),
        )
        session.add(op_record)

        event = _build_event("new_operation", trader, {
            "symbol": symbol,
            "action": op.get("action", op.get("type")),
            "side": op.get("side"),
            "amount": op.get("amount"),
            "price": op.get("price"),
            "timestamp": ts,
        })
        await _push_event(event, trader.trader_id)
        logger.info(f"[{trader.nick_name}] New operation: {op.get('action')} {symbol}")


# ── 低频任务：每 30 分钟 ──

async def poll_history():
    """轮询仓位历史和交易员资料更新。"""
    logger.info("=== History polling started ===")

    async with async_session() as session:
        result = await session.execute(select(Trader))
        traders = result.scalars().all()

        for trader in traders:
            # 更新交易员资料 (新 API 使用 traderName, subscribers 等字段)
            profile = await api_client.get_trader_profile(trader.trader_id)
            if profile:
                trader.nick_name = profile.get("traderName", trader.nick_name)
                trader.introduction = profile.get("introduction", trader.introduction)
                trader.follower_count = profile.get("subscribers", trader.follower_count)
                trader.position_shared = profile.get("sharingPosition", trader.position_shared)

            # 更新仓位历史
            history = await api_client.get_position_history(trader.trader_id)
            if history:
                # 获取已有最新的 close_time
                res = await session.execute(
                    select(PositionHistory.close_time)
                    .where(PositionHistory.trader_id == trader.trader_id)
                    .order_by(PositionHistory.close_time.desc())
                    .limit(1)
                )
                last_close = res.scalar_one_or_none() or 0

                for h in history:
                    ct = h.get("closeTime", h.get("updateTimeStamp", 0))
                    if ct and ct <= last_close:
                        continue

                    amount = h.get("amount", 0)
                    record = PositionHistory(
                        trader_id=trader.trader_id,
                        symbol=h.get("symbol", ""),
                        entry_price=h.get("entryPrice"),
                        close_price=h.get("closePrice", h.get("markPrice")),
                        pnl=h.get("pnl"),
                        roe=h.get("roe"),
                        amount=float(amount) if amount else None,
                        leverage=h.get("leverage"),
                        side="LONG" if amount and float(amount) > 0 else "SHORT",
                        open_time=h.get("openTime"),
                        close_time=ct,
                    )
                    session.add(record)

        await session.commit()

    logger.info("=== History polling completed ===")
