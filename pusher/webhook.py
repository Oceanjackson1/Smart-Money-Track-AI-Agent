import logging
from typing import Any, Dict, List, Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


class WebhookPusher:
    """通过 HTTP POST 将事件推送到配置的 Webhook URLs。"""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._urls: List[str] = list(settings.WEBHOOK_URLS)

    async def start(self):
        self._client = httpx.AsyncClient(timeout=10.0)

    async def stop(self):
        if self._client:
            await self._client.aclose()

    def add_url(self, url: str):
        if url not in self._urls:
            self._urls.append(url)
            logger.info(f"Webhook URL added: {url}")

    def remove_url(self, url: str):
        if url in self._urls:
            self._urls.remove(url)
            logger.info(f"Webhook URL removed: {url}")

    def get_urls(self) -> List[str]:
        return list(self._urls)

    async def push(self, payload: Dict[str, Any]):
        """推送事件到所有已注册的 Webhook URLs，每个 URL 最多重试 3 次。"""
        if not self._urls:
            return

        for url in self._urls:
            for attempt in range(1, 4):
                try:
                    resp = await self._client.post(
                        url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    if resp.status_code < 400:
                        logger.debug(f"Webhook pushed to {url}: {resp.status_code}")
                        break
                    logger.warning(f"Webhook {url} returned {resp.status_code} (attempt {attempt})")
                except Exception as e:
                    logger.error(f"Webhook push to {url} failed: {e} (attempt {attempt})")

                if attempt == 3:
                    logger.error(f"Webhook push to {url} exhausted all retries")


webhook_pusher = WebhookPusher()
