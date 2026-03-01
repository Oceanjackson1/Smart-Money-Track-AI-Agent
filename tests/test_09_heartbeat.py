"""测试 9: Pixel Office 心跳上报"""
import os
import sys
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.mark.asyncio
async def test_report_updates_existing_row():
    """验证已存在记录时使用 PATCH 更新。"""
    from monitoring.heartbeat import AgentHeartbeatReporter

    reporter = AgentHeartbeatReporter(
        enabled=True,
        endpoint="https://example.com/rest/v1/agents",
        api_key="sb_publishable_test",
        agent_id="agent-1",
        name="Smart Money AI Agent",
        role="product",
        role_label_zh="聪明钱数据分析师",
    )

    patch_response = Mock()
    patch_response.json.return_value = [{"id": "agent-1"}]
    patch_response.raise_for_status.return_value = None

    client = AsyncMock()
    client.patch.return_value = patch_response
    reporter._client = client

    result = await reporter.report_ready()

    assert result is True
    client.patch.assert_awaited_once()
    client.post.assert_not_called()
    print("  [PASS] Existing heartbeat row updated via PATCH")


@pytest.mark.asyncio
async def test_report_inserts_when_row_missing():
    """验证找不到记录时回退到 POST 创建。"""
    from monitoring.heartbeat import AgentHeartbeatReporter

    reporter = AgentHeartbeatReporter(
        enabled=True,
        endpoint="https://example.com/rest/v1/agents",
        api_key="sb_publishable_test",
        agent_id="agent-2",
        name="Smart Money AI Agent",
        role="product",
        role_label_zh="聪明钱数据分析师",
    )

    patch_response = Mock()
    patch_response.json.return_value = []
    patch_response.raise_for_status.return_value = None

    post_response = Mock()
    post_response.raise_for_status.return_value = None

    client = AsyncMock()
    client.patch.return_value = patch_response
    client.post.return_value = post_response
    reporter._client = client

    result = await reporter.report_starting()

    assert result is True
    client.patch.assert_awaited_once()
    client.post.assert_awaited_once()
    print("  [PASS] Missing heartbeat row inserted via POST")


@pytest.mark.asyncio
async def test_report_exception_uses_thinking_status():
    """验证异常上报使用 thinking 状态并包含上下文。"""
    from monitoring.heartbeat import AgentHeartbeatReporter

    reporter = AgentHeartbeatReporter(
        enabled=True,
        endpoint="https://example.com/rest/v1/agents",
        api_key="sb_publishable_test",
        agent_id="agent-3",
        name="Smart Money AI Agent",
        role="product",
        role_label_zh="聪明钱数据分析师",
    )

    recorded = {}

    async def fake_report(status, current_task=""):
        recorded["status"] = status
        recorded["current_task"] = current_task
        return True

    reporter.report = fake_report

    result = await reporter.report_exception("调度器异常", RuntimeError("boom"))

    assert result is True
    assert recorded["status"] == "thinking"
    assert "调度器异常" in recorded["current_task"]
    assert "boom" in recorded["current_task"]
    print("  [PASS] Exception heartbeat uses thinking status")


@pytest.mark.asyncio
async def test_report_disabled_returns_false():
    """验证关闭开关后不会尝试上报。"""
    from monitoring.heartbeat import AgentHeartbeatReporter

    reporter = AgentHeartbeatReporter(
        enabled=False,
        endpoint="https://example.com/rest/v1/agents",
        api_key="sb_publishable_test",
        agent_id="agent-4",
        name="Smart Money AI Agent",
        role="product",
        role_label_zh="聪明钱数据分析师",
    )

    result = await reporter.report_shutdown()

    assert result is False
    print("  [PASS] Disabled heartbeat reporter skips network call")
