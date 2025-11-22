"""Application bootstrap and dependency wiring for CherryQuant.

This module centralizes construction of core runtime dependencies:
- CherryQuantConfig (Pydantic settings loaded from env)
- MongoDBConnectionManager (via MongoDBConnectionPool)
- Redis async client
- DatabaseManager (MongoDB + Redis facade)

By keeping this wiring in one place (the "composition root"), we avoid
spreading configuration and environment access across adapters, which makes
this project cleaner as a Python architecture example.
"""

from __future__ import annotations

from dataclasses import dataclass

import redis.asyncio as aioredis

from config.settings.base import CherryQuantConfig
from cherryquant.adapters.data_storage.mongodb_manager import MongoDBConnectionPool
from cherryquant.adapters.data_storage.database_manager import DatabaseManager
from cherryquant.ai.llm_client.openai_client import AsyncOpenAIClient
from cherryquant.logging_config import configure_logging


@dataclass
class AppContext:
    """Runtime application context.

    Attributes:
        config:   Loaded CherryQuant configuration (Pydantic BaseSettings).
        db:       DatabaseManager instance (MongoDB + Redis facade).
        ai_client:Shared AsyncOpenAIClient instance for all AI engines.
    """

    config: CherryQuantConfig
    db: DatabaseManager
    ai_client: AsyncOpenAIClient

    async def close(self) -> None:
        """Gracefully close underlying connections (MongoDB, Redis, LLM client, etc.)."""
        await self.db.close()
        try:
            await self.ai_client.aclose()
        except Exception:
            pass


async def create_app_context(config: CherryQuantConfig | None = None) -> AppContext:
    """Create the application context from the given config (or env).

    This function is the main entry point for wiring dependencies in
    scripts like `run_cherryquant.py`, `run_cherryquant_multi_agent.py`,
    and `run_cherryquant_ai_selection.py`.
    """
    # 1. Load configuration (single source of truth)
    if config is None:
        config = CherryQuantConfig.from_env()

    # 2. Configure structured logging based on config
    configure_logging(
        log_level=config.logging.level,
        json_logs=config.logging.json_logs,
        enable_colors=config.logging.enable_colors,
    )

    db_cfg = config.database

    # 3. Initialize MongoDB connection manager via the connection pool
    mongodb_manager = await MongoDBConnectionPool.get_manager(
        uri=db_cfg.mongodb_uri,
        database=db_cfg.mongodb_database,
        min_pool_size=db_cfg.mongodb_min_pool_size,
        max_pool_size=db_cfg.mongodb_max_pool_size,
        username=db_cfg.mongodb_username,
        password=db_cfg.mongodb_password,
    )

    # 4. Initialize Redis client
    redis_url = f"redis://{db_cfg.redis_host}:{db_cfg.redis_port}"
    if db_cfg.redis_password:
        redis_url = f"redis://:{db_cfg.redis_password}@{db_cfg.redis_host}:{db_cfg.redis_port}"

    redis_client = aioredis.from_url(
        redis_url,
        db=db_cfg.redis_db,
        decode_responses=True,
    )

    # 5. Build DatabaseManager with explicit dependencies
    db_manager = DatabaseManager(
        mongodb_manager=mongodb_manager,
        redis_client=redis_client,
        cache_ttl=db_cfg.cache_ttl,
        cache_prefix="cherryquant:",
    )

    # 6. Initialize shared AsyncOpenAIClient from AIConfig
    ai_client = AsyncOpenAIClient(config.ai)

    return AppContext(config=config, db=db_manager, ai_client=ai_client)
