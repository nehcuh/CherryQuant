"""
CherryQuant MongoDB Schema Initialization Script
用于创建 MongoDB 集合、时序集合、索引和 TTL 策略
"""
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import CollectionInvalid
from datetime import datetime


class MongoDBSchemaInitializer:
    """MongoDB Schema 初始化器"""

    def __init__(self, uri: str = "mongodb://localhost:27017", db_name: str = "cherryquant"):
        """
        初始化 MongoDB 连接

        Args:
            uri: MongoDB 连接 URI
            db_name: 数据库名称
        """
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.db_name = db_name

    def create_time_series_collection(
        self,
        collection_name: str,
        time_field: str,
        meta_field: str = None,
        granularity: str = "seconds",
        expire_after_seconds: int = None
    ):
        """
        创建时序集合（Time Series Collection）

        Args:
            collection_name: 集合名称
            time_field: 时间字段名
            meta_field: 元数据字段名（可选）
            granularity: 时间粒度 (seconds|minutes|hours)
            expire_after_seconds: 数据过期时间（秒），None 表示永不过期
        """
        try:
            options = {
                "timeseries": {
                    "timeField": time_field,
                    "granularity": granularity
                }
            }

            if meta_field:
                options["timeseries"]["metaField"] = meta_field

            if expire_after_seconds:
                options["expireAfterSeconds"] = expire_after_seconds

            self.db.create_collection(collection_name, **options)
            print(f"✓ Created time series collection: {collection_name}")
        except CollectionInvalid:
            print(f"⚠ Time series collection already exists: {collection_name}")

    def create_regular_collection(self, collection_name: str):
        """创建常规集合"""
        if collection_name not in self.db.list_collection_names():
            self.db.create_collection(collection_name)
            print(f"✓ Created regular collection: {collection_name}")
        else:
            print(f"⚠ Collection already exists: {collection_name}")

    def create_indexes(self, collection_name: str, indexes: list):
        """
        创建索引

        Args:
            collection_name: 集合名称
            indexes: 索引列表，格式: [(field, direction), ...]
        """
        collection = self.db[collection_name]
        for idx in indexes:
            try:
                if isinstance(idx, tuple):
                    # 单字段索引
                    field, direction = idx
                    collection.create_index([(field, direction)])
                    print(f"  ✓ Created index on {collection_name}.{field}")
                elif isinstance(idx, dict):
                    # 复合索引或带选项的索引
                    keys = idx.get("keys")
                    options = {k: v for k, v in idx.items() if k != "keys"}
                    collection.create_index(keys, **options)
                    print(f"  ✓ Created compound index on {collection_name}: {keys}")
            except Exception as e:
                print(f"  ⚠ Index creation warning for {collection_name}: {e}")

    def init_market_data_collection(self):
        """
        初始化市场数据集合（时序数据）

        对应 PostgreSQL 的 market_data 表
        Schema:
        {
            "time": ISODate,        # 时间戳
            "metadata": {           # 元数据（用于时序集合优化）
                "symbol": str,      # 合约代码
                "exchange": str,    # 交易所
                "timeframe": str    # 时间周期（1m, 5m, 15m, 1h, 1d）
            },
            "open_price": Decimal128,
            "high_price": Decimal128,
            "low_price": Decimal128,
            "close_price": Decimal128,
            "volume": int,
            "open_interest": int,
            "turnover": Decimal128,
            "settlement_price": Decimal128,
            "created_at": ISODate
        }
        """
        # 创建时序集合
        # 1分钟数据保留 7 天（7 * 24 * 3600 = 604800 秒）
        self.create_time_series_collection(
            collection_name="market_data",
            time_field="time",
            meta_field="metadata",
            granularity="minutes",
            expire_after_seconds=604800  # 7天
        )

        # 创建索引（时序集合会自动在 metadata 和 time 上创建索引）
        # 额外创建复合索引以优化查询
        indexes = [
            {
                "keys": [("metadata.symbol", ASCENDING), ("time", DESCENDING)],
                "name": "idx_symbol_time"
            },
            {
                "keys": [("metadata.timeframe", ASCENDING), ("time", DESCENDING)],
                "name": "idx_timeframe_time"
            },
            {
                "keys": [
                    ("metadata.symbol", ASCENDING),
                    ("metadata.exchange", ASCENDING),
                    ("metadata.timeframe", ASCENDING),
                    ("time", DESCENDING)
                ],
                "name": "idx_symbol_exchange_timeframe_time",
                "unique": True  # 确保唯一性
            }
        ]
        self.create_indexes("market_data", indexes)

    def init_technical_indicators_collection(self):
        """
        初始化技术指标集合（时序数据）

        对应 PostgreSQL 的 technical_indicators 表
        Schema:
        {
            "time": ISODate,
            "metadata": {
                "symbol": str,
                "exchange": str,
                "timeframe": str
            },
            "indicators": {
                # 移动平均线
                "ma5": Decimal128,
                "ma10": Decimal128,
                "ma20": Decimal128,
                "ma60": Decimal128,
                "ema12": Decimal128,
                "ema26": Decimal128,
                # MACD
                "macd": Decimal128,
                "macd_signal": Decimal128,
                "macd_histogram": Decimal128,
                # KDJ
                "kdj_k": Decimal128,
                "kdj_d": Decimal128,
                "kdj_j": Decimal128,
                # RSI
                "rsi": Decimal128,
                # 布林带
                "bb_upper": Decimal128,
                "bb_middle": Decimal128,
                "bb_lower": Decimal128,
                # 其他
                "atr": Decimal128,
                "cci": Decimal128,
                "williams_r": Decimal128
            },
            "created_at": ISODate
        }
        """
        # 技术指标保留 30 天
        self.create_time_series_collection(
            collection_name="technical_indicators",
            time_field="time",
            meta_field="metadata",
            granularity="minutes",
            expire_after_seconds=2592000  # 30天
        )

        indexes = [
            {
                "keys": [("metadata.symbol", ASCENDING), ("time", DESCENDING)],
                "name": "idx_symbol_time"
            },
            {
                "keys": [
                    ("metadata.symbol", ASCENDING),
                    ("metadata.exchange", ASCENDING),
                    ("metadata.timeframe", ASCENDING),
                    ("time", DESCENDING)
                ],
                "name": "idx_symbol_exchange_timeframe_time",
                "unique": True
            }
        ]
        self.create_indexes("technical_indicators", indexes)

    def init_ai_decisions_collection(self):
        """
        初始化 AI 决策记录集合

        对应 PostgreSQL 的 ai_decisions 表
        Schema:
        {
            "_id": ObjectId,            # 自动生成
            "decision_time": ISODate,
            "symbol": str,
            "exchange": str,
            "action": str,              # "buy", "sell", "hold"
            "quantity": int,
            "leverage": int,
            "entry_price": Decimal128,
            "profit_target": Decimal128,
            "stop_loss": Decimal128,
            "confidence": Decimal128,   # 0-1
            "opportunity_score": int,   # 0-100
            "selection_rationale": str,
            "technical_analysis": str,
            "risk_factors": str,
            "market_regime": str,
            "volatility_index": str,
            "status": str,              # "pending", "executed", "cancelled"
            "executed_at": ISODate,
            "execution_price": Decimal128,
            "created_at": ISODate
        }
        """
        self.create_regular_collection("ai_decisions")

        indexes = [
            ("decision_time", DESCENDING),
            {
                "keys": [("symbol", ASCENDING), ("decision_time", DESCENDING)],
                "name": "idx_symbol_decision_time"
            },
            ("status", ASCENDING),
            {
                "keys": [("decision_time", DESCENDING)],
                "name": "idx_decision_time_ttl",
                "expireAfterSeconds": 31536000  # 保留 1 年
            }
        ]
        self.create_indexes("ai_decisions", indexes)

    def init_trades_collection(self):
        """
        初始化交易记录集合

        对应 PostgreSQL 的 trades 表
        Schema:
        {
            "_id": ObjectId,
            "symbol": str,
            "exchange": str,
            "direction": str,           # "long", "short"
            "quantity": int,
            "entry_price": Decimal128,
            "exit_price": Decimal128,
            "entry_time": ISODate,
            "exit_time": ISODate,
            "entry_fee": Decimal128,
            "exit_fee": Decimal128,
            "gross_pnl": Decimal128,
            "net_pnl": Decimal128,
            "pnl_percentage": Decimal128,
            "stop_loss_price": Decimal128,
            "take_profit_price": Decimal128,
            "max_favorable_move": Decimal128,
            "max_adverse_move": Decimal128,
            "ai_decision_id": ObjectId,  # 引用 ai_decisions._id
            "created_at": ISODate,
            "updated_at": ISODate
        }
        """
        self.create_regular_collection("trades")

        indexes = [
            {
                "keys": [("symbol", ASCENDING), ("entry_time", DESCENDING)],
                "name": "idx_symbol_entry_time"
            },
            ("ai_decision_id", ASCENDING),
            ("entry_time", DESCENDING),
            {
                "keys": [("entry_time", DESCENDING)],
                "name": "idx_entry_time_ttl",
                "expireAfterSeconds": 31536000  # 保留 1 年
            }
        ]
        self.create_indexes("trades", indexes)

    def init_portfolio_collection(self):
        """
        初始化投资组合集合（时序数据）

        对应 PostgreSQL 的 portfolio 表
        Schema:
        {
            "time": ISODate,
            "total_value": Decimal128,
            "available_cash": Decimal128,
            "used_margin": Decimal128,
            "unrealized_pnl": Decimal128,
            "positions_count": int,
            "total_exposure": Decimal128,
            "max_drawdown": Decimal128,
            "daily_var": Decimal128,
            "sharpe_ratio": Decimal128,
            "created_at": ISODate
        }
        """
        self.create_time_series_collection(
            collection_name="portfolio",
            time_field="time",
            granularity="hours",
            expire_after_seconds=7776000  # 保留 90 天
        )

        indexes = [
            ("time", DESCENDING)
        ]
        self.create_indexes("portfolio", indexes)

    def init_futures_contracts_collection(self):
        """
        初始化期货合约信息集合

        对应 PostgreSQL 的 futures_contracts 表
        Schema:
        {
            "_id": ObjectId,
            "symbol": str,
            "exchange": str,
            "name": str,
            "contract_size": int,
            "margin_rate": Decimal128,
            "price_tick": Decimal128,
            "trading_unit": str,
            "created_at": ISODate,
            "updated_at": ISODate
        }
        """
        self.create_regular_collection("futures_contracts")

        indexes = [
            {
                "keys": [("symbol", ASCENDING), ("exchange", ASCENDING)],
                "name": "idx_symbol_exchange",
                "unique": True
            }
        ]
        self.create_indexes("futures_contracts", indexes)

    def init_market_statistics_collection(self):
        """
        初始化市场统计集合（时序数据）

        对应 PostgreSQL 的 market_statistics 表
        Schema:
        {
            "time": ISODate,
            "metadata": {
                "exchange": str
            },
            "total_contracts": int,
            "active_contracts": int,
            "total_volume": int,
            "total_turnover": Decimal128,
            "gainers_count": int,
            "losers_count": int,
            "unchanged_count": int,
            "avg_volatility": Decimal128,
            "volatility_index": str,
            "market_regime": str,
            "sentiment_score": Decimal128,
            "created_at": ISODate
        }
        """
        self.create_time_series_collection(
            collection_name="market_statistics",
            time_field="time",
            meta_field="metadata",
            granularity="hours",
            expire_after_seconds=2592000  # 保留 30 天
        )

        indexes = [
            ("time", DESCENDING),
            {
                "keys": [("metadata.exchange", ASCENDING), ("time", DESCENDING)],
                "name": "idx_exchange_time"
            }
        ]
        self.create_indexes("market_statistics", indexes)

    def init_data_update_log_collection(self):
        """
        初始化数据更新日志集合

        对应 PostgreSQL 的 data_update_log 表
        Schema:
        {
            "_id": ObjectId,
            "table_name": str,
            "update_type": str,         # "insert", "update", "delete"
            "records_count": int,
            "start_time": ISODate,
            "end_time": ISODate,
            "status": str,              # "running", "completed", "failed"
            "error_message": str,
            "created_at": ISODate
        }
        """
        self.create_regular_collection("data_update_log")

        indexes = [
            ("created_at", DESCENDING),
            ("table_name", ASCENDING),
            {
                "keys": [("created_at", DESCENDING)],
                "name": "idx_created_at_ttl",
                "expireAfterSeconds": 2592000  # 保留 30 天
            }
        ]
        self.create_indexes("data_update_log", indexes)

    def insert_sample_contracts(self):
        """插入示例期货合约数据"""
        contracts = [
            {"symbol": "rb", "exchange": "SHFE", "name": "螺纹钢", "contract_size": 10, "margin_rate": 0.08, "price_tick": 1.0, "trading_unit": "吨"},
            {"symbol": "i", "exchange": "DCE", "name": "铁矿石", "contract_size": 100, "margin_rate": 0.08, "price_tick": 0.5, "trading_unit": "吨"},
            {"symbol": "cu", "exchange": "SHFE", "name": "沪铜", "contract_size": 5, "margin_rate": 0.08, "price_tick": 10.0, "trading_unit": "吨"},
            {"symbol": "al", "exchange": "SHFE", "name": "沪铝", "contract_size": 5, "margin_rate": 0.08, "price_tick": 10.0, "trading_unit": "吨"},
            {"symbol": "zn", "exchange": "SHFE", "name": "沪锌", "contract_size": 5, "margin_rate": 0.08, "price_tick": 5.0, "trading_unit": "吨"},
            {"symbol": "au", "exchange": "SHFE", "name": "沪金", "contract_size": 1000, "margin_rate": 0.08, "price_tick": 0.1, "trading_unit": "克"},
            {"symbol": "ag", "exchange": "SHFE", "name": "沪银", "contract_size": 15, "margin_rate": 0.08, "price_tick": 1.0, "trading_unit": "千克"},
            {"symbol": "ni", "exchange": "SHFE", "name": "沪镍", "contract_size": 1, "margin_rate": 0.08, "price_tick": 10.0, "trading_unit": "吨"},
            {"symbol": "j", "exchange": "DCE", "name": "焦炭", "contract_size": 100, "margin_rate": 0.08, "price_tick": 0.5, "trading_unit": "吨"},
            {"symbol": "jm", "exchange": "DCE", "name": "焦煤", "contract_size": 60, "margin_rate": 0.08, "price_tick": 0.5, "trading_unit": "吨"},
            {"symbol": "a", "exchange": "DCE", "name": "豆一", "contract_size": 10, "margin_rate": 0.05, "price_tick": 1.0, "trading_unit": "吨"},
            {"symbol": "c", "exchange": "DCE", "name": "玉米", "contract_size": 10, "margin_rate": 0.05, "price_tick": 1.0, "trading_unit": "吨"},
            {"symbol": "m", "exchange": "DCE", "name": "豆粕", "contract_size": 10, "margin_rate": 0.05, "price_tick": 1.0, "trading_unit": "吨"},
            {"symbol": "y", "exchange": "DCE", "name": "豆油", "contract_size": 10, "margin_rate": 0.05, "price_tick": 2.0, "trading_unit": "吨"},
            {"symbol": "p", "exchange": "DCE", "name": "棕榈油", "contract_size": 10, "margin_rate": 0.05, "price_tick": 2.0, "trading_unit": "吨"},
            {"symbol": "IF", "exchange": "CFFEX", "name": "沪深300", "contract_size": 300, "margin_rate": 0.15, "price_tick": 0.2, "trading_unit": "点"},
            {"symbol": "IC", "exchange": "CFFEX", "name": "中证500", "contract_size": 200, "margin_rate": 0.15, "price_tick": 0.2, "trading_unit": "点"},
            {"symbol": "IH", "exchange": "CFFEX", "name": "上证50", "contract_size": 300, "margin_rate": 0.15, "price_tick": 0.2, "trading_unit": "点"},
            {"symbol": "T", "exchange": "CFFEX", "name": "10年期国债", "contract_size": 10000, "margin_rate": 0.02, "price_tick": 0.005, "trading_unit": "元"}
        ]

        # 添加时间戳
        now = datetime.now()
        for contract in contracts:
            contract["created_at"] = now
            contract["updated_at"] = now

        # 使用 update_one 配合 upsert 避免重复插入
        collection = self.db["futures_contracts"]
        for contract in contracts:
            collection.update_one(
                {"symbol": contract["symbol"], "exchange": contract["exchange"]},
                {"$setOnInsert": contract},
                upsert=True
            )
        print(f"✓ Inserted/Updated {len(contracts)} sample futures contracts")

    def initialize_all(self):
        """初始化所有集合和索引"""
        print(f"\n{'='*60}")
        print(f"Initializing MongoDB Schema for database: {self.db_name}")
        print(f"{'='*60}\n")

        # 1. 时序数据集合
        print("1. Creating Time Series Collections...")
        self.init_market_data_collection()
        self.init_technical_indicators_collection()
        self.init_portfolio_collection()
        self.init_market_statistics_collection()

        # 2. 业务数据集合
        print("\n2. Creating Regular Collections...")
        self.init_ai_decisions_collection()
        self.init_trades_collection()
        self.init_futures_contracts_collection()
        self.init_data_update_log_collection()

        # 3. 插入示例数据
        print("\n3. Inserting Sample Data...")
        self.insert_sample_contracts()

        print(f"\n{'='*60}")
        print("✓ MongoDB Schema Initialization Completed!")
        print(f"{'='*60}\n")

        # 显示集合列表
        collections = self.db.list_collection_names()
        print(f"Created {len(collections)} collections:")
        for coll in collections:
            print(f"  - {coll}")

    def close(self):
        """关闭数据库连接"""
        self.client.close()


if __name__ == "__main__":
    # 从环境变量或默认值读取配置
    import os

    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DATABASE", "cherryquant")

    print(f"Connecting to MongoDB: {mongodb_uri}")
    print(f"Database: {db_name}\n")

    initializer = MongoDBSchemaInitializer(uri=mongodb_uri, db_name=db_name)

    try:
        initializer.initialize_all()
    except Exception as e:
        print(f"\n✗ Error during initialization: {e}")
        raise
    finally:
        initializer.close()
