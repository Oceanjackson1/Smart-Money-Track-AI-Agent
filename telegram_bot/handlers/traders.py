"""处理 /traders, /positions, /history, /operations 命令。"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from db.database import async_session
from db.models import Operation, Position, PositionHistory, Trader
from telegram_bot.handlers.start import get_user_lang
from telegram_bot.i18n import t

logger = logging.getLogger(__name__)


async def _resolve_trader(arg: str) -> Optional[Trader]:
    """通过排名序号或 trader_id 查找交易员。"""
    async with async_session() as session:
        # 尝试作为排名序号
        if arg.isdigit() and len(arg) <= 4:
            rank = int(arg)
            result = await session.execute(
                select(Trader).where(Trader.rank == rank)
            )
            trader = result.scalar_one_or_none()
            if trader:
                return trader

        # 作为 trader_id
        result = await session.execute(
            select(Trader).where(Trader.trader_id == arg)
        )
        return result.scalar_one_or_none()


async def traders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/traders — 查看交易员排行榜。"""
    lang = await get_user_lang(update.effective_chat.id)

    async with async_session() as session:
        result = await session.execute(
            select(Trader).order_by(Trader.rank.asc()).limit(20)
        )
        traders = result.scalars().all()

    if not traders:
        await update.message.reply_text(t("traders_empty", lang))
        return

    lines = [t("traders_title", lang)]
    for tr in traders:
        rank_icon = "🏆" if tr.rank == 1 else "🥈" if tr.rank == 2 else "🥉" if tr.rank == 3 else ""
        pnl_str = f"${tr.pnl:,.0f}" if tr.pnl else "N/A"
        roi_str = f"{tr.roi * 100:.1f}%" if tr.roi else "N/A"
        status = t("position_public", lang) if tr.position_shared else t("position_private", lang)
        followers = tr.follower_count or 0

        lines.append(
            f"<b>#{tr.rank} {rank_icon} {tr.nick_name}</b>\n"
            f"   PNL: {pnl_str}  |  ROI: {roi_str}\n"
            f"   {t('followers', lang)}: {followers:,}  |  {t('positions_label', lang)}: {status}\n"
            f"   ID: <code>{tr.trader_id}</code>\n"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def positions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/positions <ID> — 查看交易员当前仓位。"""
    lang = await get_user_lang(update.effective_chat.id)

    if not context.args:
        await update.message.reply_text(
            t("need_trader_id", lang).format(cmd="positions"), parse_mode="HTML"
        )
        return

    trader = await _resolve_trader(context.args[0])
    if not trader:
        await update.message.reply_text(t("trader_not_found", lang))
        return

    async with async_session() as session:
        result = await session.execute(
            select(Position)
            .where(Position.trader_id == trader.trader_id)
            .order_by(Position.snapshot_at.desc())
            .limit(20)
        )
        positions = result.scalars().all()

    if not positions:
        text = t("positions_title", lang).format(name=trader.nick_name)
        text += "\n" + t("positions_empty", lang)
        await update.message.reply_text(text, parse_mode="HTML")
        return

    # 按 symbol 去重（保留最新）
    seen = {}
    for p in positions:
        if p.symbol not in seen:
            seen[p.symbol] = p

    lines = [t("positions_title", lang).format(name=trader.nick_name)]
    for i, (symbol, p) in enumerate(seen.items(), 1):
        side = "LONG" if (p.amount or 0) > 0 else "SHORT"
        side_icon = "🟢" if side == "LONG" else "🔴"
        entry = f"${p.entry_price:,.2f}" if p.entry_price else "N/A"
        mark = f"${p.mark_price:,.2f}" if p.mark_price else "N/A"
        pnl_str = f"${p.pnl:,.2f}" if p.pnl is not None else "N/A"
        roe_str = f"{p.roe * 100:.2f}%" if p.roe is not None else ""
        pnl_display = f"{pnl_str} ({roe_str})" if roe_str else pnl_str

        lines.append(
            f"{i}. <b>{symbol}</b> {side_icon} {side} ×{p.leverage or '?'}\n"
            f"   {'开仓价' if lang == 'zh' else 'Entry'}: {entry}  |  "
            f"{'标记价' if lang == 'zh' else 'Mark'}: {mark}\n"
            f"   {'盈亏' if lang == 'zh' else 'PnL'}: {pnl_display}\n"
            f"   {'数量' if lang == 'zh' else 'Amount'}: {p.amount or 'N/A'}\n"
        )

    if positions[0].snapshot_at:
        lines.append(f"\n{t('last_updated', lang)}: {positions[0].snapshot_at.strftime('%Y-%m-%d %H:%M')}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/history <ID> — 查看交易员历史仓位。"""
    lang = await get_user_lang(update.effective_chat.id)

    if not context.args:
        await update.message.reply_text(
            t("need_trader_id", lang).format(cmd="history"), parse_mode="HTML"
        )
        return

    trader = await _resolve_trader(context.args[0])
    if not trader:
        await update.message.reply_text(t("trader_not_found", lang))
        return

    async with async_session() as session:
        result = await session.execute(
            select(PositionHistory)
            .where(PositionHistory.trader_id == trader.trader_id)
            .order_by(PositionHistory.close_time.desc())
            .limit(10)
        )
        records = result.scalars().all()

    if not records:
        text = t("history_title", lang).format(name=trader.nick_name)
        text += "\n" + t("history_empty", lang)
        await update.message.reply_text(text, parse_mode="HTML")
        return

    lines = [t("history_title", lang).format(name=trader.nick_name)]
    for i, h in enumerate(records, 1):
        side_icon = "🟢" if h.side == "LONG" else "🔴"
        pnl_str = f"${h.pnl:,.2f}" if h.pnl is not None else "N/A"
        roe_str = f"({h.roe * 100:.2f}%)" if h.roe is not None else ""
        entry = f"${h.entry_price:,.2f}" if h.entry_price else "N/A"
        close = f"${h.close_price:,.2f}" if h.close_price else "N/A"

        lines.append(
            f"{i}. <b>{h.symbol}</b> {side_icon} {h.side or '?'} ×{h.leverage or '?'}\n"
            f"   {'开仓' if lang == 'zh' else 'Entry'}: {entry} → {'平仓' if lang == 'zh' else 'Close'}: {close}\n"
            f"   {'盈亏' if lang == 'zh' else 'PnL'}: {pnl_str} {roe_str}\n"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def operations_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/operations <ID> — 查看交易员最新操作。"""
    lang = await get_user_lang(update.effective_chat.id)

    if not context.args:
        await update.message.reply_text(
            t("need_trader_id", lang).format(cmd="operations"), parse_mode="HTML"
        )
        return

    trader = await _resolve_trader(context.args[0])
    if not trader:
        await update.message.reply_text(t("trader_not_found", lang))
        return

    async with async_session() as session:
        result = await session.execute(
            select(Operation)
            .where(Operation.trader_id == trader.trader_id)
            .order_by(Operation.timestamp.desc())
            .limit(10)
        )
        records = result.scalars().all()

    if not records:
        text = t("operations_title", lang).format(name=trader.nick_name)
        text += "\n" + t("operations_empty", lang)
        await update.message.reply_text(text, parse_mode="HTML")
        return

    lines = [t("operations_title", lang).format(name=trader.nick_name)]
    for i, op in enumerate(records, 1):
        price_str = f"${op.price:,.2f}" if op.price else "N/A"
        ts = ""
        if op.timestamp:
            dt = datetime.fromtimestamp(op.timestamp / 1000, tz=timezone.utc)
            ts = dt.strftime("%m-%d %H:%M")

        lines.append(
            f"{i}. <b>{op.symbol}</b> | {op.action or '?'} | {op.side or ''}\n"
            f"   {'价格' if lang == 'zh' else 'Price'}: {price_str}  |  "
            f"{'数量' if lang == 'zh' else 'Amt'}: {op.amount or 'N/A'}  |  {ts}\n"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")
