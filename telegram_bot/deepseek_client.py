"""DeepSeek AI 客户端 — 支持上下文记忆的对话。"""
import json
import logging
from typing import List, Optional

import httpx
from sqlalchemy import delete, select

from config import settings
from db.database import async_session
from db.models import Trader, Position
from telegram_bot.models import ConversationMessage

logger = logging.getLogger(__name__)


class DeepSeekClient:
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def start(self):
        self._client = httpx.AsyncClient(timeout=60)

    async def stop(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _build_system_prompt(self, lang: str) -> str:
        """构造系统提示词，注入实时交易员数据摘要。"""
        data_summary = await self._get_data_snapshot()
        if lang == "en":
            return (
                "You are Smart Money AI Agent, an AI assistant specialized in Binance Smart Money data analysis.\n\n"
                "Your data comes from the Binance Smart Money leaderboard. You have access to:\n"
                "- Top trader rankings (PNL, ROI, follower count, rank)\n"
                "- Current positions (symbol, direction, leverage, PnL)\n"
                "- Position history (entry/close price, PnL, holding time)\n"
                "- Recent operations (open long/short, close, add/reduce position)\n\n"
                f"Current data snapshot:\n{data_summary}\n\n"
                "Reply in English. Be professional, concise, and back your analysis with data."
            )
        return (
            "你是 Smart Money AI Agent，一个专注于 Binance Smart Money 数据分析的 AI 助手。\n\n"
            "你的数据来源是 Binance Smart Money 排行榜，你可以访问以下实时数据：\n"
            "- 顶级交易员排行榜（PNL、ROI、关注人数、排名）\n"
            "- 交易员当前持仓（交易对、方向、杠杆、盈亏）\n"
            "- 历史仓位（开仓/平仓价、盈亏、持仓时间）\n"
            "- 最新操作记录（开多/开空/平仓/加仓/减仓）\n\n"
            f"当前数据快照：\n{data_summary}\n\n"
            "请用中文回复。分析要专业、简洁，给出有数据支撑的观点。"
        )

    async def _get_data_snapshot(self) -> str:
        """从 DB 获取当前 Top 交易员 + 仓位摘要。"""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(Trader).order_by(Trader.rank.asc()).limit(10)
                )
                traders = result.scalars().all()
                if not traders:
                    return "(暂无交易员数据)"

                lines = []
                for tr in traders:
                    pnl_str = f"${tr.pnl:,.0f}" if tr.pnl else "N/A"
                    roi_str = f"{tr.roi * 100:.1f}%" if tr.roi else "N/A"
                    status = "公开" if tr.position_shared else "私密"
                    lines.append(
                        f"#{tr.rank} {tr.nick_name} | PNL: {pnl_str} | ROI: {roi_str} | "
                        f"关注: {tr.follower_count or 0} | 仓位: {status}"
                    )

                    # 获取该交易员最新仓位
                    pos_result = await session.execute(
                        select(Position)
                        .where(Position.trader_id == tr.trader_id)
                        .order_by(Position.snapshot_at.desc())
                        .limit(5)
                    )
                    positions = pos_result.scalars().all()
                    for p in positions:
                        side = "LONG" if (p.amount or 0) > 0 else "SHORT"
                        pnl_p = f"${p.pnl:,.0f}" if p.pnl else "N/A"
                        lines.append(
                            f"  └ {p.symbol} {side} ×{p.leverage or '?'} | PnL: {pnl_p}"
                        )

                return "\n".join(lines)
        except Exception as e:
            logger.error(f"Failed to get data snapshot: {e}")
            return "(数据加载失败)"

    async def _load_history(self, chat_id: int) -> List[dict]:
        """加载用户最近 N 条对话历史。"""
        async with async_session() as session:
            result = await session.execute(
                select(ConversationMessage)
                .where(ConversationMessage.chat_id == chat_id)
                .order_by(ConversationMessage.created_at.desc())
                .limit(settings.CONVERSATION_WINDOW)
            )
            messages = list(reversed(result.scalars().all()))
            return [{"role": m.role, "content": m.content} for m in messages]

    async def _save_message(self, chat_id: int, role: str, content: str):
        """保存一条对话消息。"""
        async with async_session() as session:
            msg = ConversationMessage(chat_id=chat_id, role=role, content=content)
            session.add(msg)
            await session.commit()

    async def clear_history(self, chat_id: int):
        """清空用户对话上下文。"""
        async with async_session() as session:
            await session.execute(
                delete(ConversationMessage).where(ConversationMessage.chat_id == chat_id)
            )
            await session.commit()

    async def chat(self, chat_id: int, user_message: str, lang: str = "zh") -> str:
        """发送消息并获取 AI 回复。"""
        if not self._client:
            await self.start()

        # 构造 messages
        system_prompt = await self._build_system_prompt(lang)
        history = await self._load_history(chat_id)
        messages = [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": user_message},
        ]

        try:
            resp = await self._client.post(
                f"{settings.DEEPSEEK_BASE_URL}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.DEEPSEEK_MODEL,
                    "messages": messages,
                    "max_tokens": settings.DEEPSEEK_MAX_TOKENS,
                    "temperature": 0.7,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            reply = data["choices"][0]["message"]["content"]

            # 保存对话
            await self._save_message(chat_id, "user", user_message)
            await self._save_message(chat_id, "assistant", reply)

            return reply
        except Exception as e:
            logger.error(f"DeepSeek API error: {e}")
            raise


deepseek_client = DeepSeekClient()
