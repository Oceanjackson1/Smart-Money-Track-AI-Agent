"""测试 4: API Client 逻辑验证"""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


def test_api_client_import():
    """验证 API Client 可正常导入。"""
    from scraper.api_client import BinanceSmartMoneyClient, BASE_URL

    client = BinanceSmartMoneyClient()
    assert "binance.com" in BASE_URL
    print(f"  [PASS] API Client 导入成功, BASE_URL: {BASE_URL}")


def test_api_endpoints_config():
    """验证 API 端点配置路径。"""
    from config import settings

    assert "top-trader/list" in settings.TRADER_LIST_API
    assert "profile" in settings.PROFILE_API
    assert "chart-data" in settings.CHART_DATA_API
    print("  [PASS] API 端点配置路径正确")


@pytest.mark.asyncio
async def test_api_client_start_stop():
    """验证 API Client 生命周期（start/stop 为 no-op，不应报错）。"""
    from scraper.api_client import BinanceSmartMoneyClient

    client = BinanceSmartMoneyClient()
    await client.start()
    await client.stop()
    print("  [PASS] API Client start/stop 生命周期正常")


@pytest.mark.asyncio
async def test_get_trader_list_parses_rows():
    """验证 get_trader_list 能正确解析 rows 格式的响应。"""
    from scraper.api_client import BinanceSmartMoneyClient

    client = BinanceSmartMoneyClient()
    mock_data = {
        "total": 2,
        "rows": [
            {"topTraderId": "123", "traderName": "Trader1", "positionStatus": "IN_POSITION"},
            {"topTraderId": "456", "traderName": "Trader2", "positionStatus": "PRIVATE_POSITION"},
        ],
    }

    with patch.object(client, "_get", new_callable=AsyncMock, return_value=mock_data):
        result = await client.get_trader_list()
        assert result is not None
        assert len(result) == 2
        assert result[0]["topTraderId"] == "123"
    print("  [PASS] get_trader_list 解析 rows 响应正确")


@pytest.mark.asyncio
async def test_get_trader_list_handles_none():
    """验证 get_trader_list 处理 None 响应。"""
    from scraper.api_client import BinanceSmartMoneyClient

    client = BinanceSmartMoneyClient()
    with patch.object(client, "_get", new_callable=AsyncMock, return_value=None):
        result = await client.get_trader_list()
        assert result is None
    print("  [PASS] get_trader_list 正确处理 None 响应")


@pytest.mark.asyncio
async def test_get_trader_profile():
    """验证 get_trader_profile 调用正确。"""
    from scraper.api_client import BinanceSmartMoneyClient

    client = BinanceSmartMoneyClient()
    mock_data = {
        "topTraderId": "123",
        "traderName": "TestTrader",
        "sharingPosition": True,
        "pnl": 50000.0,
    }

    with patch.object(client, "_get", new_callable=AsyncMock, return_value=mock_data) as mock:
        result = await client.get_trader_profile("123")
        assert result is not None
        assert result["traderName"] == "TestTrader"
        assert result["sharingPosition"] is True
    print("  [PASS] get_trader_profile 调用和解析正确")


@pytest.mark.asyncio
async def test_get_chart_data():
    """验证 get_chart_data 调用正确。"""
    from scraper.api_client import BinanceSmartMoneyClient

    client = BinanceSmartMoneyClient()
    mock_data = {
        "dataType": "PNL",
        "items": [[1700000000000, 100.0], [1700086400000, 200.0]],
    }

    with patch.object(client, "_get", new_callable=AsyncMock, return_value=mock_data):
        result = await client.get_chart_data("123")
        assert result is not None
        assert result["dataType"] == "PNL"
        assert len(result["items"]) == 2
    print("  [PASS] get_chart_data 调用和解析正确")


@pytest.mark.asyncio
async def test_position_methods_return_empty():
    """验证仓位/操作方法（需要登录）返回空列表。"""
    from scraper.api_client import BinanceSmartMoneyClient

    client = BinanceSmartMoneyClient()
    positions = await client.get_position_list("any_id")
    assert positions == []

    history = await client.get_position_history("any_id")
    assert history == []

    ops = await client.get_latest_operations("any_id")
    assert ops == []
    print("  [PASS] 仓位/操作方法（需登录）正确返回空列表")
