"""测试 8: Telegram Bot 模块"""
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


# ── i18n 测试 ──

def test_i18n_t_zh():
    """验证中文文案返回。"""
    from telegram_bot.i18n import t
    result = t("welcome", "zh")
    assert "Smart Money AI Agent" in result
    assert "排行榜" in result
    print("  [PASS] 中文文案正确")


def test_i18n_t_en():
    """验证英文文案返回。"""
    from telegram_bot.i18n import t
    result = t("welcome", "en")
    assert "Smart Money AI Agent" in result
    assert "Leaderboard" in result
    print("  [PASS] 英文文案正确")


def test_i18n_t_all_keys_have_both_langs():
    """验证所有文案 key 同时有中英文。"""
    from telegram_bot.i18n import TEXTS
    for key, langs in TEXTS.items():
        assert "zh" in langs, f"Missing zh for key: {key}"
        assert "en" in langs, f"Missing en for key: {key}"
    print(f"  [PASS] 全部 {len(TEXTS)} 个 key 均有中英文")


def test_i18n_t_missing_key():
    """验证不存在的 key 返回 key 本身。"""
    from telegram_bot.i18n import t
    assert t("nonexistent_key", "zh") == "nonexistent_key"
    print("  [PASS] 未知 key 返回 key 本身")


# ── Models 测试 ──

def test_telegram_user_model():
    """验证 TelegramUser 模型字段。"""
    from telegram_bot.models import TelegramUser
    assert hasattr(TelegramUser, "chat_id")
    assert hasattr(TelegramUser, "username")
    assert hasattr(TelegramUser, "language")
    assert hasattr(TelegramUser, "subscribed")
    assert hasattr(TelegramUser, "subscribed_trader_ids")
    assert TelegramUser.__tablename__ == "telegram_users"
    print("  [PASS] TelegramUser 模型字段正确")


def test_conversation_message_model():
    """验证 ConversationMessage 模型字段。"""
    from telegram_bot.models import ConversationMessage
    assert hasattr(ConversationMessage, "chat_id")
    assert hasattr(ConversationMessage, "role")
    assert hasattr(ConversationMessage, "content")
    assert ConversationMessage.__tablename__ == "conversation_messages"
    print("  [PASS] ConversationMessage 模型字段正确")


@pytest.mark.asyncio
async def test_telegram_user_crud():
    """验证 TelegramUser CRUD 操作。"""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from db.database import Base
    from telegram_bot.models import TelegramUser

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Create
    async with Session() as session:
        user = TelegramUser(chat_id=12345, username="testuser", language="zh")
        session.add(user)
        await session.commit()

    # Read
    async with Session() as session:
        result = await session.execute(
            select(TelegramUser).where(TelegramUser.chat_id == 12345)
        )
        user = result.scalar_one()
        assert user.username == "testuser"
        assert user.language == "zh"
        assert user.subscribed is False

    # Update
    async with Session() as session:
        result = await session.execute(
            select(TelegramUser).where(TelegramUser.chat_id == 12345)
        )
        user = result.scalar_one()
        user.language = "en"
        user.subscribed = True
        user.subscribed_trader_ids = json.dumps(["trader1", "trader2"])
        await session.commit()

    async with Session() as session:
        result = await session.execute(
            select(TelegramUser).where(TelegramUser.chat_id == 12345)
        )
        user = result.scalar_one()
        assert user.language == "en"
        assert user.subscribed is True
        ids = json.loads(user.subscribed_trader_ids)
        assert "trader1" in ids

    await engine.dispose()
    print("  [PASS] TelegramUser CRUD 操作正确")


@pytest.mark.asyncio
async def test_conversation_message_crud():
    """验证 ConversationMessage CRUD 操作。"""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from db.database import Base
    from telegram_bot.models import ConversationMessage

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        msg1 = ConversationMessage(chat_id=111, role="user", content="Hello")
        msg2 = ConversationMessage(chat_id=111, role="assistant", content="Hi there!")
        session.add_all([msg1, msg2])
        await session.commit()

    async with Session() as session:
        result = await session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.chat_id == 111)
            .order_by(ConversationMessage.id)
        )
        messages = result.scalars().all()
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"

    await engine.dispose()
    print("  [PASS] ConversationMessage CRUD 操作正确")


# ── Alert Bridge 测试 ──

def test_alert_bridge_format_position_opened():
    """验证警报桥的事件格式化 (position_opened)。"""
    from telegram_bot.alert_bridge import TelegramAlertBridge

    bridge = TelegramAlertBridge()
    event = {
        "event": "position_opened",
        "timestamp": "2026-02-28T15:00:00+00:00",
        "trader": {"traderId": "123", "nickName": "TestTrader", "rank": 3},
        "data": {
            "symbol": "BTCUSDT", "side": "LONG", "leverage": 10,
            "entryPrice": 85000, "amount": 0.5,
        },
    }
    text_zh = bridge._format_event(event, "zh")
    assert "新开仓提醒" in text_zh
    assert "BTCUSDT" in text_zh
    assert "TestTrader" in text_zh

    text_en = bridge._format_event(event, "en")
    assert "New Position Alert" in text_en
    assert "BTCUSDT" in text_en
    print("  [PASS] position_opened 格式化正确 (中/英)")


def test_alert_bridge_format_position_closed():
    """验证警报桥的事件格式化 (position_closed)。"""
    from telegram_bot.alert_bridge import TelegramAlertBridge

    bridge = TelegramAlertBridge()
    event = {
        "event": "position_closed",
        "timestamp": "2026-02-28T18:00:00+00:00",
        "trader": {"traderId": "123", "nickName": "TestTrader", "rank": 1},
        "data": {"symbol": "ETHUSDT", "side": "SHORT", "lastPnl": -500},
    }
    text_zh = bridge._format_event(event, "zh")
    assert "平仓提醒" in text_zh
    assert "ETHUSDT" in text_zh

    text_en = bridge._format_event(event, "en")
    assert "Position Closed" in text_en
    print("  [PASS] position_closed 格式化正确 (中/英)")


def test_alert_bridge_format_new_operation():
    """验证警报桥的事件格式化 (new_operation)。"""
    from telegram_bot.alert_bridge import TelegramAlertBridge

    bridge = TelegramAlertBridge()
    event = {
        "event": "new_operation",
        "timestamp": "2026-02-28T19:00:00+00:00",
        "trader": {"traderId": "456", "nickName": "Trader2", "rank": 5},
        "data": {
            "symbol": "BTCUSDT", "action": "OPEN_LONG",
            "side": "LONG", "price": 90000, "amount": 1.0,
        },
    }
    text = bridge._format_event(event, "zh")
    assert "新操作提醒" in text
    assert "OPEN_LONG" in text
    print("  [PASS] new_operation 格式化正确")


def test_alert_bridge_format_unknown_event():
    """验证未知事件类型返回 None。"""
    from telegram_bot.alert_bridge import TelegramAlertBridge

    bridge = TelegramAlertBridge()
    event = {"event": "unknown_event", "trader": {}, "data": {}}
    assert bridge._format_event(event, "zh") is None
    print("  [PASS] 未知事件类型返回 None")


# ── Config 测试 ──

def test_config_new_settings():
    """验证新增的 TG 和 DeepSeek 配置项。"""
    from config import settings
    assert hasattr(settings, "TG_BOT_TOKEN")
    assert hasattr(settings, "DEEPSEEK_API_KEY")
    assert hasattr(settings, "DEEPSEEK_BASE_URL")
    assert hasattr(settings, "DEEPSEEK_MODEL")
    assert hasattr(settings, "DEEPSEEK_MAX_TOKENS")
    assert hasattr(settings, "CONVERSATION_WINDOW")
    assert settings.DEEPSEEK_MAX_TOKENS == 2048
    assert settings.CONVERSATION_WINDOW == 20
    print("  [PASS] 新增配置项全部存在且默认值正确")


# ── Push Event 集成测试 ──

@pytest.mark.asyncio
async def test_push_event_includes_telegram():
    """验证 _push_event 现在包含 Telegram alert bridge 调用。"""
    from scraper.tasks import _push_event

    with patch("scraper.tasks.webhook_pusher") as mock_wh, \
         patch("scraper.tasks.ws_manager") as mock_ws, \
         patch("scraper.tasks.telegram_alert_bridge") as mock_tg:
        mock_wh.push = AsyncMock()
        mock_ws.broadcast = AsyncMock()
        mock_tg.push = AsyncMock()

        event = {"event": "test", "data": {}}
        await _push_event(event, "trader_123")

        mock_wh.push.assert_called_once_with(event)
        mock_ws.broadcast.assert_called_once_with(event, trader_id="trader_123")
        mock_tg.push.assert_called_once_with(event, "trader_123")

    print("  [PASS] _push_event 包含 Webhook + WebSocket + Telegram 三通道推送")
