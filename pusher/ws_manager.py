import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """管理 WebSocket 连接，支持全量广播和按 traderId 订阅。"""

    def __init__(self):
        # 全量订阅的连接
        self._all_connections: List[WebSocket] = []
        # 按 traderId 订阅的连接
        self._subscriptions: Dict[str, List[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, trader_ids: Optional[List[str]] = None):
        """接受新的 WebSocket 连接。trader_ids 为空表示订阅全量。"""
        await websocket.accept()
        async with self._lock:
            if not trader_ids:
                self._all_connections.append(websocket)
                logger.info(f"WS client connected (all): {websocket.client}")
            else:
                for tid in trader_ids:
                    if tid not in self._subscriptions:
                        self._subscriptions[tid] = []
                    self._subscriptions[tid].append(websocket)
                logger.info(f"WS client connected (traders={trader_ids}): {websocket.client}")

    async def disconnect(self, websocket: WebSocket):
        """移除断开的 WebSocket 连接。"""
        async with self._lock:
            if websocket in self._all_connections:
                self._all_connections.remove(websocket)
            for tid in list(self._subscriptions.keys()):
                if websocket in self._subscriptions[tid]:
                    self._subscriptions[tid].remove(websocket)
                if not self._subscriptions[tid]:
                    del self._subscriptions[tid]

    async def broadcast(self, payload: Dict[str, Any], trader_id: Optional[str] = None):
        """广播消息。发送给全量订阅者 + 特定 traderId 订阅者。"""
        message = json.dumps(payload, ensure_ascii=False)
        targets: List[WebSocket] = []

        async with self._lock:
            targets.extend(self._all_connections)
            if trader_id and trader_id in self._subscriptions:
                targets.extend(self._subscriptions[trader_id])

        stale: List[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(message)
            except Exception:
                stale.append(ws)

        # 清理已断开的连接
        for ws in stale:
            await self.disconnect(ws)

    @property
    def active_count(self) -> int:
        all_ws: Set[WebSocket] = set(self._all_connections)
        for subs in self._subscriptions.values():
            all_ws.update(subs)
        return len(all_ws)


ws_manager = ConnectionManager()
