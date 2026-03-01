"""测试 3: Webhook 和 WebSocket 推送模块"""
import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


# ── Webhook 测试 ──

def test_webhook_add_remove_urls():
    """验证 Webhook URL 的增删操作。"""
    from pusher.webhook import WebhookPusher

    pusher = WebhookPusher()
    pusher._urls = []  # 清空

    pusher.add_url("https://example.com/hook1")
    assert "https://example.com/hook1" in pusher.get_urls()

    pusher.add_url("https://example.com/hook2")
    assert len(pusher.get_urls()) == 2

    # 重复添加不应生效
    pusher.add_url("https://example.com/hook1")
    assert len(pusher.get_urls()) == 2

    pusher.remove_url("https://example.com/hook1")
    assert "https://example.com/hook1" not in pusher.get_urls()
    assert len(pusher.get_urls()) == 1

    # 删除不存在的 URL 不应报错
    pusher.remove_url("https://nonexistent.com")
    assert len(pusher.get_urls()) == 1

    print("  [PASS] Webhook URL 增删操作正确")


def test_webhook_get_urls_returns_copy():
    """验证 get_urls 返回副本而非原始列表。"""
    from pusher.webhook import WebhookPusher

    pusher = WebhookPusher()
    pusher._urls = ["https://example.com/hook"]
    urls = pusher.get_urls()
    urls.append("https://modified.com")
    assert len(pusher.get_urls()) == 1  # 原始列表不受影响
    print("  [PASS] get_urls 返回的是副本")


@pytest.mark.asyncio
async def test_webhook_push_no_urls():
    """验证没有 URL 时 push 不报错。"""
    from pusher.webhook import WebhookPusher

    pusher = WebhookPusher()
    pusher._urls = []
    await pusher.start()
    # 不应抛出异常
    await pusher.push({"event": "test"})
    await pusher.stop()
    print("  [PASS] 无 URL 时 push 不报错")


# ── WebSocket Manager 测试 ──

def test_ws_manager_initial_state():
    """验证 WebSocket Manager 初始状态。"""
    from pusher.ws_manager import ConnectionManager

    manager = ConnectionManager()
    assert manager.active_count == 0
    assert len(manager._all_connections) == 0
    assert len(manager._subscriptions) == 0
    print("  [PASS] WebSocket Manager 初始状态正确")


@pytest.mark.asyncio
async def test_ws_manager_connect_disconnect():
    """验证 WebSocket 连接和断开。"""
    from pusher.ws_manager import ConnectionManager

    manager = ConnectionManager()

    # 模拟 WebSocket 对象
    mock_ws = AsyncMock()
    mock_ws.client = "test_client"

    await manager.connect(mock_ws, None)
    mock_ws.accept.assert_called_once()
    assert manager.active_count == 1

    await manager.disconnect(mock_ws)
    assert manager.active_count == 0
    print("  [PASS] WebSocket 连接/断开正常")


@pytest.mark.asyncio
async def test_ws_manager_subscribe_by_trader():
    """验证按 traderId 订阅。"""
    from pusher.ws_manager import ConnectionManager

    manager = ConnectionManager()

    mock_ws1 = AsyncMock()
    mock_ws1.client = "client1"
    mock_ws2 = AsyncMock()
    mock_ws2.client = "client2"

    # ws1 订阅全量
    await manager.connect(mock_ws1, None)
    # ws2 订阅特定交易员
    await manager.connect(mock_ws2, ["trader_A", "trader_B"])

    assert manager.active_count == 2
    assert "trader_A" in manager._subscriptions
    assert "trader_B" in manager._subscriptions

    await manager.disconnect(mock_ws2)
    assert "trader_A" not in manager._subscriptions
    assert manager.active_count == 1
    print("  [PASS] 按 traderId 订阅和取消订阅正常")


@pytest.mark.asyncio
async def test_ws_manager_broadcast_all():
    """验证全量广播。"""
    from pusher.ws_manager import ConnectionManager

    manager = ConnectionManager()

    mock_ws = AsyncMock()
    mock_ws.client = "test"
    await manager.connect(mock_ws, None)

    payload = {"event": "test", "data": "hello"}
    await manager.broadcast(payload)

    mock_ws.send_text.assert_called_once()
    sent = json.loads(mock_ws.send_text.call_args[0][0])
    assert sent["event"] == "test"
    print("  [PASS] 全量广播正常")


@pytest.mark.asyncio
async def test_ws_manager_broadcast_targeted():
    """验证定向广播只发给订阅者。"""
    from pusher.ws_manager import ConnectionManager

    manager = ConnectionManager()

    mock_all = AsyncMock()
    mock_all.client = "all_client"
    mock_sub = AsyncMock()
    mock_sub.client = "sub_client"
    mock_other = AsyncMock()
    mock_other.client = "other_client"

    await manager.connect(mock_all, None)  # 全量
    await manager.connect(mock_sub, ["trader_X"])  # 订阅 trader_X
    await manager.connect(mock_other, ["trader_Y"])  # 订阅 trader_Y

    await manager.broadcast({"event": "pos"}, trader_id="trader_X")

    # mock_all (全量) 和 mock_sub (订阅 trader_X) 应收到
    assert mock_all.send_text.call_count == 1
    assert mock_sub.send_text.call_count == 1
    # mock_other (订阅 trader_Y) 不应收到
    assert mock_other.send_text.call_count == 0
    print("  [PASS] 定向广播只发给相关订阅者")


@pytest.mark.asyncio
async def test_ws_manager_cleanup_stale():
    """验证断开连接的 WebSocket 自动清理。"""
    from pusher.ws_manager import ConnectionManager

    manager = ConnectionManager()

    mock_good = AsyncMock()
    mock_good.client = "good"
    mock_stale = AsyncMock()
    mock_stale.client = "stale"
    mock_stale.send_text.side_effect = Exception("Connection closed")

    await manager.connect(mock_good, None)
    await manager.connect(mock_stale, None)
    assert manager.active_count == 2

    await manager.broadcast({"event": "test"})

    # stale 连接应被自动清理
    assert manager.active_count == 1
    print("  [PASS] 断开连接自动清理成功")
