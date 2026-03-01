"""测试 5: 爬取任务逻辑"""
import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


def test_build_event():
    """验证事件消息构造格式。"""
    from scraper.tasks import _build_event
    from db.models import Trader

    trader = Trader(trader_id="12345", nick_name="TestTrader", rank=1)
    data = {"symbol": "BTCUSDT", "side": "LONG"}

    event = _build_event("position_opened", trader, data)

    assert event["event"] == "position_opened"
    assert "timestamp" in event
    assert event["trader"]["traderId"] == "12345"
    assert event["trader"]["nickName"] == "TestTrader"
    assert event["trader"]["rank"] == 1
    assert event["data"]["symbol"] == "BTCUSDT"
    print("  [PASS] 事件消息格式正确")


def test_build_event_all_types():
    """验证所有事件类型。"""
    from scraper.tasks import _build_event
    from db.models import Trader

    trader = Trader(trader_id="1", nick_name="T", rank=0)
    event_types = ["position_opened", "position_closed", "position_updated", "new_operation"]

    for et in event_types:
        event = _build_event(et, trader, {})
        assert event["event"] == et
    print("  [PASS] 4 种事件类型均可构造")


@pytest.mark.asyncio
async def test_push_event():
    """验证 _push_event 同时调用 webhook 和 websocket。"""
    from scraper.tasks import _push_event

    with patch("scraper.tasks.webhook_pusher") as mock_wh, \
         patch("scraper.tasks.ws_manager") as mock_ws:
        mock_wh.push = AsyncMock()
        mock_ws.broadcast = AsyncMock()

        event = {"event": "test", "data": {}}
        await _push_event(event, "trader_123")

        mock_wh.push.assert_called_once_with(event)
        mock_ws.broadcast.assert_called_once_with(event, trader_id="trader_123")
    print("  [PASS] _push_event 同时推送到 Webhook 和 WebSocket")


@pytest.mark.asyncio
async def test_upsert_trader_create():
    """验证创建新交易员记录。"""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from db.database import Base
    from db.models import Trader
    from scraper.tasks import _upsert_trader

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        data = {
            "traderName": "NewTrader",
            "subscribers": 100,
            "pnl": 5000.0,
            "roi": 0.5,
            "rank": 3,
            "positionStatus": "IN_POSITION",
        }
        trader = await _upsert_trader(session, "new_id_1", data)
        await session.commit()

        assert trader.trader_id == "new_id_1"
        assert trader.nick_name == "NewTrader"
        assert trader.pnl == 5000.0
        assert trader.position_shared is True
    print("  [PASS] 新交易员创建成功")

    await engine.dispose()


@pytest.mark.asyncio
async def test_upsert_trader_update():
    """验证更新已有交易员记录。"""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from db.database import Base
    from db.models import Trader
    from scraper.tasks import _upsert_trader

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 先创建
    async with Session() as session:
        trader = Trader(trader_id="exist_1", nick_name="OldName", pnl=1000.0, rank=5, position_shared=True)
        session.add(trader)
        await session.commit()

    # 再更新
    async with Session() as session:
        data = {"traderName": "NewName", "pnl": 9000.0, "rank": 2, "positionStatus": "IN_POSITION"}
        trader = await _upsert_trader(session, "exist_1", data)
        await session.commit()

        assert trader.nick_name == "NewName"
        assert trader.pnl == 9000.0
        assert trader.rank == 2
    print("  [PASS] 已有交易员更新成功")

    await engine.dispose()


@pytest.mark.asyncio
async def test_poll_trader_positions_new_position():
    """验证检测到新开仓时触发推送。"""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from db.database import Base
    from db.models import Position, Trader
    from scraper.tasks import _poll_trader_positions

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 创建交易员
    async with Session() as session:
        trader = Trader(trader_id="t1", nick_name="T1", rank=1, position_shared=True)
        session.add(trader)
        await session.commit()

    pushed_events = []

    async def mock_push(event, trader_id):
        pushed_events.append(event)

    # Mock API 返回一个新仓位
    mock_positions = [
        {"symbol": "BTCUSDT", "amount": 0.5, "entryPrice": 85000, "markPrice": 86000,
         "pnl": 500, "roe": 0.01, "leverage": 10, "updateTimeStamp": 1700000000000}
    ]

    with patch("scraper.tasks.api_client") as mock_api, \
         patch("scraper.tasks._push_event", side_effect=mock_push):
        mock_api.get_position_list = AsyncMock(return_value=mock_positions)

        async with Session() as session:
            trader = Trader(trader_id="t1", nick_name="T1", rank=1, position_shared=True)
            await _poll_trader_positions(session, trader)
            await session.commit()

    # 应检测到新开仓事件
    assert len(pushed_events) == 1
    assert pushed_events[0]["event"] == "position_opened"
    assert pushed_events[0]["data"]["symbol"] == "BTCUSDT"
    print("  [PASS] 新开仓检测并推送成功")

    await engine.dispose()


@pytest.mark.asyncio
async def test_poll_trader_positions_closed():
    """验证检测到平仓时触发推送。"""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from db.database import Base
    from db.models import Position, Trader
    from scraper.tasks import _poll_trader_positions

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 先插入一个旧仓位
    async with Session() as session:
        old_pos = Position(
            trader_id="t2", symbol="ETHUSDT", amount=10.0, pnl=200, roe=0.02
        )
        session.add(old_pos)
        await session.commit()

    pushed_events = []

    async def mock_push(event, trader_id):
        pushed_events.append(event)

    # API 返回空列表 (仓位已平)
    with patch("scraper.tasks.api_client") as mock_api, \
         patch("scraper.tasks._push_event", side_effect=mock_push):
        mock_api.get_position_list = AsyncMock(return_value=[])

        async with Session() as session:
            trader = Trader(trader_id="t2", nick_name="T2", rank=2, position_shared=True)
            await _poll_trader_positions(session, trader)
            await session.commit()

    # 应检测到平仓事件
    assert len(pushed_events) == 1
    assert pushed_events[0]["event"] == "position_closed"
    assert pushed_events[0]["data"]["symbol"] == "ETHUSDT"
    print("  [PASS] 平仓检测并推送成功")

    await engine.dispose()


@pytest.mark.asyncio
async def test_poll_trader_operations_new():
    """验证检测到新操作时触发推送。"""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from db.database import Base
    from db.models import Operation, Trader
    from scraper.tasks import _poll_trader_operations

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    pushed_events = []

    async def mock_push(event, trader_id):
        pushed_events.append(event)

    mock_ops = [
        {"symbol": "BTCUSDT", "action": "OPEN_LONG", "side": "LONG",
         "amount": 0.1, "price": 85000, "timestamp": 1700000001000},
    ]

    with patch("scraper.tasks.api_client") as mock_api, \
         patch("scraper.tasks._push_event", side_effect=mock_push):
        mock_api.get_latest_operations = AsyncMock(return_value=mock_ops)

        async with Session() as session:
            trader = Trader(trader_id="t3", nick_name="T3", rank=3, position_shared=True)
            await _poll_trader_operations(session, trader)
            await session.commit()

    assert len(pushed_events) == 1
    assert pushed_events[0]["event"] == "new_operation"
    assert pushed_events[0]["data"]["action"] == "OPEN_LONG"
    print("  [PASS] 新操作检测并推送成功")

    await engine.dispose()


@pytest.mark.asyncio
async def test_poll_trader_operations_skip_old():
    """验证已记录的操作不会重复推送。"""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from db.database import Base
    from db.models import Operation, Trader
    from scraper.tasks import _poll_trader_operations

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 先插入一条已有操作 (timestamp = 1000)
    async with Session() as session:
        old_op = Operation(
            trader_id="t4", symbol="BTCUSDT", action="CLOSE",
            timestamp=1000, raw_data="{}"
        )
        session.add(old_op)
        await session.commit()

    pushed_events = []

    async def mock_push(event, trader_id):
        pushed_events.append(event)

    # API 返回的操作 timestamp <= 已有的
    mock_ops = [
        {"symbol": "BTCUSDT", "action": "CLOSE", "timestamp": 1000},
        {"symbol": "BTCUSDT", "action": "OLD", "timestamp": 500},
    ]

    with patch("scraper.tasks.api_client") as mock_api, \
         patch("scraper.tasks._push_event", side_effect=mock_push):
        mock_api.get_latest_operations = AsyncMock(return_value=mock_ops)

        async with Session() as session:
            trader = Trader(trader_id="t4", nick_name="T4", rank=4, position_shared=True)
            await _poll_trader_operations(session, trader)
            await session.commit()

    # 不应有新推送 (所有操作都已存在)
    assert len(pushed_events) == 0
    print("  [PASS] 已记录的操作不会重复推送")

    await engine.dispose()
