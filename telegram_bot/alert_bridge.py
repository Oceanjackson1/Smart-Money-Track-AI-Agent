"""Telegram 警报桥 — 将系统推送事件转发到已订阅的 TG 用户。"""
import json
import logging
from typing import Optional

from sqlalchemy import select

from db.database import async_session
from telegram_bot.i18n import t
from telegram_bot.models import TelegramUser

logger = logging.getLogger(__name__)


class TelegramAlertBridge:
    def __init__(self):
        self._bot = None  # telegram.Bot 实例

    async def start(self, bot):
        self._bot = bot
        logger.info("Telegram alert bridge started")

    async def push(self, event: dict, trader_id: str):
        """将系统事件转发到已订阅的 TG 用户。"""
        if not self._bot:
            return

        try:
            # 查询所有订阅用户
            async with async_session() as session:
                result = await session.execute(
                    select(TelegramUser).where(TelegramUser.subscribed == True)
                )
                users = result.scalars().all()

            if not users:
                return

            for user in users:
                # 检查是否订阅了该交易员
                try:
                    sub_ids = json.loads(user.subscribed_trader_ids or "[]")
                except (json.JSONDecodeError, TypeError):
                    sub_ids = []

                # 空列表 = 订阅全部
                if sub_ids and trader_id not in sub_ids:
                    continue

                # 格式化消息
                text = self._format_event(event, user.language)
                if not text:
                    continue

                try:
                    await self._bot.send_message(
                        chat_id=user.chat_id,
                        text=text,
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.warning(f"Failed to send alert to {user.chat_id}: {e}")

        except Exception as e:
            logger.error(f"Alert bridge push error: {e}")

    def _format_event(self, event: dict, lang: str) -> Optional[str]:
        """将事件格式化为 TG 消息文本。"""
        event_type = event.get("event", "")
        trader = event.get("trader", {})
        data = event.get("data", {})
        timestamp = event.get("timestamp", "")

        name = trader.get("nickName", "Unknown")
        rank = trader.get("rank", "?")
        symbol = data.get("symbol", "?")
        time_str = timestamp[:19] if timestamp else "?"

        if event_type == "position_opened":
            return t("alert_position_opened", lang).format(
                name=name, rank=rank, symbol=symbol,
                side=data.get("side", "?"),
                leverage=data.get("leverage", "?"),
                entry_price=self._fmt_price(data.get("entryPrice")),
                amount=data.get("amount", "?"),
                time=time_str,
            )
        elif event_type == "position_closed":
            pnl = data.get("lastPnl")
            pnl_str = f"${pnl:,.2f}" if pnl is not None else "N/A"
            return t("alert_position_closed", lang).format(
                name=name, rank=rank, symbol=symbol,
                side=data.get("side", "?"),
                pnl=pnl_str,
                time=time_str,
            )
        elif event_type == "position_updated":
            pnl = data.get("pnl")
            pnl_str = f"${pnl:,.2f}" if pnl is not None else "N/A"
            return t("alert_position_updated", lang).format(
                name=name, rank=rank, symbol=symbol,
                side=data.get("side", "?"),
                leverage=data.get("leverage", "?"),
                amount=data.get("amount", "?"),
                pnl=pnl_str,
                time=time_str,
            )
        elif event_type == "new_operation":
            return t("alert_new_operation", lang).format(
                name=name, rank=rank, symbol=symbol,
                action=data.get("action", "?"),
                side=data.get("side", "?"),
                price=self._fmt_price(data.get("price")),
                amount=data.get("amount", "?"),
                time=time_str,
            )
        return None

    @staticmethod
    def _fmt_price(price) -> str:
        if price is None:
            return "N/A"
        try:
            return f"{float(price):,.2f}"
        except (ValueError, TypeError):
            return str(price)


telegram_alert_bridge = TelegramAlertBridge()
