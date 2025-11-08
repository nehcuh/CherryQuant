# CherryQuant Web API 使用指南（中文）

本指南介绍如何使用 `curl` 和常见 HTTP 工具与 CherryQuant Web API 交互。文档保留必要的专业术语（如 API、WebSocket、Swagger UI、JSON、StrategyConfig 等），其余采用中文描述，便于快速上手。

默认 API 服务信息：
- Base URL: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- 静态仪表板（如存在）: http://localhost:8000/

启动完整系统（包含 Web API）：
- 命令：`uv run python run_cherryquant_complete.py`

注意：
- 默认无鉴权（Authentication）
- 默认开启 CORS
- 请求体使用 `Content-Type: application/json`
- 响应为 `JSON`，字段名（keys）使用英文蛇形或驼峰，数值字段多数为 `float` 或 `int`


## 快速开始（Quick Start）

健康检查（Health）：
```bash
curl -s http://localhost:8000/api/v1/health | jq
```

系统状态（Status）：
```bash
curl -s http://localhost:8000/api/v1/status | jq
```

获取策略列表（List Strategies）：
```bash
curl -s http://localhost:8000/api/v1/strategies | jq
```


## 端点索引（Endpoints）

### 1) 健康与状态

- GET `/api/v1/health`
  - 返回 API 进程与关键组件的健康信息
  - 示例：
    ```bash
    curl -s http://localhost:8000/api/v1/health | jq
    ```
    示例响应：
    ```json
    {
      "status": "ok",
      "timestamp": "2025-11-06T11:23:45.123456",
      "uptime_seconds": 1234.5,
      "components": {
        "agent_manager": "initialized",
        "database": "connected",
        "websocket_clients": 0
      }
    }
    ```

- GET `/api/v1/status`
  - 返回系统总体与投资组合（Portfolio）的汇总状态
  - 示例：
    ```bash
    curl -s http://localhost:8000/api/v1/status | jq
    ```


### 2) 策略管理（Strategy Management）

- GET `/api/v1/strategies`
  - 列出当前存在的策略与其简要状态
  - 示例：
    ```bash
    curl -s http://localhost:8000/api/v1/strategies | jq
    ```

- GET `/api/v1/strategies/{strategy_id}`
  - 获取指定策略的详细信息
  - 示例：
    ```bash
    curl -s http://localhost:8000/api/v1/strategies/trend_pool_demo | jq
    ```

- POST `/api/v1/strategies`（创建策略，支持品种池/Commodity Pool）
  - 你可以传入以下三种其一：
    - `symbols`: 显式合约/品种数组（例如 `["rb","cu"]`）
    - `commodities`: 品种代码数组（例如 `["rb","i","j"]`）
    - `commodity_pool`: 预定义品种池名称（例如 `"black"`, `"metal"`, `"all"` 等）
  - 引擎会在需要时解析品种池 → 品种 → 主力合约（Dominant Contract）。
  - 字段说明（部分）：
    - `strategy_id` (string): 策略唯一 ID
    - `strategy_name` (string): 策略名称
    - `selection_mode` (string): `"ai_driven"` 或 `"manual"`
    - `max_symbols` (int): AI 可同时关注/选择的最大品种数
    - `initial_capital`、`risk_per_trade`、`leverage`、`decision_interval`、`confidence_threshold` 等交易与 AI 配置参数

  示例（推荐：使用品种池 commodity_pool）：
  ```bash
  curl -s -X POST http://localhost:8000/api/v1/strategies \
    -H "Content-Type: application/json" \
    -d '{
      "strategy_id": "trend_pool_demo",
      "strategy_name": "趋势-黑色系池",
      "commodity_pool": "black",
      "max_symbols": 3,
      "selection_mode": "ai_driven",

      "initial_capital": 100000,
      "max_position_size": 5,
      "max_positions": 2,
      "leverage": 3.0,
      "risk_per_trade": 0.02,
      "decision_interval": 300,
      "confidence_threshold": 0.6,

      "ai_model": "gpt-4",
      "ai_temperature": 0.1,
      "is_active": true,
      "manual_override": false
    }' | jq
  ```

  示例（传入 commodities 列表而不是 named pool）：
  ```bash
  curl -s -X POST http://localhost:8000/api/v1/strategies \
    -H "Content-Type: application/json" \
    -d '{
      "strategy_id": "metal_mean_reversion",
      "strategy_name": "均值回归-有色金属",
      "commodities": ["cu", "al", "zn"],
      "max_symbols": 2,
      "selection_mode": "ai_driven",

      "initial_capital": 80000,
      "max_position_size": 3,
      "max_positions": 1,
      "leverage": 2.0,
      "risk_per_trade": 0.015,
      "decision_interval": 180,
      "confidence_threshold": 0.5,

      "ai_model": "gpt-4",
      "ai_temperature": 0.2,
      "is_active": true,
      "manual_override": false
    }' | jq
  ```

  示例（传入 symbols 列表：你直接管理关注品种）：
  ```bash
  curl -s -X POST http://localhost:8000/api/v1/strategies \
    -H "Content-Type: application/json" \
    -d '{
      "strategy_id": "manual_symbols_demo",
      "strategy_name": "手工配置品种",
      "symbols": ["rb", "cu"],
      "max_symbols": 2,
      "selection_mode": "ai_driven",

      "initial_capital": 50000,
      "max_position_size": 2,
      "max_positions": 1,
      "leverage": 2.0,
      "risk_per_trade": 0.02,
      "decision_interval": 300,
      "confidence_threshold": 0.5,

      "ai_model": "gpt-4",
      "ai_temperature": 0.1,
      "is_active": true,
      "manual_override": false
    }' | jq
  ```

- POST `/api/v1/strategies/{strategy_id}/start`
- POST `/api/v1/strategies/{strategy_id}/stop`
- POST `/api/v1/strategies/{strategy_id}/pause`
- POST `/api/v1/strategies/{strategy_id}/resume`
  - 控制策略生命周期（启动/停止/暂停/恢复）
  - 示例（启动）：
    ```bash
    curl -s -X POST http://localhost:8000/api/v1/strategies/trend_pool_demo/start | jq
    ```

- DELETE `/api/v1/strategies/{strategy_id}`
  - 删除策略（运行中会先停止）
  - 示例：
    ```bash
    curl -s -X DELETE http://localhost:8000/api/v1/strategies/trend_pool_demo | jq
    ```


### 3) 交易与持仓（Trades & Positions）

- GET `/api/v1/trades`
  - 查询已记录的交易（Trade）信息（由 StrategyAgent 与 DatabaseManager 记录）
  - 示例：
    ```bash
    curl -s http://localhost:8000/api/v1/trades | jq
    ```

- GET `/api/v1/positions`
  - 返回当前持仓（Positions）
  - 示例：
    ```bash
    curl -s http://localhost:8000/api/v1/positions | jq
    ```


### 4) 风险配置与监控（Risk）

- GET `/api/v1/risk/status`
  - 返回当前组合风险状态与关键指标
  - 示例：
    ```bash
    curl -s http://localhost:8000/api/v1/risk/status | jq
    ```

- POST `/api/v1/risk/config`
  - 更新组合层风险参数（Portfolio-Level Risk Config）
  - 主要字段：
    - `max_total_capital_usage` (float, 例如 0.8)
    - `max_correlation_threshold` (float, 例如 0.7)
    - `max_sector_concentration` (float, 例如 0.4)
    - `portfolio_stop_loss` (float, 例如 0.1)
    - `daily_loss_limit` (float, 例如 0.05)
    - `max_leverage_total` (float, 例如 3.0)
  - 示例：
    ```bash
    curl -s -X POST http://localhost:8000/api/v1/risk/config \
      -H "Content-Type: application/json" \
      -d '{
        "max_total_capital_usage": 0.8,
        "max_correlation_threshold": 0.7,
        "max_sector_concentration": 0.4,
        "portfolio_stop_loss": 0.12,
        "daily_loss_limit": 0.05,
        "max_leverage_total": 3.0
      }' | jq
    ```


### 5) 绩效与日志（Performance & Logs）

- GET `/api/v1/performance/portfolio`
  - 返回投资组合层面的绩效指标（价值、PnL、收益率等）
  - 示例：
    ```bash
    curl -s http://localhost:8000/api/v1/performance/portfolio | jq
    ```

- GET `/api/v1/performance/strategy/{strategy_id}`
  - 返回指定策略的绩效快照
  - 示例：
    ```bash
    curl -s http://localhost:8000/api/v1/performance/strategy/trend_pool_demo | jq
    ```

- GET `/api/v1/logs/summary`
  - 返回 AI 决策/交易/风险的日度汇总（若可用）
  - 支持日期查询参数（例如 `?date=2025-11-06`）
  - 示例：
    ```bash
    curl -s "http://localhost:8000/api/v1/logs/summary?date=2025-11-06" | jq
    ```

- GET `/api/v1/logs/decisions`
  - 返回最近的 AI 决策日志（结构化 JSON），可按策略与数量过滤
  - 查询参数：`strategy_id`、`limit`
  - 示例：
    ```bash
    curl -s "http://localhost:8000/api/v1/logs/decisions?strategy_id=trend_pool_demo&limit=50" | jq
    ```


### 6) WebSocket（实时推送）

- WS `/ws`
  - 推送简单的事件/状态更新（若启用）
  - JavaScript 示例：
    ```js
    const ws = new WebSocket("ws://localhost:8000/ws");
    ws.onopen = () => console.log("connected");
    ws.onmessage = (evt) => console.log("message:", evt.data);
    ws.onclose = () => console.log("closed");
    ```


## “品种池（Commodity Pool）”策略说明

- `commodity_pool` 常见示例：
  - `"black"`（黑色系）: rb, hc, i, j, jm
  - `"metal"`（有色金属）: cu, al, zn, pb, ni, sn
  - `"precious_metal"`（贵金属）: au, ag
  - 其他：`"agriculture"`, `"chemical"`, `"financial"` 等
- 也可传入显式 `commodities` 数组（如 `["rb","i","j"]`）或 `symbols` 数组（如 `["rb","cu"]`）
- `selection_mode`:
  - `"ai_driven"`：AI 在提供的池/品种/合约范围内自主选择最优机会
  - `"manual"`：保留给外部择时/筛选逻辑
- `max_symbols`：单策略内 AI 可同时跟踪/操作的品种上限


## 常见问题（Troubleshooting）

- 404 “服务未初始化”：
  - 请确保完整系统已启动（Agent Manager / Database Manager 等全部就绪）
  - 建议使用 `uv run python run_cherryquant_complete.py` 启动
- 决策一直是 “hold”：
  - 确认 AI 可用（OPENAI_API_KEY）。
  - 没有 Key 时会使用模拟决策（Simulated Decision），多数情况下也会给出 buy/sell；若仍 hold，请检查 `confidence_threshold` 与实际 `confidence`。
- trades/positions 返回为空：
  - 需要几个决策周期（5m）后再观察
  - 查看 `logs/` 下日志或请求 `/api/v1/health` 确认系统就绪状态


## 环境变量（节选）

- 模型与 API
  - `OPENAI_MODEL`（例如 `gpt-4`）
  - `OPENAI_TIMEOUT`（默认 30）
  - `OPENAI_MAX_RETRIES`（默认 3）
  - `OPENAI_REQUESTS_PER_MINUTE`（默认 30）
- 数据模式
  - `DATA_MODE`（`dev|live`）
  - `DATA_SOURCE`（`tushare|simnow`）
  - `TUSHARE_TOKEN`（若使用 Tushare 数据源）
- 数据库
  - `POSTGRES_*` 与 `REDIS_*`（与 docker/docker-compose.yml 一致时可直接连接）


## 完整操作示例（Full Workflow）

1) 启动基础设施（Docker）：
```bash
docker compose -f docker/docker-compose.yml up -d
```

2) 启动应用：
```bash
uv sync --group dev
uv run pip install -e .
uv run python run_cherryquant_complete.py
```

3) 创建基于“品种池”的策略：
```bash
curl -s -X POST http://localhost:8000/api/v1/strategies \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_id": "trend_pool_demo",
    "strategy_name": "趋势-黑色系池",
    "commodity_pool": "black",
    "max_symbols": 3,
    "selection_mode": "ai_driven",
    "initial_capital": 100000,
    "max_position_size": 5,
    "max_positions": 2,
    "leverage": 3.0,
    "risk_per_trade": 0.02,
    "decision_interval": 300,
    "confidence_threshold": 0.6,
    "ai_model": "gpt-4",
    "ai_temperature": 0.1,
    "is_active": true,
    "manual_override": false
  }' | jq
```

4) 查看系统状态：
```bash
curl -s http://localhost:8000/api/v1/status | jq
curl -s http://localhost:8000/api/v1/strategies | jq
```

5) 等待数个决策周期后查看交易与持仓：
```bash
curl -s http://localhost:8000/api/v1/trades | jq
curl -s http://localhost:8000/api/v1/positions | jq
```

6) 更新风险配置（可选）：
```bash
curl -s -X POST http://localhost:8000/api/v1/risk/config \
  -H "Content-Type: application/json" \
  -d '{"portfolio_stop_loss": 0.12, "daily_loss_limit": 0.05}' | jq
```

7) 停止并移除策略：
```bash
curl -s -X POST http://localhost:8000/api/v1/strategies/trend_pool_demo/stop | jq
curl -s -X DELETE http://localhost:8000/api/v1/strategies/trend_pool_demo | jq
```

---

如需更详细的交互说明，请访问 Swagger UI（/docs）查看可用端点与请求/响应模型。