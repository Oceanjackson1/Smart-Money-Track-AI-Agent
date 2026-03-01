"""双语文案系统 (中文 / English)"""

TEXTS = {
    # ── /start 欢迎消息 ──
    "welcome": {
        "zh": (
            "🤖 <b>Hey！我是你的 Smart Money AI Agent.</b>\n"
            "\n"
            "我是一个专注于 Binance Smart Money 的 AI 数据分析师。\n"
            "你可以雇我完成以下工作——从数据查询到 AI 分析。\n"
            "\n"
            "———— 📊 <b>数据查询</b> ————\n"
            "• 排行榜速览 → /traders\n"
            "• 交易员仓位 → /positions &lt;ID&gt;\n"
            "• 历史仓位   → /history &lt;ID&gt;\n"
            "• 操作记录   → /operations &lt;ID&gt;\n"
            "• 系统状态   → /status\n"
            "\n"
            "———— 🔔 <b>实时警报</b> ————\n"
            "• 订阅警报   → /subscribe\n"
            "• 取消订阅   → /unsubscribe\n"
            "• 查看订阅   → /alerts\n"
            "\n"
            "———— 🤖 <b>AI 分析</b> ————\n"
            "• AI 智能问答 → /ask &lt;问题&gt;\n"
            "  基于实时交易员数据进行分析\n"
            "• 直接发送文字也会触发 AI 对话\n"
            "• 清空上下文 → /ask clear\n"
            "\n"
            "———— 🔧 <b>设置</b> ————\n"
            "• 切换语言   → /language\n"
            "\n"
            "💡 所有 &lt;ID&gt; 参数支持交易员排名序号（如 1、2、3）\n"
            "   或完整的交易员 ID。\n"
            "输入 /help 随时查看完整菜单。"
        ),
        "en": (
            "🤖 <b>Hey! I'm your Smart Money AI Agent.</b>\n"
            "\n"
            "I'm an AI analyst focused on Binance Smart Money data.\n"
            "Hire me to do the following — from data queries to AI analysis.\n"
            "\n"
            "———— 📊 <b>Data Queries</b> ————\n"
            "• Leaderboard   → /traders\n"
            "• Positions     → /positions &lt;ID&gt;\n"
            "• History       → /history &lt;ID&gt;\n"
            "• Operations    → /operations &lt;ID&gt;\n"
            "• System Status → /status\n"
            "\n"
            "———— 🔔 <b>Real-time Alerts</b> ————\n"
            "• Subscribe     → /subscribe\n"
            "• Unsubscribe   → /unsubscribe\n"
            "• View Alerts   → /alerts\n"
            "\n"
            "———— 🤖 <b>AI Analysis</b> ————\n"
            "• Ask AI        → /ask &lt;question&gt;\n"
            "  Analysis based on live trader data\n"
            "• Free text messages also trigger AI chat\n"
            "• Clear context → /ask clear\n"
            "\n"
            "———— 🔧 <b>Settings</b> ————\n"
            "• Language      → /language\n"
            "\n"
            "💡 All &lt;ID&gt; params accept rank number (1, 2, 3...)\n"
            "   or full trader ID.\n"
            "Type /help for the full menu anytime."
        ),
    },
    "switch_lang_btn": {
        "zh": "🌐 Switch to English",
        "en": "🌐 切换到中文",
    },
    "lang_switched": {
        "zh": "✅ 已切换到中文",
        "en": "✅ Switched to English",
    },
    # ── /traders ──
    "traders_title": {
        "zh": "📊 <b>Smart Money 排行榜</b>\n",
        "en": "📊 <b>Smart Money Leaderboard</b>\n",
    },
    "traders_empty": {
        "zh": "暂无交易员数据，请稍后再试。",
        "en": "No trader data available. Please try again later.",
    },
    "position_public": {"zh": "公开", "en": "Public"},
    "position_private": {"zh": "私密", "en": "Private"},
    "followers": {"zh": "关注", "en": "Followers"},
    "positions_label": {"zh": "仓位", "en": "Positions"},
    # ── /positions ──
    "positions_title": {
        "zh": "📈 <b>{name}</b> 的当前仓位\n",
        "en": "📈 Current Positions of <b>{name}</b>\n",
    },
    "positions_empty": {
        "zh": "该交易员暂无仓位数据。\n（仓位数据需要 Binance 登录权限）",
        "en": "No position data for this trader.\n(Position data requires Binance login)",
    },
    "last_updated": {"zh": "最后更新", "en": "Last updated"},
    # ── /history ──
    "history_title": {
        "zh": "📜 <b>{name}</b> 的历史仓位\n",
        "en": "📜 Position History of <b>{name}</b>\n",
    },
    "history_empty": {
        "zh": "该交易员暂无历史仓位数据。",
        "en": "No position history for this trader.",
    },
    # ── /operations ──
    "operations_title": {
        "zh": "⚡ <b>{name}</b> 的最新操作\n",
        "en": "⚡ Recent Operations of <b>{name}</b>\n",
    },
    "operations_empty": {
        "zh": "该交易员暂无操作记录。",
        "en": "No operation records for this trader.",
    },
    # ── 通用 ──
    "trader_not_found": {
        "zh": "❌ 未找到该交易员。请使用 /traders 查看可用列表。",
        "en": "❌ Trader not found. Use /traders to see the list.",
    },
    "need_trader_id": {
        "zh": "请提供交易员 ID 或排名序号。\n用法: /{cmd} &lt;ID或排名&gt;",
        "en": "Please provide a trader ID or rank number.\nUsage: /{cmd} &lt;ID or rank&gt;",
    },
    # ── /subscribe ──
    "subscribed_all": {
        "zh": "🔔 已订阅全部交易员的实时警报。\n当检测到开仓/平仓/调仓/新操作时，你将收到通知。",
        "en": "🔔 Subscribed to all traders' alerts.\nYou'll be notified on position open/close/update and new operations.",
    },
    "subscribed_specific": {
        "zh": "🔔 已订阅以下交易员的实时警报:\n{traders}",
        "en": "🔔 Subscribed to alerts for:\n{traders}",
    },
    "unsubscribed": {
        "zh": "🔕 已取消订阅实时警报。",
        "en": "🔕 Unsubscribed from alerts.",
    },
    "alerts_status_on": {
        "zh": "🔔 <b>警报状态: 已开启</b>\n\n订阅范围: {scope}",
        "en": "🔔 <b>Alert Status: ON</b>\n\nScope: {scope}",
    },
    "alerts_status_off": {
        "zh": "🔕 <b>警报状态: 已关闭</b>\n\n使用 /subscribe 开启警报。",
        "en": "🔕 <b>Alert Status: OFF</b>\n\nUse /subscribe to enable alerts.",
    },
    "scope_all": {"zh": "全部交易员", "en": "All traders"},
    # ── /status ──
    "status_title": {
        "zh": (
            "📡 <b>系统状态</b>\n\n"
            "• 监控交易员: {traders}\n"
            "• 活跃 WS 连接: {ws}\n"
            "• Webhook 数量: {webhooks}\n"
            "• TG 订阅用户: {tg_subs}\n"
            "• 服务器时间: {time}"
        ),
        "en": (
            "📡 <b>System Status</b>\n\n"
            "• Monitored Traders: {traders}\n"
            "• Active WS Connections: {ws}\n"
            "• Webhooks: {webhooks}\n"
            "• TG Subscribers: {tg_subs}\n"
            "• Server Time: {time}"
        ),
    },
    # ── /ask AI ──
    "ask_thinking": {
        "zh": "🤔 正在分析...",
        "en": "🤔 Analyzing...",
    },
    "ask_error": {
        "zh": "❌ AI 分析出错，请稍后再试。",
        "en": "❌ AI analysis failed. Please try again later.",
    },
    "ask_cleared": {
        "zh": "🗑️ 对话上下文已清空。",
        "en": "🗑️ Conversation context cleared.",
    },
    "ask_usage": {
        "zh": "用法: /ask &lt;你的问题&gt;\n例如: /ask 目前交易员整体偏向做多还是做空？",
        "en": "Usage: /ask &lt;your question&gt;\nExample: /ask Are traders mostly long or short right now?",
    },
    # ── 警报消息 ──
    "alert_position_opened": {
        "zh": (
            "🟢 <b>新开仓提醒</b>\n\n"
            "交易员: {name} (#{rank})\n"
            "交易对: {symbol}\n"
            "方向: {side} ×{leverage}\n"
            "开仓价: ${entry_price}\n"
            "数量: {amount}\n\n"
            "⏰ {time}"
        ),
        "en": (
            "🟢 <b>New Position Alert</b>\n\n"
            "Trader: {name} (#{rank})\n"
            "Pair: {symbol}\n"
            "Side: {side} ×{leverage}\n"
            "Entry: ${entry_price}\n"
            "Amount: {amount}\n\n"
            "⏰ {time}"
        ),
    },
    "alert_position_closed": {
        "zh": (
            "🔴 <b>平仓提醒</b>\n\n"
            "交易员: {name} (#{rank})\n"
            "交易对: {symbol}\n"
            "方向: {side}\n"
            "最终盈亏: {pnl}\n\n"
            "⏰ {time}"
        ),
        "en": (
            "🔴 <b>Position Closed Alert</b>\n\n"
            "Trader: {name} (#{rank})\n"
            "Pair: {symbol}\n"
            "Side: {side}\n"
            "Final PnL: {pnl}\n\n"
            "⏰ {time}"
        ),
    },
    "alert_position_updated": {
        "zh": (
            "🟡 <b>仓位调整提醒</b>\n\n"
            "交易员: {name} (#{rank})\n"
            "交易对: {symbol}\n"
            "方向: {side} ×{leverage}\n"
            "当前数量: {amount}\n"
            "盈亏: {pnl}\n\n"
            "⏰ {time}"
        ),
        "en": (
            "🟡 <b>Position Updated Alert</b>\n\n"
            "Trader: {name} (#{rank})\n"
            "Pair: {symbol}\n"
            "Side: {side} ×{leverage}\n"
            "Amount: {amount}\n"
            "PnL: {pnl}\n\n"
            "⏰ {time}"
        ),
    },
    "alert_new_operation": {
        "zh": (
            "⚡ <b>新操作提醒</b>\n\n"
            "交易员: {name} (#{rank})\n"
            "交易对: {symbol}\n"
            "操作: {action}\n"
            "方向: {side}\n"
            "价格: ${price}\n"
            "数量: {amount}\n\n"
            "⏰ {time}"
        ),
        "en": (
            "⚡ <b>New Operation Alert</b>\n\n"
            "Trader: {name} (#{rank})\n"
            "Pair: {symbol}\n"
            "Action: {action}\n"
            "Side: {side}\n"
            "Price: ${price}\n"
            "Amount: {amount}\n\n"
            "⏰ {time}"
        ),
    },
}


def t(key: str, lang: str = "zh") -> str:
    """根据 key 和语言返回文案。"""
    return TEXTS.get(key, {}).get(lang, key)
