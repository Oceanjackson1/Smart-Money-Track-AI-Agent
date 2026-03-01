"""测试 6: REST API 端点"""
import os
import sys
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.database import Base, get_session
from db.models import Operation, Position, Trader
from routers import traders


# 使用共享文件数据库以避免内存数据库跨连接问题
TEST_DB_PATH = "/tmp/test_smart_money.db"
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_session():
    async with TestSession() as session:
        yield session


@asynccontextmanager
async def _app_lifespan(app: FastAPI):
    """测试用 lifespan：建表并插入测试数据。"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestSession() as session:
        trader = Trader(
            trader_id="test_001", nick_name="TestTrader",
            pnl=10000.0, roi=0.25, rank=1, position_shared=True
        )
        session.add(trader)
        pos = Position(
            trader_id="test_001", symbol="BTCUSDT",
            entry_price=85000, mark_price=86000,
            amount=0.5, leverage=10, pnl=500
        )
        session.add(pos)
        op = Operation(
            trader_id="test_001", symbol="BTCUSDT",
            action="OPEN_LONG", side="LONG",
            amount=0.5, price=85000, timestamp=1700000000000,
            raw_data="{}"
        )
        session.add(op)
        await session.commit()

    yield

    await test_engine.dispose()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


@pytest.fixture(scope="module")
def test_app():
    """创建测试用 FastAPI app。"""
    app = FastAPI(lifespan=_app_lifespan)
    app.include_router(traders.router)
    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as client:
        yield client


def test_get_traders(test_app):
    """验证 GET /api/traders 返回交易员列表。"""
    resp = test_app.get("/api/traders")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["trader_id"] == "test_001"
    assert data[0]["nick_name"] == "TestTrader"
    print("  [PASS] GET /api/traders 返回正确")


def test_get_positions(test_app):
    """验证 GET /api/traders/{id}/positions 返回仓位。"""
    resp = test_app.get("/api/traders/test_001/positions")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["symbol"] == "BTCUSDT"
    assert data[0]["amount"] == 0.5
    print("  [PASS] GET /api/traders/{id}/positions 返回正确")


def test_get_operations(test_app):
    """验证 GET /api/traders/{id}/operations 返回操作记录。"""
    resp = test_app.get("/api/traders/test_001/operations")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["action"] == "OPEN_LONG"
    print("  [PASS] GET /api/traders/{id}/operations 返回正确")


def test_get_history_empty(test_app):
    """验证 GET /api/traders/{id}/history 无数据时返回空列表。"""
    resp = test_app.get("/api/traders/test_001/history")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 0
    print("  [PASS] GET /api/traders/{id}/history 空数据返回正确")


def test_get_status(test_app):
    """验证 GET /api/status 返回系统状态。"""
    resp = test_app.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "active_ws_connections" in data
    assert "webhook_urls" in data
    assert "monitored_traders" in data
    assert "server_time" in data
    assert data["monitored_traders"] >= 1
    print("  [PASS] GET /api/status 返回正确")


def test_webhook_config_add(test_app):
    """验证 POST /api/config/webhook 添加 Webhook。"""
    resp = test_app.post("/api/config/webhook", json={"url": "https://test.com/hook"})
    assert resp.status_code == 200
    data = resp.json()
    assert "https://test.com/hook" in data["urls"]
    print("  [PASS] POST /api/config/webhook 添加成功")


def test_get_positions_with_limit(test_app):
    """验证带 limit 参数的仓位查询。"""
    resp = test_app.get("/api/traders/test_001/positions?limit=1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) <= 1
    print("  [PASS] GET /api/traders/{id}/positions?limit=1 限制生效")


def test_nonexistent_trader(test_app):
    """验证不存在的交易员返回空列表。"""
    resp = test_app.get("/api/traders/nonexistent/positions")
    assert resp.status_code == 200
    assert resp.json() == []
    print("  [PASS] 不存在交易员返回空列表")
