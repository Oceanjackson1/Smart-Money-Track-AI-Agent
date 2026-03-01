import asyncio
import logging
import random
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from config import settings
from scraper.browser import browser_manager

logger = logging.getLogger(__name__)

BASE_URL = settings.BINANCE_BASE_URL


class BinanceSmartMoneyClient:
    """封装 Binance Smart Money API 调用，通过浏览器内 fetch() 发起请求。

    真实 API 端点 (通过网络拦截发现):
      - 交易员列表: GET /bapi/futures/v1/friendly/future/smart-money/top-trader/list
      - 交易员 Profile: GET /bapi/asset/v1/friendly/future/smart-money/profile
      - PNL 图表: GET /bapi/asset/v1/friendly/future/smart-money/profile/chart-data

    注意: 仓位/操作记录需要登录才能访问，未登录时页面显示"登录以查看仓位"。
    """

    def __init__(self):
        self._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_REQUESTS)

    async def start(self):
        pass

    async def stop(self):
        pass

    async def _get(self, path: str, params: dict) -> Optional[Dict[str, Any]]:
        """通过浏览器 fetch() 发送 GET 请求，带重试和反检测延迟。"""
        query = urlencode(params)
        url = f"{BASE_URL}{path}?{query}"

        for attempt in range(1, settings.MAX_RETRIES + 1):
            try:
                delay = random.uniform(settings.REQUEST_DELAY_MIN, settings.REQUEST_DELAY_MAX)
                await asyncio.sleep(delay)

                async with self._semaphore:
                    result = await browser_manager.get(url)

                status = result.get("status", 0)
                data = result.get("data")
                error = result.get("error")

                if error:
                    logger.error(f"Browser fetch error on {path}: {error} (attempt {attempt})")
                    await browser_manager.force_refresh()
                    continue

                if status == 403:
                    logger.warning(f"WAF blocked (403) on {path}, refreshing (attempt {attempt})")
                    await browser_manager.force_refresh()
                    continue

                if status == 202:
                    logger.warning(f"WAF challenge (202) on {path}, refreshing (attempt {attempt})")
                    await browser_manager.force_refresh()
                    continue

                if status >= 400:
                    logger.error(f"HTTP {status} on {path} (attempt {attempt})")
                    continue

                if data and data.get("code") == "000000":
                    return data.get("data")
                else:
                    code = data.get("code") if data else "?"
                    msg = data.get("message") if data else "no data"
                    logger.error(f"API error on {path}: code={code}, msg={msg}")
                    return None

            except Exception as e:
                logger.error(f"Unexpected error on {path}: {e} (attempt {attempt})")

            if attempt < settings.MAX_RETRIES:
                backoff = 2 ** attempt + random.uniform(0, 1)
                logger.info(f"Retrying {path} in {backoff:.1f}s...")
                await asyncio.sleep(backoff)

        logger.error(f"All {settings.MAX_RETRIES} retries exhausted for {path}")
        return None

    # ── 交易员排行榜 (公开) ──

    async def get_trader_list(
        self,
        ranking_type: str = "PNL",
        time_range: str = "30D",
        page: int = 1,
        page_size: int = 20,
        only_sharing: bool = False,
    ) -> Optional[List[dict]]:
        """获取交易员排行榜。

        返回数据格式:
            {"total": 100, "rows": [{"topTraderId": "...", "traderName": "...", ...}]}
        """
        data = await self._get(settings.TRADER_LIST_API, {
            "page": page,
            "rows": page_size,
            "timeRange": time_range,
            "rankingType": ranking_type,
            "onlyShowSharingPosition": str(only_sharing).lower(),
            "order": "DESC",
        })
        if data is None:
            return None
        if isinstance(data, dict):
            return data.get("rows", [])
        return data

    # ── 交易员资料 (公开) ──

    async def get_trader_profile(self, trader_id: str) -> Optional[dict]:
        """获取交易员 Profile 详情。

        返回字段: topTraderId, traderName, avatarUrl, introduction,
                  sharingPosition, sharingPositionHistory, sharingLatestRecord,
                  roi, pnl, subscribers, daysActive, winRate, mdd 等
        """
        return await self._get(settings.PROFILE_API, {
            "topTraderId": trader_id,
        })

    # ── PNL 图表 (公开) ──

    async def get_chart_data(
        self,
        trader_id: str,
        time_range: str = "30D",
        chart_type: str = "PNL",
    ) -> Optional[dict]:
        """获取交易员 PNL/ROI/资产 图表数据。"""
        return await self._get(settings.CHART_DATA_API, {
            "topTraderId": trader_id,
            "timeRange": time_range,
            "chartDataType": chart_type,
        })

    # ── 仓位 (需要登录) ──
    # 注意: 以下方法暂时返回空列表，因为仓位数据需要 Binance 账户登录才能访问。
    # 页面显示 "登录或注册以查看该用户的仓位"。
    # 未来可通过注入登录 cookie 实现。

    async def get_position_list(self, trader_id: str) -> Optional[List[dict]]:
        """获取交易员当前持仓 (需要登录)。"""
        logger.debug(f"Position list for {trader_id}: requires login, returning empty")
        return []

    async def get_position_history(
        self, trader_id: str, page_index: int = 1, page_size: int = 20,
    ) -> Optional[List[dict]]:
        """获取仓位历史 (需要登录)。"""
        logger.debug(f"Position history for {trader_id}: requires login, returning empty")
        return []

    async def get_latest_operations(
        self, trader_id: str, page_index: int = 1, page_size: int = 20,
    ) -> Optional[List[dict]]:
        """获取最新操作记录 (需要登录)。"""
        logger.debug(f"Latest operations for {trader_id}: requires login, returning empty")
        return []


# 全局单例
api_client = BinanceSmartMoneyClient()
