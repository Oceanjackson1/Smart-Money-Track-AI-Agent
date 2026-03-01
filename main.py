import logging
from contextlib import asynccontextmanager

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from config import settings
from db.database import init_db
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动和关闭时的初始化与清理。"""
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
    )
    scheduler.add_job(
        poll_history,
        "interval",
        minutes=settings.HISTORY_POLL_INTERVAL_MINUTES,
        id="poll_history",
        name="Poll position history",
        max_instances=1,
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

    # 启动 Telegram Bot
    if settings.TG_BOT_TOKEN:
        logger.info("Starting Telegram Bot...")
        try:
            await start_bot()
        except Exception as e:
            logger.error(f"Telegram Bot start failed: {e}")
    else:
        logger.info("TG_BOT_TOKEN not set, Telegram Bot disabled")

    logger.info("=== Smart Money Track service is ready ===")

    yield

    # ── Shutdown ──
    logger.info("Shutting down...")
    if settings.TG_BOT_TOKEN:
        await stop_bot()
    scheduler.shutdown(wait=False)
    await api_client.stop()
    await webhook_pusher.stop()
    await browser_manager.stop()
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
    uvicorn.run(
        "main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=False,
    )
