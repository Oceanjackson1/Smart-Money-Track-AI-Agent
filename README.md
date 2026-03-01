# Smart Money Track AI Agent

Smart Money Track AI Agent 是一个面向 Binance Smart Money 的实时监控与分析系统。它会持续跟踪聪明钱排行榜中的顶级交易员，抓取榜单与资料数据，检测仓位和操作变化，并通过 WebSocket、Webhook、Telegram Bot 多通道对外推送；同时集成 DeepSeek，对已采集数据进行问答和分析。

整个项目以 Python 异步栈实现，适合个人部署、策略观察、告警分发和 Telegram 交互查询。

## 核心能力

- 实时抓取 Binance Smart Money 排行榜前 N 名交易员
- 持续监控交易员资料、仓位快照、历史仓位和最新操作
- 自动识别开仓、平仓、调仓、新操作等关键事件
- 同时通过 WebSocket、Webhook、Telegram Bot 推送告警
- 进程在启动、异常、停止时会自动向 Pixel Office 心跳面板上报状态
- 提供完整 REST API，可用于自建面板或二次开发
- 提供 Telegram AI Agent，支持问答、订阅、状态查询和中英文切换
- 使用 Playwright 绕过 AWS WAF JavaScript Challenge，提升抓取稳定性
- 使用 SQLite 异步持久化，保留历史数据便于后续分析

## 适用场景

- 做 Binance Smart Money 榜单的长期监控
- 搭建个人聪明钱追踪服务
- 将信号转发到企业微信、飞书、钉钉、Discord、Telegram 等下游系统
- 用 Telegram Bot 做移动端查询和 AI 分析入口
- 为量化、投研或内容团队提供基础数据源

## 系统架构

系统分为五层：

1. 抓取层：使用 Playwright 和 httpx 访问 Binance Smart Money 相关接口，处理 WAF 验证、会话续期和数据请求。
2. 任务层：定时轮询交易员列表、仓位、历史、操作记录，并执行差异比对。
3. 存储层：通过 SQLAlchemy 和 aiosqlite 将交易员、仓位、历史、操作、Telegram 用户和对话上下文持久化。
4. 推送层：将事件同步广播到 WebSocket 客户端、Webhook 地址以及 Telegram 订阅用户。
5. 交互层：对外提供 REST API、WebSocket 接口，以及 Telegram AI Agent。

## 技术栈

| 组件 | 技术方案 | 说明 |
|------|----------|------|
| Web 服务 | FastAPI | 提供 REST API 与 WebSocket 服务 |
| 浏览器自动化 | Playwright + playwright-stealth | 通过浏览器上下文通过 WAF 校验并隐藏自动化特征 |
| 数据存储 | SQLAlchemy + aiosqlite | 异步 ORM 与本地 SQLite 持久化 |
| 定时任务 | APScheduler | 定时轮询榜单、仓位和历史数据 |
| 网络请求 | httpx | 发送 Webhook 和其他 HTTP 请求 |
| Telegram 机器人 | python-telegram-bot | 提供命令交互、实时订阅和自由文本对话 |
| AI 能力 | DeepSeek API | 基于已存储的交易员数据进行分析问答 |
| 运行方式 | uvicorn | 运行 FastAPI 应用 |

## 项目目录

```text
smart-money-track/
├── main.py                   # 服务入口：应用初始化、生命周期、调度器启动
├── config.py                 # 环境变量与配置项定义
├── requirements.txt          # Python 依赖
├── .env.example              # 环境变量示例
├── db/                       # 数据库层
│   ├── database.py           # 异步引擎和会话工厂
│   └── models.py             # 数据表模型
├── scraper/                  # 抓取层
│   ├── browser.py            # 浏览器与 WAF 会话管理
│   ├── api_client.py         # Binance Smart Money 接口封装
│   └── tasks.py              # 轮询任务与事件构造逻辑
├── pusher/                   # 推送层
│   ├── webhook.py            # Webhook 推送器
│   └── ws_manager.py         # WebSocket 连接与订阅管理
├── routers/                  # API 路由层
│   ├── traders.py            # 交易员、仓位、历史、配置等接口
│   └── ws.py                 # WebSocket 接口
├── telegram_bot/             # Telegram 机器人
│   ├── bot.py                # 机器人生命周期管理
│   ├── i18n.py               # 中英文文案
│   ├── deepseek_client.py    # AI 对话客户端
│   ├── alert_bridge.py       # 系统事件到 Telegram 的桥接层
│   ├── models.py             # Telegram 用户和对话模型
│   └── handlers/             # 命令处理器
└── tests/                    # 单元测试与调试脚本
```

## 环境要求

- Python 3.9 或更高版本
- Node 运行环境不是必须，但 Playwright 首次安装需要下载浏览器
- 可访问 Binance 和 Telegram 的网络环境
- 如果启用 AI 分析，需要有效的 DeepSeek API Key

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/Oceanjackson1/Smart-Money-Track-AI-Agent.git
cd Smart-Money-Track-AI-Agent
```

### 2. 创建虚拟环境并安装依赖

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Windows 用户可使用：

```powershell
venv\Scripts\activate
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

建议根据业务需求修改 `.env`：

```env
# 轮询间隔
POLL_INTERVAL_MINUTES=5
HISTORY_POLL_INTERVAL_MINUTES=30

# 监控榜单前 N 名
TOP_TRADERS_COUNT=20

# Webhook 推送地址，多个地址用英文逗号分隔
WEBHOOK_URLS=

# 服务监听
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# 数据库
DATABASE_URL=sqlite+aiosqlite:///./smart_money.db

# 日志级别
LOG_LEVEL=INFO

# Telegram 机器人
TG_BOT_TOKEN=

# DeepSeek
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-chat

# Pixel Office 心跳
AGENT_HEARTBEAT_ENABLED=true
AGENT_HEARTBEAT_URL=https://ewsrmznakzzkkcwftgjd.supabase.co/rest/v1/agents
AGENT_HEARTBEAT_API_KEY=sb_publishable_pbt93uIf5oX9xN1taOVJUQ_mCQve3M4
AGENT_HEARTBEAT_ID=smart-money-track-ai-agent-service
AGENT_HEARTBEAT_NAME=Smart Money AI Agent
AGENT_HEARTBEAT_ROLE=product
AGENT_HEARTBEAT_ROLE_LABEL_ZH=聪明钱数据分析师
```

### 4. 启动服务

```bash
python main.py
```

启动后系统会自动执行以下动作：

1. 初始化数据库表结构
2. 启动 Playwright 浏览器并完成 WAF 挑战
3. 启动 Binance Smart Money API 客户端
4. 启动 Webhook 推送器
5. 注册并启动定时轮询任务
6. 立即执行一次初始数据抓取
7. 如已配置 `TG_BOT_TOKEN`，则启动 Telegram Bot
8. 对外提供 HTTP API 与 WebSocket 服务

成功启动后可访问：

- 接口文档：`http://localhost:8000/docs`
- 服务根地址：`http://localhost:8000/`
- WebSocket 地址：`ws://localhost:8000/ws`

## 配置项说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `POLL_INTERVAL_MINUTES` | `5` | 仓位与最新操作轮询间隔，单位分钟 |
| `HISTORY_POLL_INTERVAL_MINUTES` | `30` | 历史仓位轮询间隔，单位分钟 |
| `TOP_TRADERS_COUNT` | `20` | 监控榜单前多少名交易员 |
| `WEBHOOK_URLS` | 空 | 事件推送地址列表，支持多个 |
| `SERVER_HOST` | `0.0.0.0` | 服务监听地址 |
| `SERVER_PORT` | `8000` | 服务监听端口 |
| `DATABASE_URL` | `sqlite+aiosqlite:///./smart_money.db` | 数据库连接字符串 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `TG_BOT_TOKEN` | 空 | Telegram Bot Token |
| `DEEPSEEK_API_KEY` | 空 | DeepSeek API 密钥 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 使用的 DeepSeek 模型 |
| `AGENT_HEARTBEAT_ENABLED` | `true` | 是否启用 Pixel Office 心跳上报 |
| `AGENT_HEARTBEAT_URL` | Supabase `agents` 接口 | 心跳上报地址 |
| `AGENT_HEARTBEAT_API_KEY` | publishable key | Supabase publishable key |
| `AGENT_HEARTBEAT_ID` | `smart-money-track-ai-agent-service` | 大屏中的固定代理 ID |
| `AGENT_HEARTBEAT_NAME` | `Smart Money AI Agent` | 大屏展示名称 |
| `AGENT_HEARTBEAT_ROLE` | `product` | 大屏角色枚举值 |
| `AGENT_HEARTBEAT_ROLE_LABEL_ZH` | `聪明钱数据分析师` | 大屏中文头衔 |

## 对外接口

### REST API

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 返回服务名称、版本和文档入口 |
| `GET` | `/api/traders` | 获取当前监控中的交易员列表 |
| `GET` | `/api/traders/{trader_id}/positions` | 获取某个交易员的当前仓位快照 |
| `GET` | `/api/traders/{trader_id}/history` | 获取某个交易员的历史仓位 |
| `GET` | `/api/traders/{trader_id}/operations` | 获取某个交易员的最新操作记录 |
| `POST` | `/api/config/webhook` | 新增一个 Webhook 推送地址 |
| `DELETE` | `/api/config/webhook` | 删除一个 Webhook 推送地址 |
| `GET` | `/api/status` | 获取系统状态 |

仓位、历史和操作记录接口支持 `limit` 参数，范围为 `1-200`，默认值为 `50`。

### WebSocket 接口

连接地址：

```text
ws://localhost:8000/ws
```

支持两种订阅方式：

```text
# 订阅所有交易员的事件
ws://localhost:8000/ws

# 仅订阅指定交易员
ws://localhost:8000/ws?traders=4808778158325714688,4881573544529703681
```

客户端可发送以下消息：

```json
{"type": "ping"}
```

服务端会返回：

```json
{"type": "pong"}
```

动态切换订阅：

```json
{"type": "subscribe", "traderIds": ["trader_id_1", "trader_id_2"]}
```

成功后返回：

```json
{"type": "subscribed", "traderIds": ["trader_id_1", "trader_id_2"]}
```

### Telegram 机器人

在 Telegram 中搜索你配置的机器人并发送 `/start` 即可使用。

支持的命令如下：

| 命令 | 说明 |
|------|------|
| `/start` | 开始使用并查看帮助 |
| `/help` | 查看帮助信息 |
| `/traders` | 查看交易员排行榜 |
| `/positions <ID>` | 查看某位交易员当前仓位 |
| `/history <ID>` | 查看某位交易员历史仓位 |
| `/operations <ID>` | 查看某位交易员最新操作 |
| `/status` | 查看系统状态 |
| `/subscribe [ID...]` | 订阅全部交易员或指定交易员的实时警报 |
| `/unsubscribe` | 取消警报订阅 |
| `/alerts` | 查看当前订阅设置 |
| `/ask <问题>` | 让 AI 基于已采集数据进行分析 |
| `/language` | 切换中英文界面 |

补充说明：

- 所有带 `<ID>` 的命令既支持完整交易员 ID，也支持榜单排名序号
- 直接发送普通文本，也会自动触发 AI 对话
- 输入 `/ask clear` 可清空当前会话上下文
- 订阅警报后，机器人会主动推送开仓、平仓、调仓和新操作事件

## 事件格式

WebSocket、Webhook 和 Telegram 桥接层共用同一套事件结构。示例：

```json
{
  "event": "position_opened",
  "timestamp": "2026-02-28T15:00:00+00:00",
  "trader": {
    "traderId": "4808778158325714688",
    "nickName": "投机投机之路",
    "rank": 3
  },
  "data": {
    "symbol": "BTCUSDT",
    "side": "LONG",
    "entryPrice": 85000.0,
    "leverage": 10,
    "amount": 0.5,
    "pnl": 1200.0,
    "roe": 0.028
  }
}
```

事件类型说明：

| 事件名 | 含义 | 触发条件 |
|--------|------|----------|
| `position_opened` | 新开仓 | 检测到新的交易对仓位 |
| `position_closed` | 平仓 | 原有仓位在新快照中消失 |
| `position_updated` | 调仓 | 仓位数量变化超过阈值 |
| `new_operation` | 新操作 | 检测到新的交易操作记录 |

## 数据模型

### Trader 交易员表

| 字段 | 类型 | 说明 |
|------|------|------|
| `trader_id` | String | Binance 交易员唯一 ID |
| `nick_name` | String | 昵称 |
| `user_photo_url` | String | 头像地址 |
| `follower_count` | Integer | 关注人数 |
| `pnl` | Float | 盈亏金额 |
| `roi` | Float | 收益率 |
| `rank` | Integer | 当前排名 |
| `position_shared` | Boolean | 是否公开仓位 |
| `introduction` | Text | 交易员简介 |
| `updated_at` | DateTime | 最后更新时间 |

### Position 当前仓位表

| 字段 | 类型 | 说明 |
|------|------|------|
| `trader_id` | String | 交易员 ID |
| `symbol` | String | 交易对，例如 `BTCUSDT` |
| `entry_price` | Float | 开仓均价 |
| `mark_price` | Float | 标记价格 |
| `pnl` | Float | 未实现盈亏 |
| `roe` | Float | 收益率 |
| `amount` | Float | 持仓数量，正数为多头，负数为空头 |
| `leverage` | Integer | 杠杆倍数 |
| `snapshot_at` | DateTime | 快照时间 |

### PositionHistory 历史仓位表

| 字段 | 类型 | 说明 |
|------|------|------|
| `trader_id` | String | 交易员 ID |
| `symbol` | String | 交易对 |
| `entry_price` | Float | 开仓均价 |
| `close_price` | Float | 平仓均价 |
| `pnl` | Float | 已实现盈亏 |
| `roe` | Float | 收益率 |
| `side` | String | 持仓方向，`LONG` 或 `SHORT` |
| `open_time` | BigInteger | 开仓时间戳 |
| `close_time` | BigInteger | 平仓时间戳 |

### Operation 操作记录表

| 字段 | 类型 | 说明 |
|------|------|------|
| `trader_id` | String | 交易员 ID |
| `symbol` | String | 交易对 |
| `action` | String | 操作类型 |
| `side` | String | 方向 |
| `amount` | Float | 数量 |
| `price` | Float | 成交价格 |
| `timestamp` | BigInteger | 操作时间戳 |

### TelegramUser 机器人用户表

| 字段 | 类型 | 说明 |
|------|------|------|
| `chat_id` | BigInteger | Telegram 聊天 ID，唯一索引 |
| `username` | String | Telegram 用户名 |
| `language` | String | 语言偏好，支持 `zh` 和 `en` |
| `subscribed` | Boolean | 是否启用警报订阅 |
| `subscribed_trader_ids` | Text | 订阅的交易员 ID 列表，空数组表示订阅全部 |

### ConversationMessage 对话上下文表

| 字段 | 类型 | 说明 |
|------|------|------|
| `chat_id` | BigInteger | Telegram 聊天 ID |
| `role` | String | 角色，`user` 或 `assistant` |
| `content` | Text | 对话内容 |
| `created_at` | DateTime | 创建时间 |

## 运行测试

运行单元测试：

```bash
python -m pytest tests/ -v --ignore=tests/test_e2e_smoke.py
```

运行真实接口冒烟测试：

```bash
python tests/test_e2e_smoke.py
```

测试覆盖概览：

| 测试文件 | 覆盖范围 | 用例数 |
|----------|----------|--------|
| `test_01_config.py` | 配置加载、默认值和类型转换 | 4 |
| `test_02_database.py` | ORM 模型、索引与基本 CRUD | 7 |
| `test_03_pusher.py` | Webhook 推送与 WebSocket 连接管理 | 9 |
| `test_04_api_client.py` | 接口封装、数据解析和异常处理 | 8 |
| `test_05_tasks.py` | 事件构造、轮询逻辑、去重与状态检测 | 9 |
| `test_06_rest_api.py` | REST API 响应格式和状态码 | 9 |
| `test_08_telegram_bot.py` | 机器人文案、模型、桥接和交互逻辑 | 14 |
| `test_e2e_smoke.py` | 真实 Binance API 冒烟测试 | 19 |

## 部署建议

- 建议先在本地验证 `.env` 配置，再部署到服务器
- 若需要稳定运行，建议使用 `systemd`、`supervisor` 或 Docker 进行托管
- 若服务暴露到公网，建议在反向代理层补充鉴权、限流和来源控制
- Webhook 下游建议自行增加签名验证，防止恶意请求伪造

## 反检测与稳定性策略

| 策略 | 说明 |
|------|------|
| WAF 绕过 | 通过 Playwright 执行挑战脚本并维护有效会话 |
| 浏览器指纹处理 | 使用 `playwright-stealth` 降低自动化暴露概率 |
| 请求节流 | 在接口调用间加入随机延迟，避免过于规律的访问模式 |
| 并发限制 | 控制并发请求数，降低封禁风险 |
| 会话续期 | 定期刷新 WAF 相关令牌和浏览器上下文 |
| 自动重试 | 请求失败时执行重试，403 场景触发会话刷新 |

## 已知限制

- Binance Smart Money 的部分仓位详情、历史仓位和操作记录接口依赖登录状态。未登录时，当前实现可能返回空列表。
- 项目默认使用 SQLite，适合个人使用和轻量部署；如果计划多实例运行，建议替换为 PostgreSQL 等独立数据库。
- 当前 REST API 未内置权限控制，更适合在可信网络、反向代理或已有鉴权体系后使用。
- Binance 页面结构和接口字段可能调整，后续如有变动，需要同步更新抓取逻辑。

## 常见问题

### 1. 服务启动后没有仓位数据

这通常不是程序异常，而是 Binance Smart Money 对仓位、历史和操作接口增加了登录限制。排行榜和交易员资料通常仍可获取。

### 2. Telegram Bot 没有启动

请确认 `.env` 中配置了有效的 `TG_BOT_TOKEN`。如果没有配置，主服务会正常启动，但机器人功能会被自动禁用。

### 3. AI 问答无法使用

请确认配置了 `DEEPSEEK_API_KEY`，并且部署环境可以访问 DeepSeek API。

### 4. Webhook 没有收到推送

请确认：

- Webhook URL 已通过接口正确添加
- 下游服务允许接收来自当前服务器的请求
- 日志中没有网络错误、超时或 4xx/5xx 响应

## 开发与二次扩展建议

- 扩展更多交易所或榜单来源时，可直接在 `scraper/` 下增加新的客户端和任务
- 如果要做前端监控面板，可直接消费 `/api/*` 或 WebSocket 数据
- 如果要增强告警能力，可在 `pusher/` 中补充更多推送通道
- 如果要增强 AI 分析质量，可在 `telegram_bot/deepseek_client.py` 中补充提示词和统计摘要

## 许可证

本项目采用 MIT 许可证，详见 `LICENSE` 文件。
