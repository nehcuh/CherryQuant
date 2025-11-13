"""
CherryQuant 数据库管理器 (MongoDB 版本)
使用 MongoDB + Redis 的架构
保持与原 PostgreSQL 版本相同的接口
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from decimal import Decimal
from dataclasses import dataclass, asdict

# MongoDB 驱动
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
from bson import ObjectId, Decimal128
import redis.asyncio as aioredis

from .timeframe_data_manager import TimeFrame, MarketDataPoint, TechnicalIndicators
from .mongodb_manager import MongoDBConnectionManager, get_mongodb_manager

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """数据库配置（MongoDB 版本）"""
    # MongoDB 配置
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "cherryquant"
    mongodb_min_pool_size: int = 5
    mongodb_max_pool_size: int = 50
    mongodb_username: Optional[str] = None
    mongodb_password: Optional[str] = None

    # Redis 配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None

    # 缓存配置
    cache_ttl: int = 300  # 5分钟

    # 向后兼容（兼容旧的 PostgreSQL 配置名称）
    @classmethod
    def from_postgres_config(cls, postgres_host=None, postgres_port=None, **kwargs):
        """从旧的 PostgreSQL 配置创建（向后兼容）"""
        logger.warning("⚠️  检测到 PostgreSQL 配置，已自动转换为 MongoDB 配置")
        return cls(**kwargs)


class DatabaseManager:
    """CherryQuant 数据库管理器 (MongoDB 版本)"""

    def __init__(self, config: DatabaseConfig):
        """
        初始化数据库管理器

        Args:
            config: 数据库配置
        """
        self.config = config
        self.mongodb_manager: Optional[MongoDBConnectionManager] = None
        self.redis_client: Optional[aioredis.Redis] = None

        # 缓存配置
        self.cache_ttl = config.cache_ttl
        self.cache_prefix = "cherryquant:"

    async def initialize(self):
        """初始化所有数据库连接"""
        try:
            # 初始化 MongoDB
            self.mongodb_manager = await get_mongodb_manager(
                uri=self.config.mongodb_uri,
                database=self.config.mongodb_database,
                min_pool_size=self.config.mongodb_min_pool_size,
                max_pool_size=self.config.mongodb_max_pool_size,
                username=self.config.mongodb_username,
                password=self.config.mongodb_password
            )

            # 初始化 Redis
            await self._connect_redis()

            logger.info("✅ 数据库连接初始化完成 (MongoDB)")
        except Exception as e:
            logger.error(f"❌ 数据库初始化失败: {e}")
            await self.close()
            raise

    async def _connect_redis(self):
        """连接Redis缓存"""
        try:
            redis_url = f"redis://{self.config.redis_host}:{self.config.redis_port}"
            if self.config.redis_password:
                redis_url = f"redis://:{self.config.redis_password}@{self.config.redis_host}:{self.config.redis_port}"

            self.redis_client = aioredis.from_url(
                redis_url,
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
        存储市场数据到 MongoDB

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
            collection = self.mongodb_manager.get_collection("market_data")

            # 准备文档
            documents = []
            for point in data_points:
                doc = {
                    "time": point.timestamp,
                    "metadata": {
                        "symbol": symbol,
                        "exchange": exchange,
                        "timeframe": timeframe.value
                    },
                    "open_price": Decimal128(str(point.open)) if point.open is not None else None,
                    "high_price": Decimal128(str(point.high)) if point.high is not None else None,
                    "low_price": Decimal128(str(point.low)) if point.low is not None else None,
                    "close_price": Decimal128(str(point.close)) if point.close is not None else None,
                    "volume": int(point.volume) if point.volume is not None else None,
                    "open_interest": int(point.open_interest) if point.open_interest is not None else None,
                    "turnover": Decimal128(str(point.turnover)) if point.turnover is not None else None,
                    "created_at": datetime.now()
                }
                documents.append(doc)

            # 时间序列集合只支持 insert，不支持 upsert
            # 使用 insert_many，忽略重复键错误
            try:
                await collection.insert_many(documents, ordered=False)
            except Exception as e:
                # 忽略重复键错误 (DuplicateKeyError, code 11000)
                if "11000" not in str(e) and "duplicate" not in str(e).lower():
                    raise
                # 部分插入成功也算成功
                pass

            # 更新缓存
            cache_key = f"{self.cache_prefix}market_data:{symbol}:{exchange}:{timeframe.value}"
            await self._set_cache(cache_key, [asdict(point) for point in data_points], self.cache_ttl)

            logger.info(f"存储市场数据 (MongoDB): {symbol}.{exchange} {timeframe.value} {len(data_points)}条")
            return True

        except Exception as e:
            logger.error(f"存储市场数据失败 (MongoDB): {e}")
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

            # 构建查询条件
            query = {
                "metadata.symbol": symbol,
                "metadata.exchange": exchange,
                "metadata.timeframe": timeframe.value
            }

            if start_time:
                query["time"] = query.get("time", {})
                query["time"]["$gte"] = start_time
            if end_time:
                query["time"] = query.get("time", {})
                query["time"]["$lte"] = end_time

            # 查询数据
            collection = self.mongodb_manager.get_collection("market_data")
            cursor = collection.find(query).sort("time", DESCENDING)

            if limit:
                cursor = cursor.limit(limit)

            docs = await cursor.to_list(length=None)

            # 转换为 MarketDataPoint
            data_points = []
            for doc in docs:
                point = MarketDataPoint(
                    timestamp=doc["time"],
                    open=float(doc["open_price"].to_decimal()) if doc.get("open_price") else None,
                    high=float(doc["high_price"].to_decimal()) if doc.get("high_price") else None,
                    low=float(doc["low_price"].to_decimal()) if doc.get("low_price") else None,
                    close=float(doc["close_price"].to_decimal()) if doc.get("close_price") else None,
                    volume=doc.get("volume"),
                    open_interest=doc.get("open_interest"),
                    turnover=float(doc["turnover"].to_decimal()) if doc.get("turnover") else None
                )
                data_points.append(point)

            # 缓存结果
            if data_points:
                await self._set_cache(cache_key, [asdict(point) for point in data_points], self.cache_ttl)

            logger.info(f"从 MongoDB 获取市场数据: {symbol}.{exchange} {timeframe.value} {len(data_points)}条")
            return data_points

        except Exception as e:
            logger.error(f"获取市场数据失败 (MongoDB): {e}")
            return []

    # ==================== 技术指标管理 ====================

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
            collection = self.mongodb_manager.get_collection("technical_indicators")

            # 准备文档
            from pymongo import UpdateOne
            operations = []

            for indicator in indicators:
                doc = {
                    "time": indicator.timestamp,
                    "metadata": {
                        "symbol": symbol,
                        "exchange": exchange,
                        "timeframe": timeframe.value
                    },
                    "indicators": {
                        # 移动平均线
                        "ma5": Decimal128(str(indicator.ma5)) if indicator.ma5 is not None else None,
                        "ma10": Decimal128(str(indicator.ma10)) if indicator.ma10 is not None else None,
                        "ma20": Decimal128(str(indicator.ma20)) if indicator.ma20 is not None else None,
                        "ma60": Decimal128(str(indicator.ma60)) if indicator.ma60 is not None else None,
                        "ema12": Decimal128(str(indicator.ema12)) if indicator.ema12 is not None else None,
                        "ema26": Decimal128(str(indicator.ema26)) if indicator.ema26 is not None else None,
                        # MACD
                        "macd": Decimal128(str(indicator.macd)) if indicator.macd is not None else None,
                        "macd_signal": Decimal128(str(indicator.macd_signal)) if indicator.macd_signal is not None else None,
                        "macd_histogram": Decimal128(str(indicator.macd_histogram)) if indicator.macd_histogram is not None else None,
                        # KDJ
                        "kdj_k": Decimal128(str(indicator.kdj_k)) if indicator.kdj_k is not None else None,
                        "kdj_d": Decimal128(str(indicator.kdj_d)) if indicator.kdj_d is not None else None,
                        "kdj_j": Decimal128(str(indicator.kdj_j)) if indicator.kdj_j is not None else None,
                        # RSI
                        "rsi": Decimal128(str(indicator.rsi)) if indicator.rsi is not None else None,
                        # 布林带
                        "bb_upper": Decimal128(str(indicator.bb_upper)) if indicator.bb_upper is not None else None,
                        "bb_middle": Decimal128(str(indicator.bb_middle)) if indicator.bb_middle is not None else None,
                        "bb_lower": Decimal128(str(indicator.bb_lower)) if indicator.bb_lower is not None else None,
                        # 其他
                        "atr": Decimal128(str(indicator.atr)) if indicator.atr is not None else None,
                        "cci": Decimal128(str(indicator.cci)) if indicator.cci is not None else None,
                        "williams_r": Decimal128(str(indicator.williams_r)) if indicator.williams_r is not None else None,
                    },
                    "created_at": datetime.now()
                }

                operations.append(
                    UpdateOne(
                        {
                            "time": doc["time"],
                            "metadata.symbol": doc["metadata"]["symbol"],
                            "metadata.exchange": doc["metadata"]["exchange"],
                            "metadata.timeframe": doc["metadata"]["timeframe"]
                        },
                        {"$set": doc},
                        upsert=True
                    )
                )

            await collection.bulk_write(operations, ordered=False)

            logger.info(f"存储技术指标 (MongoDB): {symbol}.{exchange} {timeframe.value} {len(indicators)}条")
            return True

        except Exception as e:
            logger.error(f"存储技术指标失败 (MongoDB): {e}")
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
            # 构建查询条件
            query = {
                "metadata.symbol": symbol,
                "metadata.exchange": exchange,
                "metadata.timeframe": timeframe.value
            }

            if start_time:
                query["time"] = query.get("time", {})
                query["time"]["$gte"] = start_time
            if end_time:
                query["time"] = query.get("time", {})
                query["time"]["$lte"] = end_time

            # 查询数据
            collection = self.mongodb_manager.get_collection("technical_indicators")
            cursor = collection.find(query).sort("time", DESCENDING)

            if limit:
                cursor = cursor.limit(limit)

            docs = await cursor.to_list(length=None)

            # 转换为 TechnicalIndicators
            indicators = []
            for doc in docs:
                ind_data = doc.get("indicators", {})
                indicator = TechnicalIndicators(
                    timestamp=doc["time"],
                    ma5=float(ind_data["ma5"].to_decimal()) if ind_data.get("ma5") else None,
                    ma10=float(ind_data["ma10"].to_decimal()) if ind_data.get("ma10") else None,
                    ma20=float(ind_data["ma20"].to_decimal()) if ind_data.get("ma20") else None,
                    ma60=float(ind_data["ma60"].to_decimal()) if ind_data.get("ma60") else None,
                    ema12=float(ind_data["ema12"].to_decimal()) if ind_data.get("ema12") else None,
                    ema26=float(ind_data["ema26"].to_decimal()) if ind_data.get("ema26") else None,
                    macd=float(ind_data["macd"].to_decimal()) if ind_data.get("macd") else None,
                    macd_signal=float(ind_data["macd_signal"].to_decimal()) if ind_data.get("macd_signal") else None,
                    macd_histogram=float(ind_data["macd_histogram"].to_decimal()) if ind_data.get("macd_histogram") else None,
                    kdj_k=float(ind_data["kdj_k"].to_decimal()) if ind_data.get("kdj_k") else None,
                    kdj_d=float(ind_data["kdj_d"].to_decimal()) if ind_data.get("kdj_d") else None,
                    kdj_j=float(ind_data["kdj_j"].to_decimal()) if ind_data.get("kdj_j") else None,
                    rsi=float(ind_data["rsi"].to_decimal()) if ind_data.get("rsi") else None,
                    bb_upper=float(ind_data["bb_upper"].to_decimal()) if ind_data.get("bb_upper") else None,
                    bb_middle=float(ind_data["bb_middle"].to_decimal()) if ind_data.get("bb_middle") else None,
                    bb_lower=float(ind_data["bb_lower"].to_decimal()) if ind_data.get("bb_lower") else None,
                    atr=float(ind_data["atr"].to_decimal()) if ind_data.get("atr") else None,
                    cci=float(ind_data["cci"].to_decimal()) if ind_data.get("cci") else None,
                    williams_r=float(ind_data["williams_r"].to_decimal()) if ind_data.get("williams_r") else None,
                )
                indicators.append(indicator)

            logger.info(f"从 MongoDB 获取技术指标: {symbol}.{exchange} {timeframe.value} {len(indicators)}条")
            return indicators

        except Exception as e:
            logger.error(f"获取技术指标失败 (MongoDB): {e}")
            return []

    # ==================== AI决策管理 ====================

    async def store_ai_decision(self, decision: Dict[str, Any]) -> bool:
        """
        存储AI决策记录

        Args:
            decision: 决策信息字典

        Returns:
            是否成功
        """
        try:
            collection = self.mongodb_manager.get_collection("ai_decisions")

            # 准备文档
            doc = {
                "decision_time": decision.get("decision_time", datetime.now()),
                "symbol": decision.get("symbol"),
                "exchange": decision.get("exchange"),
                "action": decision.get("action"),
                "quantity": decision.get("quantity"),
                "leverage": decision.get("leverage"),
                "entry_price": Decimal128(str(decision["entry_price"])) if decision.get("entry_price") else None,
                "profit_target": Decimal128(str(decision["profit_target"])) if decision.get("profit_target") else None,
                "stop_loss": Decimal128(str(decision["stop_loss"])) if decision.get("stop_loss") else None,
                "confidence": Decimal128(str(decision["confidence"])) if decision.get("confidence") else None,
                "opportunity_score": decision.get("opportunity_score"),
                "selection_rationale": decision.get("selection_rationale"),
                "technical_analysis": decision.get("technical_analysis"),
                "risk_factors": decision.get("risk_factors"),
                "market_regime": decision.get("market_regime"),
                "volatility_index": decision.get("volatility_index"),
                "status": decision.get("status", "pending"),
                "executed_at": decision.get("executed_at"),
                "execution_price": Decimal128(str(decision["execution_price"])) if decision.get("execution_price") else None,
                "created_at": datetime.now()
            }

            result = await collection.insert_one(doc)
            logger.info(f"存储AI决策 (MongoDB): {decision.get('symbol')} {decision.get('action')}")
            return True

        except Exception as e:
            logger.error(f"存储AI决策失败 (MongoDB): {e}")
            return False

    async def get_ai_decisions(
        self,
        symbol: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取AI决策记录

        Args:
            symbol: 合约代码（可选）
            start_time: 开始时间（可选）
            end_time: 结束时间（可选）
            status: 状态过滤（可选）
            limit: 返回条数限制（可选）

        Returns:
            决策记录列表
        """
        try:
            collection = self.mongodb_manager.get_collection("ai_decisions")

            # 构建查询条件
            query = {}
            if symbol:
                query["symbol"] = symbol
            if status:
                query["status"] = status
            if start_time or end_time:
                query["decision_time"] = {}
                if start_time:
                    query["decision_time"]["$gte"] = start_time
                if end_time:
                    query["decision_time"]["$lte"] = end_time

            cursor = collection.find(query).sort("decision_time", DESCENDING)
            if limit:
                cursor = cursor.limit(limit)

            docs = await cursor.to_list(length=None)

            # 转换为字典列表
            decisions = []
            for doc in docs:
                decision = {
                    "id": str(doc["_id"]),
                    "decision_time": doc.get("decision_time"),
                    "symbol": doc.get("symbol"),
                    "exchange": doc.get("exchange"),
                    "action": doc.get("action"),
                    "quantity": doc.get("quantity"),
                    "leverage": doc.get("leverage"),
                    "entry_price": float(doc["entry_price"].to_decimal()) if doc.get("entry_price") else None,
                    "profit_target": float(doc["profit_target"].to_decimal()) if doc.get("profit_target") else None,
                    "stop_loss": float(doc["stop_loss"].to_decimal()) if doc.get("stop_loss") else None,
                    "confidence": float(doc["confidence"].to_decimal()) if doc.get("confidence") else None,
                    "opportunity_score": doc.get("opportunity_score"),
                    "selection_rationale": doc.get("selection_rationale"),
                    "technical_analysis": doc.get("technical_analysis"),
                    "risk_factors": doc.get("risk_factors"),
                    "market_regime": doc.get("market_regime"),
                    "volatility_index": doc.get("volatility_index"),
                    "status": doc.get("status"),
                    "executed_at": doc.get("executed_at"),
                    "execution_price": float(doc["execution_price"].to_decimal()) if doc.get("execution_price") else None,
                }
                decisions.append(decision)

            logger.info(f"从 MongoDB 获取AI决策: {len(decisions)}条")
            return decisions

        except Exception as e:
            logger.error(f"获取AI决策失败 (MongoDB): {e}")
            return []

    async def update_ai_decision_status(
        self,
        decision_id: str,
        status: str,
        executed_at: Optional[datetime] = None,
        execution_price: Optional[float] = None
    ) -> bool:
        """
        更新AI决策状态

        Args:
            decision_id: 决策ID
            status: 新状态
            executed_at: 执行时间（可选）
            execution_price: 执行价格（可选）

        Returns:
            是否成功
        """
        try:
            collection = self.mongodb_manager.get_collection("ai_decisions")

            update_doc = {"status": status}
            if executed_at:
                update_doc["executed_at"] = executed_at
            if execution_price:
                update_doc["execution_price"] = Decimal128(str(execution_price))

            result = await collection.update_one(
                {"_id": ObjectId(decision_id)},
                {"$set": update_doc}
            )

            if result.modified_count > 0:
                logger.info(f"更新AI决策状态 (MongoDB): {decision_id} -> {status}")
                return True
            else:
                logger.warning(f"未找到AI决策 (MongoDB): {decision_id}")
                return False

        except Exception as e:
            logger.error(f"更新AI决策状态失败 (MongoDB): {e}")
            return False

    # ==================== 交易记录管理 ====================

    async def create_trade_entry(self, trade: Dict[str, Any]) -> Optional[str]:
        """
        创建交易记录

        Args:
            trade: 交易信息字典

        Returns:
            交易ID（字符串），失败返回None
        """
        try:
            collection = self.mongodb_manager.get_collection("trades")

            # 准备文档
            doc = {
                "symbol": trade.get("symbol"),
                "exchange": trade.get("exchange"),
                "direction": trade.get("direction"),
                "quantity": trade.get("quantity"),
                "entry_price": Decimal128(str(trade["entry_price"])) if trade.get("entry_price") else None,
                "entry_time": trade.get("entry_time", datetime.now()),
                "entry_fee": Decimal128(str(trade["entry_fee"])) if trade.get("entry_fee") else None,
                "stop_loss_price": Decimal128(str(trade["stop_loss_price"])) if trade.get("stop_loss_price") else None,
                "take_profit_price": Decimal128(str(trade["take_profit_price"])) if trade.get("take_profit_price") else None,
                "ai_decision_id": ObjectId(trade["ai_decision_id"]) if trade.get("ai_decision_id") else None,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }

            result = await collection.insert_one(doc)
            trade_id = str(result.inserted_id)
            logger.info(f"创建交易记录 (MongoDB): {trade_id}")
            return trade_id

        except Exception as e:
            logger.error(f"创建交易记录失败 (MongoDB): {e}")
            return None

    async def close_trade(
        self,
        trade_id: str,
        exit_price: float,
        exit_time: Optional[datetime] = None,
        exit_fee: Optional[float] = None
    ) -> bool:
        """
        关闭交易

        Args:
            trade_id: 交易ID
            exit_price: 平仓价格
            exit_time: 平仓时间
            exit_fee: 平仓手续费

        Returns:
            是否成功
        """
        try:
            collection = self.mongodb_manager.get_collection("trades")

            # 获取交易记录
            trade = await collection.find_one({"_id": ObjectId(trade_id)})
            if not trade:
                logger.warning(f"未找到交易记录 (MongoDB): {trade_id}")
                return False

            # 计算盈亏
            entry_price = float(trade["entry_price"].to_decimal())
            quantity = trade["quantity"]
            direction = trade["direction"]

            if direction == "long":
                gross_pnl = (exit_price - entry_price) * quantity
            else:  # short
                gross_pnl = (entry_price - exit_price) * quantity

            total_fee = 0
            if trade.get("entry_fee"):
                total_fee += float(trade["entry_fee"].to_decimal())
            if exit_fee:
                total_fee += exit_fee

            net_pnl = gross_pnl - total_fee
            pnl_percentage = (net_pnl / (entry_price * quantity)) * 100 if entry_price * quantity > 0 else 0

            # 更新交易记录
            update_doc = {
                "exit_price": Decimal128(str(exit_price)),
                "exit_time": exit_time or datetime.now(),
                "exit_fee": Decimal128(str(exit_fee)) if exit_fee else None,
                "gross_pnl": Decimal128(str(gross_pnl)),
                "net_pnl": Decimal128(str(net_pnl)),
                "pnl_percentage": Decimal128(str(pnl_percentage)),
                "updated_at": datetime.now()
            }

            result = await collection.update_one(
                {"_id": ObjectId(trade_id)},
                {"$set": update_doc}
            )

            if result.modified_count > 0:
                logger.info(f"关闭交易 (MongoDB): {trade_id}, PnL: {net_pnl:.2f}")
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"关闭交易失败 (MongoDB): {e}")
            return False

    # ==================== 组合和策略管理 ====================

    async def record_trade(self, trade_data: Dict[str, Any]) -> bool:
        """
        记录交易（简化版，直接调用 create_trade_entry）

        Args:
            trade_data: 交易数据

        Returns:
            是否成功
        """
        trade_id = await self.create_trade_entry(trade_data)
        return trade_id is not None

    async def record_portfolio_status(self, portfolio_data: Dict[str, Any]) -> bool:
        """
        记录投资组合状态

        Args:
            portfolio_data: 组合数据

        Returns:
            是否成功
        """
        try:
            collection = self.mongodb_manager.get_collection("portfolio")

            doc = {
                "time": portfolio_data.get("as_of", datetime.now()),
                "total_value": Decimal128(str(portfolio_data["total_value"])) if portfolio_data.get("total_value") else None,
                "available_cash": Decimal128(str(portfolio_data["available_cash"])) if portfolio_data.get("available_cash") else None,
                "used_margin": Decimal128(str(portfolio_data["used_margin"])) if portfolio_data.get("used_margin") else None,
                "unrealized_pnl": Decimal128(str(portfolio_data["unrealized_pnl"])) if portfolio_data.get("unrealized_pnl") else None,
                "positions_count": portfolio_data.get("positions_count", 0),
                "total_exposure": Decimal128(str(portfolio_data["total_exposure"])) if portfolio_data.get("total_exposure") else None,
                "max_drawdown": Decimal128(str(portfolio_data["max_drawdown"])) if portfolio_data.get("max_drawdown") else None,
                "daily_var": Decimal128(str(portfolio_data["daily_var"])) if portfolio_data.get("daily_var") else None,
                "sharpe_ratio": Decimal128(str(portfolio_data["sharpe_ratio"])) if portfolio_data.get("sharpe_ratio") else None,
                "created_at": datetime.now()
            }

            await collection.insert_one(doc)
            logger.info("记录投资组合状态 (MongoDB)")
            return True

        except Exception as e:
            logger.error(f"记录投资组合状态失败 (MongoDB): {e}")
            return False

    async def record_strategy_performance(self, strategy_id: str, performance_data: Dict[str, Any]) -> bool:
        """
        记录策略表现（简化实现）

        Args:
            strategy_id: 策略ID
            performance_data: 表现数据

        Returns:
            是否成功
        """
        # TODO: 实现策略表现记录
        logger.warning("record_strategy_performance not fully implemented yet")
        return True

    async def get_strategy_performance(self, strategy_id: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        获取策略表现（简化实现）

        Args:
            strategy_id: 策略ID
            days: 天数

        Returns:
            表现数据列表
        """
        # TODO: 实现策略表现查询
        logger.warning("get_strategy_performance not fully implemented yet")
        return []

    async def get_portfolio_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        获取投资组合历史

        Args:
            days: 天数

        Returns:
            组合历史列表
        """
        try:
            collection = self.mongodb_manager.get_collection("portfolio")

            start_time = datetime.now() - timedelta(days=days)
            cursor = collection.find({"time": {"$gte": start_time}}).sort("time", DESCENDING)

            docs = await cursor.to_list(length=None)

            history = []
            for doc in docs:
                item = {
                    "as_of": doc.get("time"),
                    "total_value": float(doc["total_value"].to_decimal()) if doc.get("total_value") else None,
                    "available_cash": float(doc["available_cash"].to_decimal()) if doc.get("available_cash") else None,
                    "used_margin": float(doc["used_margin"].to_decimal()) if doc.get("used_margin") else None,
                    "unrealized_pnl": float(doc["unrealized_pnl"].to_decimal()) if doc.get("unrealized_pnl") else None,
                    "positions_count": doc.get("positions_count"),
                }
                history.append(item)

            logger.info(f"从 MongoDB 获取组合历史: {len(history)}条")
            return history

        except Exception as e:
            logger.error(f"获取组合历史失败 (MongoDB): {e}")
            return []

    async def get_trade_history(
        self,
        symbol: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = 100
    ) -> List[Dict[str, Any]]:
        """
        获取交易历史

        Args:
            symbol: 合约代码（可选）
            start_time: 开始时间（可选）
            end_time: 结束时间（可选）
            limit: 返回条数限制

        Returns:
            交易历史列表
        """
        try:
            collection = self.mongodb_manager.get_collection("trades")

            # 构建查询条件
            query = {}
            if symbol:
                query["symbol"] = symbol
            if start_time or end_time:
                query["entry_time"] = {}
                if start_time:
                    query["entry_time"]["$gte"] = start_time
                if end_time:
                    query["entry_time"]["$lte"] = end_time

            cursor = collection.find(query).sort("entry_time", DESCENDING)
            if limit:
                cursor = cursor.limit(limit)

            docs = await cursor.to_list(length=None)

            trades = []
            for doc in docs:
                trade = {
                    "id": str(doc["_id"]),
                    "symbol": doc.get("symbol"),
                    "exchange": doc.get("exchange"),
                    "direction": doc.get("direction"),
                    "quantity": doc.get("quantity"),
                    "entry_price": float(doc["entry_price"].to_decimal()) if doc.get("entry_price") else None,
                    "exit_price": float(doc["exit_price"].to_decimal()) if doc.get("exit_price") else None,
                    "entry_time": doc.get("entry_time"),
                    "exit_time": doc.get("exit_time"),
                    "gross_pnl": float(doc["gross_pnl"].to_decimal()) if doc.get("gross_pnl") else None,
                    "net_pnl": float(doc["net_pnl"].to_decimal()) if doc.get("net_pnl") else None,
                    "pnl_percentage": float(doc["pnl_percentage"].to_decimal()) if doc.get("pnl_percentage") else None,
                }
                trades.append(trade)

            logger.info(f"从 MongoDB 获取交易历史: {len(trades)}条")
            return trades

        except Exception as e:
            logger.error(f"获取交易历史失败 (MongoDB): {e}")
            return []

    # ==================== 缓存管理 ====================

    async def clear_cache(self, pattern: str = None):
        """
        清除缓存

        Args:
            pattern: 缓存键模式（可选）
        """
        try:
            if pattern:
                # 删除匹配模式的键
                keys = await self.redis_client.keys(f"{self.cache_prefix}{pattern}*")
                if keys:
                    await self.redis_client.delete(*keys)
                    logger.info(f"清除缓存: {len(keys)}个键")
            else:
                # 清除所有缓存
                keys = await self.redis_client.keys(f"{self.cache_prefix}*")
                if keys:
                    await self.redis_client.delete(*keys)
                    logger.info(f"清除所有缓存: {len(keys)}个键")
        except Exception as e:
            logger.error(f"清除缓存失败: {e}")

    async def _get_cache(self, key: str) -> Optional[Any]:
        """从 Redis 获取缓存"""
        try:
            import json
            data = await self.redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.debug(f"获取缓存失败: {e}")
            return None

    async def _set_cache(self, key: str, value: Any, ttl: int = None):
        """设置 Redis 缓存"""
        try:
            import json
            data = json.dumps(value, default=str)
            await self.redis_client.setex(key, ttl or self.cache_ttl, data)
        except Exception as e:
            logger.debug(f"设置缓存失败: {e}")

    # ==================== 统计和维护 ====================

    async def get_data_statistics(self) -> Dict[str, Any]:
        """
        获取数据统计信息

        Returns:
            统计信息字典
        """
        try:
            stats = await self.mongodb_manager.get_stats()

            # 获取各集合的文档数量
            collections_stats = {}
            for coll_name in ["market_data", "technical_indicators", "ai_decisions", "trades", "portfolio"]:
                coll = self.mongodb_manager.get_collection(coll_name)
                count = await coll.count_documents({})
                collections_stats[coll_name] = count

            result = {
                "database": {
                    "storage_size_mb": stats.get("storageSize", 0) / 1024 / 1024,
                    "data_size_mb": stats.get("dataSize", 0) / 1024 / 1024,
                    "index_size_mb": stats.get("indexSize", 0) / 1024 / 1024,
                    "collections": stats.get("collections", 0),
                },
                "collections": collections_stats,
                "timestamp": datetime.now()
            }

            logger.info("获取数据统计 (MongoDB)")
            return result

        except Exception as e:
            logger.error(f"获取数据统计失败 (MongoDB): {e}")
            return {}

    async def cleanup_old_data(self, days_to_keep: int = 30):
        """
        清理旧数据

        Args:
            days_to_keep: 保留天数
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)

            # 注意：时序集合已经配置了 TTL，会自动清理
            # 这里只需要清理非时序集合的旧数据

            # 清理旧的更新日志
            collection = self.mongodb_manager.get_collection("data_update_log")
            result = await collection.delete_many({"created_at": {"$lt": cutoff_date}})
            logger.info(f"清理旧日志 (MongoDB): {result.deleted_count}条")

            logger.info(f"数据清理完成 (MongoDB): 保留 {days_to_keep} 天")

        except Exception as e:
            logger.error(f"清理旧数据失败 (MongoDB): {e}")

    async def close(self):
        """关闭所有数据库连接"""
        try:
            if self.mongodb_manager:
                await self.mongodb_manager.disconnect()
            if self.redis_client:
                await self.redis_client.close()
            logger.info("✅ 数据库连接已关闭 (MongoDB)")
        except Exception as e:
            logger.error(f"关闭数据库连接失败: {e}")


# 便捷函数
async def get_database_manager(config: DatabaseConfig = None) -> DatabaseManager:
    """
    获取数据库管理器实例

    Args:
        config: 数据库配置

    Returns:
        数据库管理器实例
    """
    if config is None:
        # 从配置文件读取
        from config.settings.base import CONFIG
        config = DatabaseConfig(
            mongodb_uri=CONFIG.database.mongodb_uri,
            mongodb_database=CONFIG.database.mongodb_database,
            mongodb_min_pool_size=CONFIG.database.mongodb_min_pool_size,
            mongodb_max_pool_size=CONFIG.database.mongodb_max_pool_size,
            mongodb_username=CONFIG.database.mongodb_username,
            mongodb_password=CONFIG.database.mongodb_password,
            redis_host=CONFIG.database.redis_host,
            redis_port=CONFIG.database.redis_port,
            redis_db=CONFIG.database.redis_db,
            redis_password=CONFIG.database.redis_password,
            cache_ttl=CONFIG.database.cache_ttl
        )

    manager = DatabaseManager(config)
    await manager.initialize()
    return manager
