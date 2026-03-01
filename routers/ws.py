import json
import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from pusher.ws_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    traders: Optional[str] = Query(None, description="逗号分隔的 traderId 列表，为空则订阅全量"),
):
    """
    WebSocket 端点。

    连接方式：
    - ws://host:port/ws          → 订阅全量推送
    - ws://host:port/ws?traders=id1,id2  → 仅订阅指定交易员
    """
    trader_ids = None
    if traders:
        trader_ids = [t.strip() for t in traders.split(",") if t.strip()]

    await ws_manager.connect(websocket, trader_ids)

    try:
        while True:
            # 接收客户端消息（用于心跳 / 动态修改订阅）
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif msg.get("type") == "subscribe":
                    # 动态添加订阅
                    new_ids = msg.get("traderIds", [])
                    if new_ids:
                        await ws_manager.disconnect(websocket)
                        await ws_manager.connect(websocket, new_ids)
                        await websocket.send_text(json.dumps({
                            "type": "subscribed",
                            "traderIds": new_ids,
                        }))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
        logger.info(f"WS client disconnected: {websocket.client}")
