# CherryQuant Web API Usage Guide

This document shows how to interact with the CherryQuant Web API using `curl` and common HTTP tools. It includes pool-aware strategy creation (commodity pools) and practical examples for the most frequently used endpoints.

By default, the API is served by:
- Base URL: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Static dashboard: http://localhost:8000/ (if present)

To run the API, start the complete system:
- uv run python run_cherryquant_complete.py

Notes:
- Authentication: none (by default)
- CORS: enabled for all origins
- Content-Type: application/json (for POST bodies)
- JSON numbers are typically floats or integers where applicable


## Quick Start

Health check:
```bash
curl -s http://localhost:8000/api/v1/health | jq
```

System status:
```bash
curl -s http://localhost:8000/api/v1/status | jq
```

List strategies:
```bash
curl -s http://localhost:8000/api/v1/strategies | jq
```


## Endpoints

### 1) Health and Status

- GET /api/v1/health
  - Returns health information about the API process
  - Example:
    ```bash
    curl -s http://localhost:8000/api/v1/health | jq
    ```
    Response (example):
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

- GET /api/v1/status
  - Returns overall system and portfolio aggregate status
  - Example:
    ```bash
    curl -s http://localhost:8000/api/v1/status | jq
    ```


### 2) Strategy Management

- GET /api/v1/strategies
  - List current strategies and their high-level states
  - Example:
    ```bash
    curl -s http://localhost:8000/api/v1/strategies | jq
    ```

- GET /api/v1/strategies/{strategy_id}
  - Get detailed information for a single strategy
  - Example:
    ```bash
    curl -s http://localhost:8000/api/v1/strategies/trend_pool_demo | jq
    ```

- POST /api/v1/strategies (Create strategy, pool-aware)
  - Create a new strategy. You can supply:
    - symbols: explicit instrument list (e.g., ["rb", "cu"])
    - OR commodities: list of commodity codes (e.g., ["rb", "i", "j"])
    - OR commodity_pool: a named pool (e.g., "black", "metal", "all")
  - The engine can resolve commodity pool -> commodities -> dominant contracts when needed.

  Example (pool-aware, recommended):
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

  Example (explicit commodities list instead of a named pool):
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

  Example (explicit symbols list: you manage instruments directly):
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

- POST /api/v1/strategies/{strategy_id}/start
- POST /api/v1/strategies/{strategy_id}/stop
- POST /api/v1/strategies/{strategy_id}/pause
- POST /api/v1/strategies/{strategy_id}/resume
  - Update a strategy’s lifecycle
  - Example (start):
    ```bash
    curl -s -X POST http://localhost:8000/api/v1/strategies/trend_pool_demo/start | jq
    ```

- DELETE /api/v1/strategies/{strategy_id}
  - Remove a strategy (will also stop it if running)
  - Example:
    ```bash
    curl -s -X DELETE http://localhost:8000/api/v1/strategies/trend_pool_demo | jq
    ```


### 3) Trades and Positions

- GET /api/v1/trades
  - Query trade logs accumulated by agents
  - Example:
    ```bash
    curl -s http://localhost:8000/api/v1/trades | jq
    ```

- GET /api/v1/positions
  - Returns current held positions
  - Example:
    ```bash
    curl -s http://localhost:8000/api/v1/positions | jq
    ```


### 4) Risk Configuration and Monitoring

- GET /api/v1/risk/status
  - Returns current portfolio risk posture and key metrics
  - Example:
    ```bash
    curl -s http://localhost:8000/api/v1/risk/status | jq
    ```

- POST /api/v1/risk/config
  - Update risk parameters (portfolio-level)
  - Fields:
    - max_total_capital_usage (float e.g., 0.8)
    - max_correlation_threshold (float e.g., 0.7)
    - max_sector_concentration (float e.g., 0.4)
    - portfolio_stop_loss (float e.g., 0.1)
    - daily_loss_limit (float e.g., 0.05)
    - max_leverage_total (float e.g., 3.0)

  Example:
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


### 5) Performance and Logs

- GET /api/v1/performance/portfolio
  - Returns portfolio-level performance metrics (value, pnl, returns, etc.)
  - Example:
    ```bash
    curl -s http://localhost:8000/api/v1/performance/portfolio | jq
    ```

- GET /api/v1/performance/strategy/{strategy_id}
  - Returns a specific strategy’s performance snapshot
  - Example:
    ```bash
    curl -s http://localhost:8000/api/v1/performance/strategy/trend_pool_demo | jq
    ```

- GET /api/v1/logs/summary
  - Returns aggregated daily summary of AI decisions / trades / risks (if available)
  - Example:
    ```bash
    curl -s "http://localhost:8000/api/v1/logs/summary?date=2025-11-06" | jq
    ```

- GET /api/v1/logs/decisions
  - Returns recent AI decision logs (structured) with optional filters
  - Query params: strategy_id, limit (default example)
  - Example:
    ```bash
    curl -s "http://localhost:8000/api/v1/logs/decisions?strategy_id=trend_pool_demo&limit=50" | jq
    ```


### 6) WebSocket (Realtime)

- WS /ws
  - Broadcasts simple events/status updates to connected clients (if enabled)
  - Example (browser/Node.js):
    ```js
    const ws = new WebSocket("ws://localhost:8000/ws");
    ws.onopen = () => console.log("connected");
    ws.onmessage = (evt) => console.log("message:", evt.data);
    ws.onclose = () => console.log("closed");
    ```


## Pool-Aware Strategy Notes

- commodity_pool supports named categories like:
  - "black": rb, hc, i, j, jm
  - "metal": cu, al, zn, pb, ni, sn
  - "precious_metal": au, ag
  - "agriculture", "chemical", "financial", etc.
- You can also pass an explicit commodities list (e.g., ["rb","i","j"]) or explicit symbols ["rb","cu"].
- selection_mode:
  - "ai_driven": AI will choose the best opportunities within the provided pool/commodities/symbols
  - "manual": reserved for external orchestration (if you do your own selection)
- max_symbols: upper bound for how many symbols the strategy may act on concurrently/asynchronously.


## Common Troubleshooting

- 404 "服务未初始化":
  - Ensure the complete system has started the agent manager and database manager.
  - Use run_cherryquant_complete.py to boot the Web + Agents + Data integrations.

- Decisions always "hold":
  - Confirm the AI is reachable (OPENAI_API_KEY). If not set, the engine will simulate decisions, but still produce buy/sell in many cases.
  - Check confidence_threshold vs actual confidence in your strategy config.

- Empty lists (trades/positions):
  - The system may need a few decision cycles. Check logs under logs/ and the /api/v1/health status.


## Environment Variables (Selected)

- OPENAI_MODEL (e.g., "gpt-4")
- OPENAI_TIMEOUT (default 30)
- OPENAI_MAX_RETRIES (default 3)
- OPENAI_REQUESTS_PER_MINUTE (default 30)
- DATA_MODE (dev|live), DATA_SOURCE (tushare|simnow)
- TUSHARE_TOKEN (if using Tushare-based sources)
- POSTGRES_* and REDIS_* (match docker/docker-compose.yml if using Docker)


## Example: Full Workflow

1) Start infrastructure:
```bash
docker compose -f docker/docker-compose.yml up -d
```

2) Start the app:
```bash
uv sync --group dev
uv run pip install -e .
uv run python run_cherryquant_complete.py
```

3) Create a pool-aware strategy:
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

4) Check status:
```bash
curl -s http://localhost:8000/api/v1/status | jq
curl -s http://localhost:8000/api/v1/strategies | jq
```

5) Observe trades and positions (after a few cycles):
```bash
curl -s http://localhost:8000/api/v1/trades | jq
curl -s http://localhost:8000/api/v1/positions | jq
```

6) Update risk config (optional):
```bash
curl -s -X POST http://localhost:8000/api/v1/risk/config \
  -H "Content-Type: application/json" \
  -d '{"portfolio_stop_loss": 0.12, "daily_loss_limit": 0.05}' | jq
```

7) Stop/remove the strategy:
```bash
curl -s -X POST http://localhost:8000/api/v1/strategies/trend_pool_demo/stop | jq
curl -s -X DELETE http://localhost:8000/api/v1/strategies/trend_pool_demo | jq
```

---

For more details, use the interactive docs at /docs and explore available endpoints and request/response models.