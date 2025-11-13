"""
CherryQuant 数据库管理器
整合PostgreSQL (TimescaleDB) 和 Redis 的多数据库架构
使用连接池和事务管理
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Protocol
import json
import pandas as pd
import numpy as np
from contextlib import asynccontextmanager
from dataclasses import dataclass

# 数据库连接库
import asyncpg
import redis.asyncio as aioredis
import aiofiles

from .timeframe_data_manager import TimeFrame, MarketDataPoint, TechnicalIndicators

logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    """数据库配置"""
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "cherryquant"
    postgres_user: str = "cherryquant"
    postgres_password: str = "cherryquant123"
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    cache_ttl: int = 300  # 5分钟
    connection_pool_min: int = 2
    connection_pool_max: int = 10
    command_timeout: int = 60


class DatabaseManager:
    """CherryQuant数据库管理器"""

    def __init__(self, config: DatabaseConfig):
        """
        初始化数据库管理器

        Args:
            config: 数据库配置
        """
        self.config = config
        self.postgres_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[aioredis.Redis] = None

        # 缓存配置
        self.cache_ttl = config.cache_ttl
        self.cache_prefix = "cherryquant:"

    async def initialize(self):
        """初始化所有数据库连接"""
        try:
            await self._connect_postgresql()
            await self._connect_redis()
            logger.info("✅ 数据库连接初始化完成")
        except Exception as e:
            logger.error(f"❌ 数据库初始化失败: {e}")
            await self.close()
            raise

    async def _ensure_postgres_pool(self):
        """确保连接池可用，必要时重建"""
        try:
            if self.postgres_pool is None or getattr(self.postgres_pool, "_closed", False):
                await self._connect_postgresql()
        except Exception as e:
            logger.error(f"重建PostgreSQL连接池失败: {e}")
            raise

    async def _connect_postgresql(self):
        """连接PostgreSQL数据库"""
        try:
            self.postgres_pool = await asyncpg.create_pool(
                host=self.config.postgres_host,
                port=self.config.postgres_port,
                database=self.config.postgres_db,
                user=self.config.postgres_user,
                password=self.config.postgres_password,
                min_size=self.config.connection_pool_min,
                max_size=self.config.connection_pool_max,
                command_timeout=self.config.command_timeout
            )
            logger.info("✅ PostgreSQL连接成功")
        except Exception as e:
            logger.error(f"❌ PostgreSQL连接失败: {e}")
            raise

    async def _connect_redis(self):
        """连接Redis缓存"""
        try:
            # redis.asyncio.from_url 返回同步对象，不需要 await
            self.redis_client = aioredis.from_url(
                f"redis://{self.config.redis_host}:{self.config.redis_port}",
                db=self.config.redis_db,
                decode_responses=True
            )
            logger.info("✅ Redis连接成功")
        except Exception as e:
            logger.error(f"❌ Redis连接失败: {e}")
            raise

    # ==================== 市场数据管理 ====================

    async def store_market_data(
        self,
        symbol: str,
        exchange: str,
        timeframe: TimeFrame,
        data_points: List[MarketDataPoint]
    ) -> bool:
        """
        存储市场数据到PostgreSQL

        Args:
            symbol: 合约代码
            exchange: 交易所
            timeframe: 时间周期
            data_points: 数据点列表

        Returns:
            是否成功
        """
        if not data_points:
            return True

        try:
            await self._ensure_postgres_pool()
            async with self.postgres_pool.acquire() as conn:
                # 使用 executemany 简化批量写入并避免占位符重复
                sql = """
                INSERT INTO market_data (
                    time, symbol, exchange, timeframe,
                    open_price, high_price, low_price, close_price,
                    volume, open_interest, turnover
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                ON CONFLICT (time, symbol, exchange, timeframe) DO UPDATE SET
                    open_price = EXCLUDED.open_price,
                    high_price = EXCLUDED.high_price,
                    low_price = EXCLUDED.low_price,
                    close_price = EXCLUDED.close_price,
                    volume = EXCLUDED.volume,
                    open_interest = EXCLUDED.open_interest,
                    turnover = EXCLUDED.turnover
                """
                rows = [
                    (
                        point.timestamp,
                        symbol,
                        exchange,
                        timeframe.value,
                        point.open,
                        point.high,
                        point.low,
                        point.close,
                        point.volume,
                        point.open_interest,
                        point.turnover,
                    )
                    for point in data_points
                ]
                await conn.executemany(sql, rows)

            # 更新缓存
            cache_key = f"{self.cache_prefix}market_data:{symbol}:{exchange}:{timeframe.value}"
            await self._set_cache(cache_key, [point.__dict__ for point in data_points], self.cache_ttl)

            logger.info(f"存储市场数据: {symbol}.{exchange} {timeframe.value} {len(data_points)}条")
            return True

        except Exception as e:
            msg = str(e).lower()
            logger.error(f"存储市场数据失败: {e}")
            # 连接关闭或事件循环问题时尝试一次重连后重试
            if any(x in msg for x in ["connection was closed", "event loop is closed", "pool is closed", "closed"]):
                try:
                    await self._connect_postgresql()
                    async with self.postgres_pool.acquire() as conn:
                        sql = """
                INSERT INTO market_data (
                    time, symbol, exchange, timeframe,
                    open_price, high_price, low_price, close_price,
                    volume, open_interest, turnover
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                ON CONFLICT (time, symbol, exchange, timeframe) DO UPDATE SET
                    open_price = EXCLUDED.open_price,
                    high_price = EXCLUDED.high_price,
                    low_price = EXCLUDED.low_price,
                    close_price = EXCLUDED.close_price,
                    volume = EXCLUDED.volume,
                    open_interest = EXCLUDED.open_interest,
                    turnover = EXCLUDED.turnover
                """
                        rows = [
                            (
                                point.timestamp,
                                symbol,
                                exchange,
                                timeframe.value,
                                point.open,
                                point.high,
                                point.low,
                                point.close,
                                point.volume,
                                point.open_interest,
                                point.turnover,
                            )
                            for point in data_points
                        ]
                        await conn.executemany(sql, rows)
                    return True
                except Exception:
                    return False
            return False

    async def get_market_data(
        self,
        symbol: str,
        exchange: str,
        timeframe: TimeFrame,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[MarketDataPoint]:
        """
        获取市场数据

        Args:
            symbol: 合约代码
            exchange: 交易所
            timeframe: 时间周期
            start_time: 开始时间
            end_time: 结束时间
            limit: 数据条数限制

        Returns:
            市场数据点列表
        """
        try:
            # 先尝试从缓存获取
            cache_key = f"{self.cache_prefix}market_data:{symbol}:{exchange}:{timeframe.value}"
            cached_data = await self._get_cache(cache_key)
            if cached_data:
                logger.debug(f"从缓存获取市场数据: {symbol}.{exchange} {timeframe.value}")
                return [MarketDataPoint(**point) for point in cached_data]

            # 从数据库查询（带一次重试）
            await self._ensure_postgres_pool()
            async def _fetch_once():
                async with self.postgres_pool.acquire() as conn:
                    where_conditions = [
                        "symbol = $1",
                        "exchange = $2",
                        "timeframe = $3"
                    ]
                    params = [symbol, exchange, timeframe.value]
                    param_index = 4
                    
                    if start_time:
                        where_conditions.append(f"time >= ${param_index}")
                        params.append(start_time)
                        param_index += 1
                    if end_time:
                        where_conditions.append(f"time <= ${param_index}")
                        params.append(end_time)
                        param_index += 1
                    
                    where_clause = " AND ".join(where_conditions)
                    sql = f"""
                    SELECT time, open_price, high_price, low_price, close_price,
                           volume, open_interest, turnover
                    FROM market_data
                    WHERE {where_clause}
                    ORDER BY time DESC
                    """
                    
                    if limit:
                        sql += f" LIMIT ${param_index}"
                        params.append(limit)
                        param_index += 1
                        
                    return await conn.fetch(sql, *params)

            rows = None
            try:
                rows = await _fetch_once()
            except Exception as e1:
                if "another operation is in progress" in str(e1).lower() or "closed" in str(e1).lower():
                    logger.warning(f"查询重试: {e1}")
                    await asyncio.sleep(0.3)
                    await self._connect_postgresql()
                    rows = await _fetch_once()
                else:
                    raise

            data_points = []
            for row in rows:
                point = MarketDataPoint(
                    timestamp=row['time'],
                    open=row['open_price'],
                    high=row['high_price'],
                    low=row['low_price'],
                    close=row['close_price'],
                    volume=row['volume'],
                    open_interest=row['open_interest'],
                    turnover=row['turnover']
                )
                data_points.append(point)

            # 缓存结果
            await self._set_cache(cache_key, [point.__dict__ for point in data_points], self.cache_ttl)

            logger.info(f"从数据库获取市场数据: {symbol}.{exchange} {timeframe.value} {len(data_points)}条")
            return data_points

        except Exception as e:
            logger.error(f"获取市场数据失败: {e}")
            return []

    async def store_technical_indicators(
        self,
        symbol: str,
        exchange: str,
        timeframe: TimeFrame,
        indicators: List[TechnicalIndicators]
    ) -> bool:
        """
        存储技术指标

        Args:
            symbol: 合约代码
            exchange: 交易所
            timeframe: 时间周期
            indicators: 技术指标列表

        Returns:
            是否成功
        """
        if not indicators:
            return True

        try:
            await self._ensure_postgres_pool()
            async with self.postgres_pool.acquire() as conn:
                # 使用 executemany 简化批量写入
                sql = """
                INSERT INTO technical_indicators (
                    time, symbol, exchange, timeframe,
                    ma5, ma10, ma20, ma60, ema12, ema26,
                    macd, macd_signal, macd_histogram,
                    kdj_k, kdj_d, kdj_j, rsi,
                    bb_upper, bb_middle, bb_lower,
                    atr, cci, williams_r
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23)
                ON CONFLICT (time, symbol, exchange, timeframe) DO UPDATE SET
                    ma5 = EXCLUDED.ma5,
                    ma10 = EXCLUDED.ma10,
                    ma20 = EXCLUDED.ma20,
                    ma60 = EXCLUDED.ma60,
                    ema12 = EXCLUDED.ema12,
                    ema26 = EXCLUDED.ema26,
                    macd = EXCLUDED.macd,
                    macd_signal = EXCLUDED.macd_signal,
                    macd_histogram = EXCLUDED.macd_histogram,
                    kdj_k = EXCLUDED.kdj_k,
                    kdj_d = EXCLUDED.kdj_d,
                    kdj_j = EXCLUDED.kdj_j,
                    rsi = EXCLUDED.rsi,
                    bb_upper = EXCLUDED.bb_upper,
                    bb_middle = EXCLUDED.bb_middle,
                    bb_lower = EXCLUDED.bb_lower,
                    atr = EXCLUDED.atr,
                    cci = EXCLUDED.cci,
                    williams_r = EXCLUDED.williams_r
                """
                rows = [
                    (
                        indicator.timestamp,
                        symbol,
                        exchange,
                        timeframe.value,
                        indicator.ma5,
                        indicator.ma10,
                        indicator.ma20,
                        indicator.ma60,
                        indicator.ema12,
                        indicator.ema26,
                        indicator.macd,
                        indicator.macd_signal,
                        indicator.macd_histogram,
                        indicator.kdj_k,
                        indicator.kdj_d,
                        indicator.kdj_j,
                        indicator.rsi,
                        indicator.bb_upper,
                        indicator.bb_middle,
                        indicator.bb_lower,
                        indicator.atr,
                        indicator.cci,
                        indicator.williams_r,
                    )
                    for indicator in indicators
                ]
                await conn.executemany(sql, rows)

            # 更新缓存
            cache_key = f"{self.cache_prefix}indicators:{symbol}:{exchange}:{timeframe.value}"
            await self._set_cache(cache_key, [ind.__dict__ for ind in indicators], self.cache_ttl)

            logger.info(f"存储技术指标: {symbol}.{exchange} {timeframe.value} {len(indicators)}条")
            return True

        except Exception as e:
            msg = str(e).lower()
            logger.error(f"存储技术指标失败: {e}")
            if any(x in msg for x in ["connection was closed", "event loop is closed", "pool is closed", "closed"]):
                try:
                    await self._connect_postgresql()
                    async with self.postgres_pool.acquire() as conn:
                        sql = """
                INSERT INTO technical_indicators (
                    time, symbol, exchange, timeframe,
                    ma5, ma10, ma20, ma60, ema12, ema26,
                    macd, macd_signal, macd_histogram,
                    kdj_k, kdj_d, kdj_j, rsi,
                    bb_upper, bb_middle, bb_lower,
                    atr, cci, williams_r
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23)
                ON CONFLICT (time, symbol, exchange, timeframe) DO UPDATE SET
                    ma5 = EXCLUDED.ma5,
                    ma10 = EXCLUDED.ma10,
                    ma20 = EXCLUDED.ma20,
                    ma60 = EXCLUDED.ma60,
                    ema12 = EXCLUDED.ema12,
                    ema26 = EXCLUDED.ema26,
                    macd = EXCLUDED.macd,
                    macd_signal = EXCLUDED.macd_signal,
                    macd_histogram = EXCLUDED.macd_histogram,
                    kdj_k = EXCLUDED.kdj_k,
                    kdj_d = EXCLUDED.kdj_d,
                    kdj_j = EXCLUDED.kdj_j,
                    rsi = EXCLUDED.rsi,
                    bb_upper = EXCLUDED.bb_upper,
                    bb_middle = EXCLUDED.bb_middle,
                    bb_lower = EXCLUDED.bb_lower,
                    atr = EXCLUDED.atr,
                    cci = EXCLUDED.cci,
                    williams_r = EXCLUDED.williams_r
                """
                        rows = [
                            (
                                indicator.timestamp,
                                symbol,
                                exchange,
                                timeframe.value,
                                indicator.ma5,
                                indicator.ma10,
                                indicator.ma20,
                                indicator.ma60,
                                indicator.ema12,
                                indicator.ema26,
                                indicator.macd,
                                indicator.macd_signal,
                                indicator.macd_histogram,
                                indicator.kdj_k,
                                indicator.kdj_d,
                                indicator.kdj_j,
                                indicator.rsi,
                                indicator.bb_upper,
                                indicator.bb_middle,
                                indicator.bb_lower,
                                indicator.atr,
                                indicator.cci,
                                indicator.williams_r,
                            )
                            for indicator in indicators
                        ]
                        await conn.executemany(sql, rows)
                    return True
                except Exception:
                    return False
            return False

    async def get_technical_indicators(
        self,
        symbol: str,
        exchange: str,
        timeframe: TimeFrame,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[TechnicalIndicators]:
        """
        获取技术指标

        Args:
            symbol: 合约代码
            exchange: 交易所
            timeframe: 时间周期
            start_time: 开始时间
            end_time: 结束时间
            limit: 数据条数限制

        Returns:
            技术指标列表
        """
        try:
            # 先尝试从缓存获取
            cache_key = f"{self.cache_prefix}indicators:{symbol}:{exchange}:{timeframe.value}"
            cached_data = await self._get_cache(cache_key)
            if cached_data:
                logger.debug(f"从缓存获取技术指标: {symbol}.{exchange} {timeframe.value}")
                return [TechnicalIndicators(**ind) for ind in cached_data]

            # 从数据库查询
            async with self.postgres_pool.acquire() as conn:
                where_conditions = [
                    "symbol = $1",
                    "exchange = $2",
                    "timeframe = $3"
                ]
                params = [symbol, exchange, timeframe.value]
                param_index = 4

                if start_time:
                    where_conditions.append(f"time >= ${param_index}")
                    params.append(start_time)
                    param_index += 1
                if end_time:
                    where_conditions.append(f"time <= ${param_index}")
                    params.append(end_time)
                    param_index += 1

                where_clause = " AND ".join(where_conditions)

                sql = f"""
                SELECT time, ma5, ma10, ma20, ma60, ema12, ema26,
                       macd, macd_signal, macd_histogram,
                       kdj_k, kdj_d, kdj_j, rsi,
                       bb_upper, bb_middle, bb_lower,
                       atr, cci, williams_r
                FROM technical_indicators
                WHERE {where_clause}
                ORDER BY time DESC
                """

                if limit:
                    sql += f" LIMIT ${param_index}"
                    params.append(limit)
                    param_index += 1

                rows = await conn.fetch(sql, *params)

                indicators = []
                for row in rows:
                    indicator = TechnicalIndicators(
                        timestamp=row['time'],
                        ma5=row['ma5'],
                        ma10=row['ma10'],
                        ma20=row['ma20'],
                        ma60=row['ma60'],
                        ema12=row['ema12'],
                        ema26=row['ema26'],
                        macd=row['macd'],
                        macd_signal=row['macd_signal'],
                        macd_histogram=row['macd_histogram'],
                        kdj_k=row['kdj_k'],
                        kdj_d=row['kdj_d'],
                        kdj_j=row['kdj_j'],
                        rsi=row['rsi'],
                        bb_upper=row['bb_upper'],
                        bb_middle=row['bb_middle'],
                        bb_lower=row['bb_lower'],
                        atr=row['atr'],
                        cci=row['cci'],
                        williams_r=row['williams_r']
                    )
                    indicators.append(indicator)

                # 缓存结果
                await self._set_cache(cache_key, [ind.__dict__ for ind in indicators], self.cache_ttl)

                logger.info(f"从数据库获取技术指标: {symbol}.{exchange} {timeframe.value} {len(indicators)}条")
                return indicators

        except Exception as e:
            logger.error(f"获取技术指标失败: {e}")
            return []

    # ==================== AI决策管理 ====================

    async def store_ai_decision(self, decision: Dict[str, Any]) -> bool:
        """
        存储AI决策

        Args:
            decision: AI决策数据

        Returns:
            是否成功
        """
        try:
            await self._ensure_postgres_pool()
            async with self.postgres_pool.acquire() as conn:
                sql = """
                INSERT INTO ai_decisions (
                    decision_time, symbol, exchange, action, quantity, leverage,
                    entry_price, profit_target, stop_loss, confidence,
                    opportunity_score, selection_rationale, technical_analysis,
                    risk_factors, market_regime, volatility_index, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                RETURNING id
                """

                decision_id = await conn.fetchval(sql,
                    decision['decision_time'],
                    decision['symbol'],
                    decision['exchange'],
                    decision['action'],
                    decision['quantity'],
                    decision['leverage'],
                    decision['entry_price'],
                    decision['profit_target'],
                    decision['stop_loss'],
                    decision['confidence'],
                    decision['opportunity_score'],
                    decision['selection_rationale'],
                    decision['technical_analysis'],
                    decision['risk_factors'],
                    decision['market_regime'],
                    decision['volatility_index'],
                    decision['status']
                )

                decision['id'] = decision_id

            # 缓存最新决策
            cache_key = f"{self.cache_prefix}latest_decision:{decision['symbol']}"
            await self._set_cache(cache_key, decision, self.cache_ttl * 2)  # 决策缓存更久

            logger.info(f"存储AI决策: {decision['symbol']} {decision['action']} ID:{decision_id}")
            return True

        except Exception as e:
            msg = str(e).lower()
            logger.error(f"存储AI决策失败: {e}")
            if any(x in msg for x in ["connection was closed", "event loop is closed", "pool is closed", "closed"]):
                try:
                    await self._connect_postgresql()
                    async with self.postgres_pool.acquire() as conn:
                        sql = """
                INSERT INTO ai_decisions (
                    decision_time, symbol, exchange, action, quantity, leverage,
                    entry_price, profit_target, stop_loss, confidence,
                    opportunity_score, selection_rationale, technical_analysis,
                    risk_factors, market_regime, volatility_index, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                RETURNING id
                """
                        decision_id = await conn.fetchval(sql,
                            decision['decision_time'],
                            decision['symbol'],
                            decision['exchange'],
                            decision['action'],
                            decision['quantity'],
                            decision['leverage'],
                            decision['entry_price'],
                            decision['profit_target'],
                            decision['stop_loss'],
                            decision['confidence'],
                            decision['opportunity_score'],
                            decision['selection_rationale'],
                            decision['technical_analysis'],
                            decision['risk_factors'],
                            decision['market_regime'],
                            decision['volatility_index'],
                            decision['status']
                        )
                        decision['id'] = decision_id
                    return True
                except Exception:
                    return False
            return False

    async def get_ai_decisions(
        self,
        symbol: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        获取AI决策记录

        Args:
            symbol: 合约代码（可选）
            limit: 数据条数

        Returns:
            AI决策列表
        """
        try:
            async with self.postgres_pool.acquire() as conn:
                if symbol:
                    sql = """
                    SELECT * FROM ai_decisions
                    WHERE symbol = $1
                    ORDER BY decision_time DESC
                    LIMIT $2
                    """
                    rows = await conn.fetch(sql, symbol, limit)
                else:
                    sql = """
                    SELECT * FROM ai_decisions
                    ORDER BY decision_time DESC
                    LIMIT $1
                    """
                    rows = await conn.fetch(sql, limit)

                decisions = []
                for row in rows:
                    decision = dict(row)
                    decisions.append(decision)

                return decisions

        except Exception as e:
            logger.error(f"获取AI决策失败: {e}")
            return []

    # ==================== 交易与决策更新 ====================

    async def update_ai_decision_status(
        self,
        decision_id: int,
        status: str,
        executed_at: Optional[datetime] = None,
        execution_price: Optional[float] = None,
    ) -> bool:
        """更新AI决策状态与执行信息"""
        try:
            await self._ensure_postgres_pool()
            async with self.postgres_pool.acquire() as conn:
                sql = """
                UPDATE ai_decisions
                SET status = $1,
                    executed_at = COALESCE($2, executed_at),
                    execution_price = COALESCE($3, execution_price)
                WHERE id = $4
                """
                await conn.execute(sql, status, executed_at, execution_price, decision_id)
            return True
        except Exception as e:
            logger.error(f"更新AI决策状态失败: {e}")
            return False

    async def create_trade_entry(self, trade: Dict[str, Any]) -> Optional[int]:
        """创建交易记录（开仓）"""
        try:
            await self._ensure_postgres_pool()
            async with self.postgres_pool.acquire() as conn:
                sql = """
                INSERT INTO trades (
                    symbol, exchange, direction, quantity,
                    entry_price, entry_time,
                    entry_fee, ai_decision_id
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                RETURNING id
                """
                trade_id = await conn.fetchval(
                    sql,
                    trade.get("symbol"),
                    trade.get("exchange"),
                    trade.get("direction"),
                    trade.get("quantity", 0),
                    trade.get("entry_price", 0.0),
                    trade.get("entry_time", datetime.now()),
                    trade.get("entry_fee", 0.0),
                    trade.get("ai_decision_id")
                )
                return trade_id
        except Exception as e:
            logger.error(f"创建交易记录失败: {e}")
            return None

    async def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        exit_time: Optional[datetime] = None,
        exit_fee: float = 0.0,
        gross_pnl: Optional[float] = None,
        net_pnl: Optional[float] = None,
        pnl_percentage: Optional[float] = None,
    ) -> bool:
        """平仓交易，更新交易记录"""
        try:
            await self._ensure_postgres_pool()
            async with self.postgres_pool.acquire() as conn:
                sql = """
                UPDATE trades
                SET exit_price = $1,
                    exit_time = $2,
                    exit_fee = $3,
                    gross_pnl = COALESCE($4, gross_pnl),
                    net_pnl = COALESCE($5, net_pnl),
                    pnl_percentage = COALESCE($6, pnl_percentage)
                WHERE id = $7
                """
                await conn.execute(
                    sql,
                    exit_price,
                    exit_time or datetime.now(),
                    exit_fee,
                    gross_pnl,
                    net_pnl,
                    pnl_percentage,
                    trade_id,
                )
                return True
        except Exception as e:
            logger.error(f"平仓更新失败: {e}")
            return False

    # ==================== 缓存管理 ====================

    async def _get_cache(self, key: str) -> Optional[List[Dict]]:
        """获取缓存数据"""
        try:
            if not self.redis_client:
                return None

            cached_data = await self.redis_client.get(key)
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            logger.debug(f"获取缓存失败: {e}")
            return None

    async def _set_cache(self, key: str, data: Any, ttl: int):
        """设置缓存数据"""
        try:
            if not self.redis_client:
                return

            serialized_data = json.dumps(data, default=str)
            await self.redis_client.setex(key, ttl, serialized_data)
        except Exception as e:
            logger.debug(f"设置缓存失败: {e}")

    async def clear_cache(self, pattern: str = None):
        """
        清空缓存

        Args:
            pattern: 缓存键模式（可选）
        """
        try:
            if not self.redis_client:
                return

            if pattern:
                keys = await self.redis_client.keys(f"{self.cache_prefix}{pattern}*")
                if keys:
                    await self.redis_client.delete(*keys)
                    logger.info(f"清理缓存: {len(keys)}个键")
            else:
                keys = await self.redis_client.keys(f"{self.cache_prefix}*")
                if keys:
                    await self.redis_client.delete(*keys)
                    logger.info(f"清理所有缓存: {len(keys)}个键")

        except Exception as e:
            logger.error(f"清理缓存失败: {e}")

    # ==================== 数据统计和管理 ====================

    async def get_data_statistics(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        try:
            await self._ensure_postgres_pool()
            async with self.postgres_pool.acquire() as conn:
                # 获取市场数据统计
                market_stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_records,
                    COUNT(DISTINCT symbol) as unique_symbols,
                    COUNT(DISTINCT exchange) as unique_exchanges,
                    COUNT(DISTINCT timeframe) as unique_timeframes,
                    MIN(time) as earliest_time,
                    MAX(time) as latest_time
                FROM market_data
                """)

                # 获取AI决策统计
                decision_stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_decisions,
                    COUNT(DISTINCT symbol) as unique_symbols,
                    COUNT(CASE WHEN status = 'executed' THEN 1 END) as executed_decisions,
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_decisions,
                    AVG(confidence) as avg_confidence
                FROM ai_decisions
                """)

                # 获取交易记录统计
                trade_stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_trades,
                    COUNT(CASE WHEN direction = 'long' THEN 1 END) as long_trades,
                    COUNT(CASE WHEN direction = 'short' THEN 1 END) as short_trades,
                    SUM(net_pnl) as total_pnl,
                    AVG(net_pnl) as avg_pnl
                FROM trades
                WHERE exit_price IS NOT NULL
                """)

                return {
                    "market_data": dict(market_stats) if market_stats else {},
                    "ai_decisions": dict(decision_stats) if decision_stats else {},
                    "trades": dict(trade_stats) if trade_stats else {},
                    "cache_info": await self._get_cache_info()
                }

        except Exception as e:
            logger.error(f"获取数据库统计失败: {e}")
            return {}

    async def _get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        try:
            if not self.redis_client:
                return {"status": "disconnected"}

            info = await self.redis_client.info()
            keys_count = await self.redis_client.dbsize()

            return {
                "status": "connected",
                "used_memory": info.get('used_memory_human', 'N/A'),
                "connected_clients": info.get('connected_clients', 0),
                "total_keys": keys_count,
                "cache_prefix": self.cache_prefix
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ==================== 代理管理 ====================

    async def record_trade(self, trade_data: Dict[str, Any]) -> bool:
        """
        记录交易数据

        Args:
            trade_data: 交易数据字典

        Returns:
            是否成功
        """
        try:
            async with self.postgres_pool.acquire() as conn:
                sql = """
                INSERT INTO strategy_trades (
                    trade_id, strategy_id, symbol, direction, order_type,
                    quantity, price, timestamp, commission, pnl, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """
                await conn.execute(
                    sql,
                    trade_data.get('trade_id'),
                    trade_data.get('strategy_id'),
                    trade_data.get('symbol'),
                    trade_data.get('direction'),
                    trade_data.get('order_type'),
                    trade_data.get('quantity'),
                    trade_data.get('price'),
                    trade_data.get('timestamp'),
                    trade_data.get('commission'),
                    trade_data.get('pnl'),
                    trade_data.get('status')
                )

            logger.info(f"记录交易: {trade_data.get('strategy_id')} {trade_data.get('symbol')} {trade_data.get('direction')}")
            return True

        except Exception as e:
            logger.error(f"记录交易失败: {e}")
            return False

    async def record_portfolio_status(self, portfolio_data: Dict[str, Any]) -> bool:
        """
        记录组合状态

        Args:
            portfolio_data: 组合状态数据

        Returns:
            是否成功
        """
        try:
            async with self.postgres_pool.acquire() as conn:
                sql = """
                INSERT INTO portfolio_status (
                    timestamp, portfolio_value, total_pnl, daily_pnl,
                    total_trades, active_strategies, total_strategies,
                    capital_usage, sector_concentration
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """
                await conn.execute(
                    sql,
                    portfolio_data.get('timestamp'),
                    portfolio_data.get('portfolio_value'),
                    portfolio_data.get('total_pnl'),
                    portfolio_data.get('daily_pnl'),
                    portfolio_data.get('total_trades'),
                    portfolio_data.get('active_strategies'),
                    portfolio_data.get('total_strategies'),
                    portfolio_data.get('capital_usage'),
                    portfolio_data.get('sector_concentration')
                )

            return True

        except Exception as e:
            logger.error(f"记录组合状态失败: {e}")
            return False

    async def record_strategy_performance(self, strategy_id: str, performance_data: Dict[str, Any]) -> bool:
        """
        记录策略性能数据

        Args:
            strategy_id: 策略ID
            performance_data: 性能数据

        Returns:
            是否成功
        """
        try:
            async with self.postgres_pool.acquire() as conn:
                sql = """
                INSERT INTO strategy_performance (
                    timestamp, strategy_id, account_value, cash_available,
                    positions_count, total_trades, win_rate, total_pnl,
                    max_drawdown, return_pct, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """
                await conn.execute(
                    sql,
                    datetime.now(),
                    strategy_id,
                    performance_data.get('account_value'),
                    performance_data.get('cash_available'),
                    performance_data.get('positions_count'),
                    performance_data.get('total_trades'),
                    performance_data.get('win_rate'),
                    performance_data.get('total_pnl'),
                    performance_data.get('max_drawdown'),
                    performance_data.get('return_pct'),
                    performance_data.get('status')
                )

            return True

        except Exception as e:
            logger.error(f"记录策略性能失败: {e}")
            return False

    async def get_strategy_performance(self, strategy_id: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        获取策略性能历史

        Args:
            strategy_id: 策略ID
            days: 查询天数

        Returns:
            性能数据列表
        """
        try:
            start_time = datetime.now() - timedelta(days=days)

            async with self.postgres_pool.acquire() as conn:
                sql = """
                SELECT * FROM strategy_performance
                WHERE strategy_id = $1 AND timestamp >= $2
                ORDER BY timestamp DESC
                """
                rows = await conn.fetch(sql, strategy_id, start_time)

                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"获取策略性能失败: {e}")
            return []

    async def get_portfolio_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        获取组合历史数据

        Args:
            days: 查询天数

        Returns:
            历史数据列表
        """
        try:
            start_time = datetime.now() - timedelta(days=days)

            async with self.postgres_pool.acquire() as conn:
                sql = """
                SELECT * FROM portfolio_status
                WHERE timestamp >= $1
                ORDER BY timestamp DESC
                """
                rows = await conn.fetch(sql, start_time)

                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"获取组合历史失败: {e}")
            return []

    async def get_trade_history(
        self,
        strategy_id: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取交易历史

        Args:
            strategy_id: 策略ID（可选）
            symbol: 合约代码（可选）
            limit: 数据条数

        Returns:
            交易历史列表
        """
        try:
            async with self.postgres_pool.acquire() as conn:
                conditions = []
                params = []
                param_count = 1

                if strategy_id:
                    conditions.append(f"strategy_id = ${param_count}")
                    params.append(strategy_id)
                    param_count += 1

                if symbol:
                    conditions.append(f"symbol = ${param_count}")
                    params.append(symbol)
                    param_count += 1

                where_clause = ""
                if conditions:
                    where_clause = "WHERE " + " AND ".join(conditions)

                conditions.append(f"LIMIT ${param_count}")
                params.append(limit)

                sql = f"""
                SELECT * FROM strategy_trades
                {where_clause}
                ORDER BY timestamp DESC
                LIMIT ${param_count}
                """
                rows = await conn.fetch(sql, *params)

                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"获取交易历史失败: {e}")
            return []

    # ==================== 数据维护 ====================

    async def cleanup_old_data(self, days_to_keep: int = 30):
        """
        清理旧数据

        Args:
            days_to_keep: 保留天数
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)

            async with self.postgres_pool.acquire() as conn:
                # 清理1分钟数据
                result1 = await conn.execute("""
                DELETE FROM market_data
                WHERE timeframe = '1m' AND time < $1
                """, cutoff_date)

                # 清理技术指标
                result2 = await conn.execute("""
                DELETE FROM technical_indicators
                WHERE time < $1
                """, cutoff_date)

                logger.info(f"清理旧数据: 1分钟数据, 技术指标")

        except Exception as e:
            logger.error(f"清理旧数据失败: {e}")

    async def close(self):
        """关闭所有数据库连接"""
        try:
            if self.postgres_pool:
                await self.postgres_pool.close()
                logger.info("PostgreSQL连接已关闭")

            if self.redis_client:
                await self.redis_client.close()
                logger.info("Redis连接已关闭")

        except Exception as e:
            logger.error(f"关闭数据库连接失败: {e}")

# 全局数据库管理器实例
db_manager: Optional[DatabaseManager] = None

async def get_database_manager(config: DatabaseConfig) -> DatabaseManager:
    """获取数据库管理器实例"""
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager(config)
        await db_manager.initialize()
    return db_manager