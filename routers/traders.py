from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from db.models import Operation, Position, PositionHistory, Trader
from pusher.webhook import webhook_pusher
from pusher.ws_manager import ws_manager

router = APIRouter(prefix="/api", tags=["traders"])


# ── Response Models ──

class TraderOut(BaseModel):
    trader_id: str
    nick_name: Optional[str] = None
    follower_count: Optional[int] = None
    pnl: Optional[float] = None
    roi: Optional[float] = None
    rank: Optional[int] = None
    position_shared: bool
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PositionOut(BaseModel):
    symbol: str
    entry_price: Optional[float] = None
    mark_price: Optional[float] = None
    pnl: Optional[float] = None
    roe: Optional[float] = None
    amount: Optional[float] = None
    leverage: Optional[int] = None
    update_time: Optional[int] = None
    snapshot_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class HistoryOut(BaseModel):
    symbol: str
    entry_price: Optional[float] = None
    close_price: Optional[float] = None
    pnl: Optional[float] = None
    roe: Optional[float] = None
    amount: Optional[float] = None
    leverage: Optional[int] = None
    side: Optional[str] = None
    open_time: Optional[int] = None
    close_time: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class OperationOut(BaseModel):
    symbol: str
    action: Optional[str] = None
    side: Optional[str] = None
    amount: Optional[float] = None
    price: Optional[float] = None
    timestamp: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class WebhookConfig(BaseModel):
    url: str


class StatusOut(BaseModel):
    active_ws_connections: int
    webhook_urls: List[str]
    monitored_traders: int
    server_time: str


# ── Endpoints ──

@router.get("/traders", response_model=List[TraderOut])
async def list_traders(session: AsyncSession = Depends(get_session)):
    """查询所有监控中的交易员。"""
    result = await session.execute(
        select(Trader).order_by(Trader.rank.asc())
    )
    return result.scalars().all()


@router.get("/traders/{trader_id}/positions", response_model=List[PositionOut])
async def get_positions(
    trader_id: str,
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """查询交易员最新仓位快照。"""
    result = await session.execute(
        select(Position)
        .where(Position.trader_id == trader_id)
        .order_by(Position.snapshot_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/traders/{trader_id}/history", response_model=List[HistoryOut])
async def get_history(
    trader_id: str,
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """查询交易员仓位历史。"""
    result = await session.execute(
        select(PositionHistory)
        .where(PositionHistory.trader_id == trader_id)
        .order_by(PositionHistory.close_time.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/traders/{trader_id}/operations", response_model=List[OperationOut])
async def get_operations(
    trader_id: str,
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """查询交易员最新操作记录。"""
    result = await session.execute(
        select(Operation)
        .where(Operation.trader_id == trader_id)
        .order_by(Operation.timestamp.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/config/webhook")
async def add_webhook(config: WebhookConfig):
    """添加 Webhook URL。"""
    webhook_pusher.add_url(config.url)
    return {"message": "Webhook added", "urls": webhook_pusher.get_urls()}


@router.delete("/config/webhook")
async def remove_webhook(config: WebhookConfig):
    """删除 Webhook URL。"""
    webhook_pusher.remove_url(config.url)
    return {"message": "Webhook removed", "urls": webhook_pusher.get_urls()}


@router.get("/status", response_model=StatusOut)
async def get_status(session: AsyncSession = Depends(get_session)):
    """获取系统运行状态。"""
    result = await session.execute(select(Trader))
    trader_count = len(result.scalars().all())
    return StatusOut(
        active_ws_connections=ws_manager.active_count,
        webhook_urls=webhook_pusher.get_urls(),
        monitored_traders=trader_count,
        server_time=datetime.now(timezone.utc).isoformat(),
    )
