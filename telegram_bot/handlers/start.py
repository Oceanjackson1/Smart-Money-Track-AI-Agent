"""处理 /start, /help, /language 命令和语言切换回调。"""
import logging

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from db.database import async_session
from telegram_bot.i18n import t
from telegram_bot.models import TelegramUser

logger = logging.getLogger(__name__)


async def _get_or_create_user(chat_id: int, username: str = None) -> TelegramUser:
    """获取或创建 TG 用户记录。"""
    async with async_session() as session:
        result = await session.execute(
            select(TelegramUser).where(TelegramUser.chat_id == chat_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = TelegramUser(chat_id=chat_id, username=username, language="zh")
            session.add(user)
            await session.commit()
            await session.refresh(user)
        elif username and user.username != username:
            user.username = username
            await session.commit()
        return user


async def get_user_lang(chat_id: int) -> str:
    """获取用户语言偏好。"""
    async with async_session() as session:
        result = await session.execute(
            select(TelegramUser.language).where(TelegramUser.chat_id == chat_id)
        )
        lang = result.scalar_one_or_none()
        return lang or "zh"


def _build_welcome_keyboard(lang: str) -> InlineKeyboardMarkup:
    """构建语言切换按钮。"""
    target_lang = "en" if lang == "zh" else "zh"
    btn_text = t("switch_lang_btn", lang)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_text, callback_data=f"switch_lang:{target_lang}")]
    ])


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start 和 /help 命令。"""
    user = await _get_or_create_user(
        update.effective_chat.id,
        update.effective_user.username if update.effective_user else None,
    )
    lang = user.language
    await update.message.reply_text(
        t("welcome", lang),
        parse_mode="HTML",
        reply_markup=_build_welcome_keyboard(lang),
    )


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/language 命令 — 切换语言。"""
    chat_id = update.effective_chat.id
    async with async_session() as session:
        result = await session.execute(
            select(TelegramUser).where(TelegramUser.chat_id == chat_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = TelegramUser(chat_id=chat_id, language="zh")
            session.add(user)

        new_lang = "en" if user.language == "zh" else "zh"
        user.language = new_lang
        await session.commit()

    await update.message.reply_text(
        t("lang_switched", new_lang),
        parse_mode="HTML",
        reply_markup=_build_welcome_keyboard(new_lang),
    )


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理语言切换 InlineButton 回调。"""
    query = update.callback_query
    await query.answer()

    data = query.data  # "switch_lang:en" 或 "switch_lang:zh"
    new_lang = data.split(":")[1] if ":" in data else "zh"

    chat_id = update.effective_chat.id
    async with async_session() as session:
        result = await session.execute(
            select(TelegramUser).where(TelegramUser.chat_id == chat_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = TelegramUser(chat_id=chat_id, language=new_lang)
            session.add(user)
        else:
            user.language = new_lang
        await session.commit()

    # 重新发送欢迎消息
    await query.edit_message_text(
        t("welcome", new_lang),
        parse_mode="HTML",
        reply_markup=_build_welcome_keyboard(new_lang),
    )
