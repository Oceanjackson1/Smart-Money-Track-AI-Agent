import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from apscheduler.events import EVENT_JOB_ERROR
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from config import settings
from db.database import init_db
from monitoring.heartbeat import agent_heartbeat
from pusher.webhook import webhook_pusher
from routers import traders, ws
from scraper.api_client import api_client
from scraper.browser import browser_manager
from scraper.tasks import poll_history, poll_positions
from telegram_bot.bot import start_bot, stop_bot

# 日志配置
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def _dispatch_heartbeat_report(coro) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        try:
            asyncio.run(coro)
        except Exception:
            logger.exception("Failed to dispatch heartbeat report without running loop")
    else:
        loop.create_task(coro)


def _scheduler_error_listener(event) -> None:
    if not getattr(event, "exception", None):
        return
    logger.error(
        "Scheduler job failed: %s",
        event.job_id,
        exc_info=(type(event.exception), event.exception, event.exception.__traceback__),
    )
    _dispatch_heartbeat_report(
        agent_heartbeat.report_exception(f"定时任务异常 {event.job_id}", event.exception),
    )


def _install_asyncio_exception_handler(loop: asyncio.AbstractEventLoop):
    previous_handler = loop.get_exception_handler()

    def handler(current_loop: asyncio.AbstractEventLoop, context):
        exc = context.get("exception")
        message = context.get("message", "未处理的 asyncio 异常")
        if exc is not None:
            logger.error(
                "Unhandled asyncio exception: %s",
                message,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
        else:
            logger.error("Unhandled asyncio exception: %s", message)
        current_loop.create_task(agent_heartbeat.report_exception(message, exc))
        if previous_handler is not None:
            previous_handler(current_loop, context)
        else:
            current_loop.default_exception_handler(context)

    loop.set_exception_handler(handler)
    return previous_handler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动和关闭时的初始化与清理。"""
    loop = asyncio.get_running_loop()
    previous_loop_exception_handler = _install_asyncio_exception_handler(loop)
    scheduler.add_listener(_scheduler_error_listener, EVENT_JOB_ERROR)
    startup_completed = False

    try:
        await agent_heartbeat.report_starting()

        # ── Startup ──
        logger.info("Initializing database...")
        await init_db()

        logger.info("Starting browser manager...")
        await browser_manager.start()

        logger.info("Starting API client...")
        await api_client.start()

        logger.info("Starting webhook pusher...")
        await webhook_pusher.start()

        # 配置定时任务
        scheduler.add_job(
            poll_positions,
            "interval",
            minutes=settings.POLL_INTERVAL_MINUTES,
            id="poll_positions",
            name="Poll trader positions",
            max_instances=1,
            replace_existing=True,
        )
        scheduler.add_job(
            poll_history,
            "interval",
            minutes=settings.HISTORY_POLL_INTERVAL_MINUTES,
            id="poll_history",
            name="Poll position history",
            max_instances=1,
            replace_existing=True,
        )
        scheduler.start()
        logger.info(
            f"Scheduler started: positions every {settings.POLL_INTERVAL_MINUTES}min, "
            f"history every {settings.HISTORY_POLL_INTERVAL_MINUTES}min"
        )

        # 立即执行一次首次抓取
        logger.info("Running initial data fetch...")
        try:
            await poll_positions()
        except Exception as e:
            logger.error(f"Initial position poll failed: {e}")
            await agent_heartbeat.report_exception("首次仓位抓取失败", e)

        # 启动 Telegram Bot
        if settings.TG_BOT_TOKEN:
            logger.info("Starting Telegram Bot...")
            try:
                await start_bot()
            except Exception as e:
                logger.error(f"Telegram Bot start failed: {e}")
                await agent_heartbeat.report_exception("Telegram Bot 启动失败", e)
        else:
            logger.info("TG_BOT_TOKEN not set, Telegram Bot disabled")

        startup_completed = True
        await agent_heartbeat.report_ready()
        logger.info("=== Smart Money Track service is ready ===")

        yield
    except Exception as exc:
        await agent_heartbeat.report_exception("服务生命周期异常", exc)
        raise
    finally:
        logger.info("Shutting down...")

        if settings.TG_BOT_TOKEN:
            try:
                await stop_bot()
            except Exception as exc:
                logger.error("Failed to stop Telegram Bot: %s", exc)
                await agent_heartbeat.report_exception("Telegram Bot 停止失败", exc)

        if scheduler.running:
            try:
                scheduler.shutdown(wait=False)
            except Exception as exc:
                logger.error("Failed to stop scheduler: %s", exc)
                await agent_heartbeat.report_exception("调度器停止失败", exc)

        try:
            await api_client.stop()
        except Exception as exc:
            logger.error("Failed to stop API client: %s", exc)
            await agent_heartbeat.report_exception("API Client 停止失败", exc)

        try:
            await webhook_pusher.stop()
        except Exception as exc:
            logger.error("Failed to stop webhook pusher: %s", exc)
            await agent_heartbeat.report_exception("Webhook 推送器停止失败", exc)

        try:
            await browser_manager.stop()
        except Exception as exc:
            logger.error("Failed to stop browser manager: %s", exc)
            await agent_heartbeat.report_exception("浏览器管理器停止失败", exc)

        if startup_completed:
            await agent_heartbeat.report_shutdown()
        await agent_heartbeat.close()
        loop.set_exception_handler(previous_loop_exception_handler)
        logger.info("Service stopped")


app = FastAPI(
    title="Smart Money Track",
    description="Binance Smart Money 交易员监控系统",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(traders.router)
app.include_router(ws.router)


@app.get("/")
async def root():
    return {
        "service": "Smart Money Track",
        "version": "1.0.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    try:
        uvicorn.run(
            "main:app",
            host=settings.SERVER_HOST,
            port=settings.SERVER_PORT,
            reload=False,
        )
    except Exception as exc:
        logger.exception("Uvicorn process crashed")
        asyncio.run(agent_heartbeat.report_exception("Uvicorn 进程异常退出", exc))
        raise
