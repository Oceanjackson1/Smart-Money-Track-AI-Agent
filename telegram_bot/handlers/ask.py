"""处理 /ask 命令和自由文本 AI 对话。"""
import logging

from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.deepseek_client import deepseek_client
from telegram_bot.handlers.start import get_user_lang
from telegram_bot.i18n import t

logger = logging.getLogger(__name__)


async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/ask <问题> — AI 智能问答。"""
    lang = await get_user_lang(update.effective_chat.id)
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text(t("ask_usage", lang), parse_mode="HTML")
        return

    question = " ".join(context.args)

    # /ask clear → 清空上下文
    if question.strip().lower() == "clear":
        await deepseek_client.clear_history(chat_id)
        await update.message.reply_text(t("ask_cleared", lang))
        return

    # 发送"正在分析"提示
    thinking_msg = await update.message.reply_text(t("ask_thinking", lang))

    try:
        reply = await deepseek_client.chat(chat_id, question, lang)
        await thinking_msg.edit_text(reply, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"AI chat error for {chat_id}: {e}")
        await thinking_msg.edit_text(t("ask_error", lang))


async def free_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理非命令的自由文本 → AI 对话。"""
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if not text or text.startswith("/"):
        return

    lang = await get_user_lang(update.effective_chat.id)
    chat_id = update.effective_chat.id

    thinking_msg = await update.message.reply_text(t("ask_thinking", lang))

    try:
        reply = await deepseek_client.chat(chat_id, text, lang)
        await thinking_msg.edit_text(reply, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"AI free text error for {chat_id}: {e}")
        await thinking_msg.edit_text(t("ask_error", lang))
