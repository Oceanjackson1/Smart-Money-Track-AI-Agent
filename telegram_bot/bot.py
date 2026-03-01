"""Telegram Bot 入口 — 创建 Application、注册 handlers、管理生命周期。"""
import logging

from telegram import BotCommand
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import settings
from telegram_bot.alert_bridge import telegram_alert_bridge
from telegram_bot.deepseek_client import deepseek_client
from telegram_bot.handlers.alerts import alerts_command, subscribe_command, unsubscribe_command
from telegram_bot.handlers.ask import ask_command, free_text_handler
from telegram_bot.handlers.start import language_callback, language_command, start_command
from telegram_bot.handlers.status import status_command
from telegram_bot.handlers.traders import (
    history_command,
    operations_command,
    positions_command,
    traders_command,
)

logger = logging.getLogger(__name__)

_application: Application = None


async def start_bot():
    """启动 Telegram Bot (polling 模式，非阻塞)。"""
    global _application

    if not settings.TG_BOT_TOKEN:
        logger.warning("TG_BOT_TOKEN not set, Telegram bot disabled")
        return

    _application = Application.builder().token(settings.TG_BOT_TOKEN).build()

    # ── 注册命令处理器 ──
    _application.add_handler(CommandHandler(["start", "help"], start_command))
    _application.add_handler(CommandHandler("language", language_command))
    _application.add_handler(CommandHandler("traders", traders_command))
    _application.add_handler(CommandHandler("positions", positions_command))
    _application.add_handler(CommandHandler("history", history_command))
    _application.add_handler(CommandHandler("operations", operations_command))
    _application.add_handler(CommandHandler("status", status_command))
    _application.add_handler(CommandHandler("subscribe", subscribe_command))
    _application.add_handler(CommandHandler("unsubscribe", unsubscribe_command))
    _application.add_handler(CommandHandler("alerts", alerts_command))
    _application.add_handler(CommandHandler("ask", ask_command))

    # ── 回调处理器 ──
    _application.add_handler(CallbackQueryHandler(language_callback, pattern=r"^switch_lang:"))

    # ── 自由文本 → AI 对话 (放最后，优先级最低) ──
    _application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, free_text_handler))

    # ── 初始化并启动 ──
    await _application.initialize()
    await _application.start()
    await _application.updater.start_polling(drop_pending_updates=True)

    # ── 注册 BotFather 命令菜单 ──
    await _register_commands(_application.bot)

    # ── 启动 DeepSeek 客户端 ──
    await deepseek_client.start()

    # ── 启动警报桥 ──
    await telegram_alert_bridge.start(_application.bot)

    logger.info("Telegram Bot started (polling mode)")


async def stop_bot():
    """停止 Telegram Bot。"""
    global _application

    if _application is None:
        return

    logger.info("Stopping Telegram Bot...")
    await deepseek_client.stop()

    if _application.updater and _application.updater.running:
        await _application.updater.stop()
    await _application.stop()
    await _application.shutdown()

    _application = None
    logger.info("Telegram Bot stopped")


async def _register_commands(bot):
    """注册 BotFather 命令菜单 (中英文两套)。"""
    # 中文命令 (默认)
    zh_commands = [
        BotCommand("start", "开始 / 查看帮助"),
        BotCommand("traders", "查看交易员排行榜"),
        BotCommand("positions", "查看交易员当前仓位"),
        BotCommand("history", "查看交易员历史仓位"),
        BotCommand("operations", "查看交易员最新操作"),
        BotCommand("status", "系统运行状态"),
        BotCommand("subscribe", "订阅实时警报"),
        BotCommand("unsubscribe", "取消订阅警报"),
        BotCommand("alerts", "查看警报设置"),
        BotCommand("ask", "AI 智能问答"),
        BotCommand("language", "切换中英文"),
    ]

    # English commands
    en_commands = [
        BotCommand("start", "Start / Help"),
        BotCommand("traders", "View trader leaderboard"),
        BotCommand("positions", "View trader positions"),
        BotCommand("history", "View position history"),
        BotCommand("operations", "View recent operations"),
        BotCommand("status", "System status"),
        BotCommand("subscribe", "Subscribe to alerts"),
        BotCommand("unsubscribe", "Unsubscribe from alerts"),
        BotCommand("alerts", "View alert settings"),
        BotCommand("ask", "Ask AI a question"),
        BotCommand("language", "Switch language"),
    ]

    try:
        # 默认命令 (中文)
        await bot.set_my_commands(zh_commands)
        # English 命令
        await bot.set_my_commands(en_commands, language_code="en")
        logger.info("Bot commands registered (zh + en)")
    except Exception as e:
        logger.warning(f"Failed to register bot commands: {e}")
