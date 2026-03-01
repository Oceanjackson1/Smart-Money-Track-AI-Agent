import os
from typing import List

from dotenv import load_dotenv

load_dotenv()


class Settings:
    POLL_INTERVAL_MINUTES: int = int(os.getenv("POLL_INTERVAL_MINUTES", "5"))
    HISTORY_POLL_INTERVAL_MINUTES: int = int(os.getenv("HISTORY_POLL_INTERVAL_MINUTES", "30"))
    TOP_TRADERS_COUNT: int = int(os.getenv("TOP_TRADERS_COUNT", "20"))
    WEBHOOK_URLS: List[str] = [
        url.strip()
        for url in os.getenv("WEBHOOK_URLS", "").split(",")
        if url.strip()
    ]
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./smart_money.db")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Binance API
    BINANCE_BASE_URL: str = "https://www.binance.com"
    SMART_MONEY_PAGE: str = "/zh-CN/smart-money"
    # 真实 API 路径 (通过网络拦截发现)
    TRADER_LIST_API: str = "/bapi/futures/v1/friendly/future/smart-money/top-trader/list"
    PROFILE_API: str = "/bapi/asset/v1/friendly/future/smart-money/profile"
    CHART_DATA_API: str = "/bapi/asset/v1/friendly/future/smart-money/profile/chart-data"

    # Telegram Bot
    TG_BOT_TOKEN: str = os.getenv("TG_BOT_TOKEN", "")

    # DeepSeek AI
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    DEEPSEEK_MAX_TOKENS: int = int(os.getenv("DEEPSEEK_MAX_TOKENS", "2048"))
    CONVERSATION_WINDOW: int = int(os.getenv("CONVERSATION_WINDOW", "20"))

    # 反检测
    REQUEST_DELAY_MIN: float = 1.0
    REQUEST_DELAY_MAX: float = 3.0
    MAX_CONCURRENT_REQUESTS: int = 3
    MAX_RETRIES: int = 3
    WAF_TOKEN_REFRESH_MINUTES: int = 10


settings = Settings()
