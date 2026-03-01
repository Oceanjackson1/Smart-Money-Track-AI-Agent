from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base

# 导入 Telegram 模型，确保 Base.metadata.create_all 能自动建表
from telegram_bot.models import ConversationMessage, TelegramUser  # noqa: F401


class Trader(Base):
    __tablename__ = "traders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trader_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    nick_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    user_photo_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    follower_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    position_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    twitter_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    introduction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trader_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    entry_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mark_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 正=多, 负=空
    leverage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    update_time: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # 毫秒时间戳
    snapshot_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), nullable=True)


class PositionHistory(Base):
    __tablename__ = "position_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trader_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    entry_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    close_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    leverage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    side: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # LONG / SHORT
    open_time: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    close_time: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), nullable=True)


class Operation(Base):
    __tablename__ = "operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trader_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # 开多/开空/平仓/加仓/减仓
    side: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timestamp: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    raw_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 原始JSON，防止字段遗漏
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), nullable=True)
