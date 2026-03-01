"""处理 /status 命令。"""
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from telegram import Update
from telegram.ext import ContextTypes

from db.database import async_session
from db.models import Trader
from pusher.webhook import webhook_pusher
from pusher.ws_manager import ws_manager
from telegram_bot.handlers.start import get_user_lang
from telegram_bot.i18n import t
from telegram_bot.models import TelegramUser

logger = logging.getLogger(__name__)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/status — 系统运行状态。"""
    lang = await get_user_lang(update.effective_chat.id)

    async with async_session() as session:
        # 监控交易员数量
        result = await session.execute(select(func.count(Trader.id)))
        trader_count = result.scalar() or 0

        # TG 订阅用户数
        result = await session.execute(
            select(func.count(TelegramUser.id)).where(TelegramUser.subscribed == True)
        )
        tg_sub_count = result.scalar() or 0

    ws_count = ws_manager.active_count
    webhook_count = len(webhook_pusher.get_urls())
    server_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    await update.message.reply_text(
        t("status_title", lang).format(
            traders=trader_count,
            ws=ws_count,
            webhooks=webhook_count,
            tg_subs=tg_sub_count,
            time=server_time,
        ),
        parse_mode="HTML",
    )
