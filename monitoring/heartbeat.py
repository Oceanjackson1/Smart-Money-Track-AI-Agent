import logging
from typing import Literal, Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

HeartbeatStatus = Literal["working", "idle", "thinking", "sleeping"]


class AgentHeartbeatReporter:
    """向 Pixel Office 对应的 Supabase 表上报服务状态。"""

    def __init__(
        self,
        *,
        enabled: bool,
        endpoint: str,
        api_key: str,
        agent_id: str,
        name: str,
        role: str,
        role_label_zh: str,
        timeout: float = 5.0,
    ):
        self.enabled = enabled
        self.endpoint = endpoint
        self.api_key = api_key
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.role_label_zh = role_label_zh
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    def _headers(self, prefer: str) -> dict:
        # Supabase publishable key 只需要 apikey，不使用 Bearer JWT。
        return {
            "apikey": self.api_key,
            "Content-Type": "application/json",
            "Prefer": prefer,
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    def _normalize_task(self, current_task: str) -> str:
        return " ".join((current_task or "").split())[:240]

    def _build_payload(self, status: HeartbeatStatus, current_task: str) -> dict:
        return {
            "id": self.agent_id,
            "status": status,
            "current_task": self._normalize_task(current_task),
            "name": self.name,
            "role": self.role,
            "role_label_zh": self.role_label_zh,
        }

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def report(self, status: HeartbeatStatus, current_task: str = "") -> bool:
        if not (self.enabled and self.endpoint and self.api_key and self.agent_id):
            return False

        payload = self._build_payload(status, current_task)
        client = await self._get_client()

        try:
            # 优先 patch，避免在表未正确设置唯一约束时重复插入多行。
            response = await client.patch(
                self.endpoint,
                params={"id": f"eq.{self.agent_id}"},
                headers=self._headers("return=representation"),
                json=payload,
            )
            response.raise_for_status()
            if response.json():
                return True

            response = await client.post(
                self.endpoint,
                headers=self._headers("resolution=merge-duplicates,return=representation"),
                json=payload,
            )
            response.raise_for_status()
            return True
        except Exception as exc:
            logger.warning("Heartbeat report failed: %s", exc)
            return False

    async def report_starting(self) -> bool:
        return await self.report("working", "启动 Smart Money Track 服务")

    async def report_ready(self) -> bool:
        return await self.report("working", "监控 Binance Smart Money 排行榜与交易员事件")

    async def report_shutdown(self) -> bool:
        return await self.report("idle", "")

    async def report_exception(self, context: str, exc: Optional[BaseException] = None) -> bool:
        if exc is None:
            detail = context
        else:
            detail = f"{context}: {exc.__class__.__name__}: {exc}"
        return await self.report("thinking", detail)


agent_heartbeat = AgentHeartbeatReporter(
    enabled=settings.AGENT_HEARTBEAT_ENABLED,
    endpoint=settings.AGENT_HEARTBEAT_URL,
    api_key=settings.AGENT_HEARTBEAT_API_KEY,
    agent_id=settings.AGENT_HEARTBEAT_ID,
    name=settings.AGENT_HEARTBEAT_NAME,
    role=settings.AGENT_HEARTBEAT_ROLE,
    role_label_zh=settings.AGENT_HEARTBEAT_ROLE_LABEL_ZH,
    timeout=settings.AGENT_HEARTBEAT_TIMEOUT_SECONDS,
)
