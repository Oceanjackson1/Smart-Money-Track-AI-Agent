"""测试 2: 数据库模型和初始化"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def test_models_import():
    """验证所有模型类可正常导入。"""
    from db.models import Operation, Position, PositionHistory, Trader

    assert Trader.__tablename__ == "traders"
    assert Position.__tablename__ == "positions"
    assert PositionHistory.__tablename__ == "position_history"
    assert Operation.__tablename__ == "operations"
    print("  [PASS] 所有模型类导入成功")


def test_trader_model_columns():
    """验证 Trader 模型字段完整性。"""
    from db.models import Trader

    columns = {c.name for c in Trader.__table__.columns}
    expected = {
        "id", "trader_id", "nick_name", "user_photo_url",
        "follower_count", "pnl", "roi", "rank",
        "position_shared", "twitter_url", "introduction", "updated_at"
    }
    assert expected.issubset(columns), f"Missing columns: {expected - columns}"
    print(f"  [PASS] Trader 模型包含 {len(columns)} 个字段")


def test_position_model_columns():
    """验证 Position 模型字段完整性。"""
    from db.models import Position

    columns = {c.name for c in Position.__table__.columns}
    expected = {
        "id", "trader_id", "symbol", "entry_price", "mark_price",
        "pnl", "roe", "amount", "leverage", "update_time", "snapshot_at"
    }
    assert expected.issubset(columns), f"Missing columns: {expected - columns}"
    print(f"  [PASS] Position 模型包含 {len(columns)} 个字段")


def test_position_history_model_columns():
    """验证 PositionHistory 模型字段完整性。"""
    from db.models import PositionHistory

    columns = {c.name for c in PositionHistory.__table__.columns}
    expected = {
        "id", "trader_id", "symbol", "entry_price", "close_price",
        "pnl", "roe", "amount", "leverage", "side",
        "open_time", "close_time", "fetched_at"
    }
    assert expected.issubset(columns), f"Missing columns: {expected - columns}"
    print(f"  [PASS] PositionHistory 模型包含 {len(columns)} 个字段")


def test_operation_model_columns():
    """验证 Operation 模型字段完整性。"""
    from db.models import Operation

    columns = {c.name for c in Operation.__table__.columns}
    expected = {
        "id", "trader_id", "symbol", "action", "side",
        "amount", "price", "timestamp", "raw_data", "fetched_at"
    }
    assert expected.issubset(columns), f"Missing columns: {expected - columns}"
    print(f"  [PASS] Operation 模型包含 {len(columns)} 个字段")


def test_trader_id_unique_index():
    """验证 trader_id 字段有唯一索引。"""
    from db.models import Trader

    col = Trader.__table__.c.trader_id
    assert col.unique is True, "trader_id should be unique"
    assert col.index is True, "trader_id should be indexed"
    print("  [PASS] trader_id 字段已设置唯一索引")


@pytest.mark.asyncio
async def test_init_db():
    """验证数据库初始化（建表）功能正常。"""
    # 使用内存数据库测试
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from db.database import Base

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 验证表已创建
    async with test_engine.begin() as conn:
        tables = await conn.run_sync(
            lambda sync_conn: sync_conn.dialect.get_table_names(sync_conn)
        )
    assert "traders" in tables
    assert "positions" in tables
    assert "position_history" in tables
    assert "operations" in tables
    print(f"  [PASS] 数据库建表成功: {tables}")

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_crud_operations():
    """验证基本 CRUD 操作。"""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from db.database import Base
    from db.models import Trader

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    # Create
    async with TestSession() as session:
        trader = Trader(
            trader_id="test_123",
            nick_name="TestTrader",
            pnl=50000.0,
            roi=0.456,
            rank=1,
            position_shared=True,
        )
        session.add(trader)
        await session.commit()

    # Read
    async with TestSession() as session:
        result = await session.execute(
            select(Trader).where(Trader.trader_id == "test_123")
        )
        trader = result.scalar_one_or_none()
        assert trader is not None
        assert trader.nick_name == "TestTrader"
        assert trader.pnl == 50000.0
        assert trader.position_shared is True
        print("  [PASS] CRUD 操作: 创建和读取成功")

    # Update
    async with TestSession() as session:
        result = await session.execute(
            select(Trader).where(Trader.trader_id == "test_123")
        )
        trader = result.scalar_one()
        trader.pnl = 60000.0
        await session.commit()

    async with TestSession() as session:
        result = await session.execute(
            select(Trader).where(Trader.trader_id == "test_123")
        )
        trader = result.scalar_one()
        assert trader.pnl == 60000.0
        print("  [PASS] CRUD 操作: 更新成功")

    await test_engine.dispose()
