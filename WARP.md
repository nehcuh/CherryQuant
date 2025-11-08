# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

Project: CherryQuant — AI-driven Chinese futures trading system built around vn.py, OpenAI LLM decisioning, multi-timeframe analytics, and a Postgres/Redis data stack.

What you’ll use most

- Setup (once per machine)
  - uv env + deps: uv sync --group dev
  - Example env: cp .env.example .env
  - Start data services: docker-compose -f docker/docker-compose.yml up -d

- Run the apps
  - Simulation mode (recommended): uv run python run_cherryquant.py simulation
  - Backtest mode (placeholder): uv run python run_cherryquant.py backtest
  - Live mode (not fully implemented): uv run python run_cherryquant.py live
  - Realtime recorder (vn.py CTP ticks→bars): see docs/VN_RECORDER.md
  - AI market selection demo: uv run python run_cherryquant_ai_selection.py


- Tests
  - All tests: uv run pytest tests -v
  - Single test file: uv run pytest tests/test_ai_engine.py -v
  - Single test case: uv run pytest tests/test_ai_engine.py::test_market_data_fetch -q
  - Coverage (if needed): uv run pytest --cov=cherryquant --cov-report=html

- Lint/format/type-check
  - Ruff check: uv run ruff check .
  - Ruff autofix: uv run ruff check . --fix
  - Black check: uv run black --check .
  - Black format: uv run black .
  - Type check (3rd-party stubs may be missing): uv run mypy . --ignore-missing-imports

- Database ops (Docker)
  - Up services: docker-compose -f docker/docker-compose.yml up -d
  - Status: docker-compose -f docker/docker-compose.yml ps
  - Logs (all): docker-compose -f docker/docker-compose.yml logs -f
  - psql shell: docker-compose -f docker/docker-compose.yml exec postgresql psql -U cherryquant -d cherryquant
  - Redis CLI: docker-compose -f docker/docker-compose.yml exec redis redis-cli
  - Down services: docker-compose -f docker/docker-compose.yml down

Important environment

- Core keys in .env
  - OPENAI_API_KEY, OPENAI_BASE_URL (optional; defaults to https://api.openai.com/v1)
  - DATA_SOURCE=tushare | simnow; set TUSHARE_TOKEN if using Tushare; for simnow also set SIMNOW_USERID and SIMNOW_PASSWORD
  - Postgres/Redis endpoints (match docker/docker-compose.yml) if you use the DB demos
- Notes
  - AI selection demo gracefully falls back to a simulated decision when no API key is present.
  - AKShare and OpenAI calls require network access; transient failures are handled with logs rather than hard asserts.

High-level architecture and flow

- Entry points and modes
  - run_cherryquant.py
    - Orchestrates modes: simulation, backtest, live
    - Sets up logging, data sources (Tushare by default; realtime via vn.py recorder), history caching, and an async simulation loop that pulls LLM decisions and simulates trades
  - run_cherryquant_ai_selection.py
    - Full-market scan and instrument selection demo using the AISelectionEngine


- AI decisioning
  - src/cherryquant/ai/decision_engine/futures_engine.py
    - FuturesDecisionEngine: fetches market data (AKShare), computes indicators (MA, RSI, MACD), builds prompts (src/cherryquant/ai/prompts/futures_prompts.py), and requests JSON decisions via src/cherryquant/ai/llm_client/openai_client.py
  - src/cherryquant/ai/decision_engine/ai_selection_engine.py
    - AISelectionEngine: market-wide scan using src/cherryquant/adapters/data_adapter/multi_symbol_manager.py, builds a comprehensive prompt (src/cherryquant/ai/prompts/ai_selection_prompts.py), validates and returns a structured selection + trade plan
  - src/cherryquant/ai/llm_client/openai_client.py
    - Thin wrapper around OpenAI Chat Completions; async facade provided; validates decision JSON

- Market data acquisition (outside vn.py)
  - src/cherryquant/adapters/data_adapter/
    - market_data_manager.py: pluggable sources; AKShare primary with optional SimNow/VnPy placeholders; automatic primary/fallback
    - multi_symbol_manager.py: breadth scans of SHFE/DCE/CZCE/CFFEX with per-symbol metrics; caches recent snapshots
    - history_data_manager.py: simple local SQLite cache for historical bars with standardization

- Multi-timeframe analytics (LLM-friendly)
  - src/cherryquant/adapters/data_storage/timeframe_data_manager.py
    - TimeFrameDataManager: produces OHLCV series across monthly→minute, computes indicators, derives summaries (trend/momentum/volatility/risk), and assembles AI-optimized payloads; in demo, uses generated sample series

- Data persistence and caching
  - src/cherryquant/adapters/data_storage/database_manager.py + config/database_config.py
    - Unified async manager for Postgres (TimescaleDB) and Redis
    - CRUD for market_data, technical_indicators, ai_decisions; Redis-backed read-through caching
    - docker/sql/init.sql provisions hypertables, indexes, materialized views, and policies

- Strategy integration (vn.py)
  - src/cherryquant/cherry_quant_strategy.py
    - CtaTemplate strategy wiring LLM decisions to trading actions (buy_to_enter/sell_to_enter/close/hold), basic risk gates and stop/target placeholders
    - Current simulation path in run_cherryquant.py demonstrates decision→execution loop without live gateway

- Configuration
  - config/settings/settings.py: trading parameters, AI thresholds, risk limits, contract metadata
  - config/database_config.py: Postgres/Redis endpoints, retention and source update cadence

Practical tips for this repo

- Use simulation mode first; it verifies OpenAI connectivity and runs an async loop without broker connectivity

- Tests are light and network-sensitive; install dev deps with uv sync --group dev
- Logging goes to logs/ and stdout; increase detail by tweaking LOGGING_CONFIG in config/settings/settings.py
