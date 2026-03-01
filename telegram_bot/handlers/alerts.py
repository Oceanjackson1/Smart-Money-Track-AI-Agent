"""处理 /subscribe, /unsubscribe, /alerts 命令。"""
import json
import logging

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from db.database import async_session
from telegram_bot.handlers.start import get_user_lang
from telegram_bot.i18n import t
from telegram_bot.models import TelegramUser

logger = logging.getLogger(__name__)


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/subscribe [trader_ids...] — 订阅警报。"""
    lang = await get_user_lang(update.effective_chat.id)
    chat_id = update.effective_chat.id

    # 解析要订阅的交易员 ID
    trader_ids = list(context.args) if context.args else []

    async with async_session() as session:
        result = await session.execute(
            select(TelegramUser).where(TelegramUser.chat_id == chat_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = TelegramUser(
                chat_id=chat_id,
                username=update.effective_user.username if update.effective_user else None,
            )
            session.add(user)

        user.subscribed = True
        user.subscribed_trader_ids = json.dumps(trader_ids)
        await session.commit()

    if trader_ids:
        await update.message.reply_text(
            t("subscribed_specific", lang).format(traders="\n".join(f"• {tid}" for tid in trader_ids)),
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(t("subscribed_all", lang), parse_mode="HTML")


async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/unsubscribe — 取消订阅。"""
    lang = await get_user_lang(update.effective_chat.id)
    chat_id = update.effective_chat.id

    async with async_session() as session:
        result = await session.execute(
            select(TelegramUser).where(TelegramUser.chat_id == chat_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.subscribed = False
            await session.commit()

    await update.message.reply_text(t("unsubscribed", lang), parse_mode="HTML")


async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/alerts — 查看警报设置。"""
    lang = await get_user_lang(update.effective_chat.id)
    chat_id = update.effective_chat.id

    async with async_session() as session:
        result = await session.execute(
            select(TelegramUser).where(TelegramUser.chat_id == chat_id)
        )
        user = result.scalar_one_or_none()

    if not user or not user.subscribed:
        await update.message.reply_text(t("alerts_status_off", lang), parse_mode="HTML")
        return

    try:
        sub_ids = json.loads(user.subscribed_trader_ids or "[]")
    except (json.JSONDecodeError, TypeError):
        sub_ids = []

    if sub_ids:
        scope = "\n".join(f"• {tid}" for tid in sub_ids)
    else:
        scope = t("scope_all", lang)

    await update.message.reply_text(
        t("alerts_status_on", lang).format(scope=scope), parse_mode="HTML"
    )
