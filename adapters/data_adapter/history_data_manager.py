"""
历史数据管理器
用于获取和存储期货历史K线数据
支持多种数据源：AKShare、PostgreSQL、InfluxDB等
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class HistoryDataManager:
    """历史数据管理器"""

    def __init__(self, cache_size: int = 1000, cache_ttl: int = 3600):
        """
        初始化历史数据管理器

        Args:
            cache_size: 缓存大小
            cache_ttl: 缓存TTL（秒）
        """
        self.cache_size = cache_size
        self.cache_ttl = cache_ttl
        self.data_cache = {}
        self._setup_database_connections()

    def _setup_database_connections(self):
        """设置数据库连接"""
        import os
        from dotenv import load_dotenv

        load_dotenv()

        self.db_configs = {
            "postgresql": {
                "host": os.getenv("POSTGRES_HOST", "localhost"),
                "port": int(os.getenv("POSTGRES_PORT", "5432")),
                "database": os.getenv("POSTGRES_DB", "cherryquant"),
                "user": os.getenv("POSTGRES_USER", "cherryquant"),
                "password": os.getenv("POSTGRES_PASSWORD", "cherryquant123"),
            },
            "influxdb": {
                "url": os.getenv("INFLUXDB_URL", "http://localhost:8086"),
                "token": os.getenv("INFLUXDB_TOKEN", ""),
                "org": os.getenv("INFLUXDB_ORG", "cherryquant"),
                "bucket": os.getenv("INFLUXDB_BUCKET", "market_data"),
            },
        }

        self.connections = {}
        self._connect_databases()

    def _connect_databases(self):
        """连接数据库"""
        try:
            # PostgreSQL连接（仅在运行时由子类导入依赖）
            self.connections["postgresql"] = PostgreSQLConnection(
                self.db_configs["postgresql"]
            )
        except ImportError:
            logger.warning("asyncpg未安装，跳过PostgreSQL连接")
        except Exception as e:
            logger.warning(f"PostgreSQL连接失败: {e}")

        try:
            # InfluxDB连接
            self.connections["influxdb"] = InfluxDBConnection(
                self.db_configs["influxdb"]
            )
        except Exception as e:
            logger.warning(f"InfluxDB连接失败或未安装: {e}")

    async def get_historical_data(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        start_date: str = None,
        end_date: str = None,
        days: int = 30,
    ) -> pd.DataFrame:
        """
        获取历史数据

        Args:
            symbol: 期货合约代码
            exchange: 交易所
            interval: 时间间隔
            start_date: 开始日期
            end_date: 结束日期
            days: 获取天数

        Returns:
            历史数据DataFrame
        """
        # 先从缓存获取
        cache_key = f"{symbol}_{exchange}_{interval}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data is not None:
            logger.debug(f"从缓存获取历史数据: {cache_key}")
            return cached_data

        # 从数据库获取
        for db_name, connection in self.connections.items():
            try:
                if connection.is_connected:
                    logger.debug(f"尝试从{db_name}获取历史数据")
                    df = await connection.get_kline_data(
                        symbol, exchange, interval, start_date, end_date
                    )
                    if not df.empty:
                        logger.info(f"从{db_name}获取历史数据成功: {len(df)}条记录")
                        self._cache_data(cache_key, df)
                        return df
            except Exception as e:
                logger.warning(f"{db_name}获取历史数据失败: {e}")

        # 最后从外部数据源获取
        logger.info("从外部数据源获取历史数据")
        df = await self._get_external_data(symbol, exchange, interval, days)
        if not df.empty:
            # 保存到数据库
            await self._save_to_databases(df, symbol, exchange, interval)
            self._cache_data(cache_key, df)

        return df

    async def _get_external_data(
        self, symbol: str, exchange: str, interval: str, days: int = 30
    ) -> pd.DataFrame:
        """从外部数据源获取数据（Tushare 日线；分钟线由 vn.py 记录器提供）"""
        try:
            # 仅支持日线级别的外部抓取；分钟线请使用 vn.py 实时记录器
            interval_norm = (interval or "").lower()
            if interval_norm not in {"1d", "d", "daily", "day"}:
                logger.info("分钟级别历史数据由 vn.py 记录器提供，外部抓取跳过")
                return pd.DataFrame()

            # 使用 Tushare 获取主连/日线历史
            try:
                from adapters.data_adapter.market_data_manager import TushareDataSource
            except Exception:
                logger.warning("Tushare 依赖不可用，无法获取外部日线数据")
                return pd.DataFrame()

            ts_source = TushareDataSource()
            if not ts_source.is_available():
                logger.warning("Tushare Token 未配置或无效，无法获取外部日线数据")
                return pd.DataFrame()

            # 直接调用其日线接口：count 使用 days 近似
            df = await ts_source.get_kline_data(symbol=symbol, period="1d", count=max(days, 1))  # type: ignore[arg-type]
            if df is None or df.empty:
                return pd.DataFrame()

            # 标准化输出
            required_columns = ["datetime", "open", "high", "low", "close", "volume"]
            out = df[required_columns].copy()
            out["datetime"] = pd.to_datetime(out["datetime"]).sort_values()
            out = out.sort_values("datetime").reset_index(drop=True)
            return out

        except Exception as e:
            logger.warning(f"获取外部数据失败: {e}")
            return pd.DataFrame()

    def _convert_symbol(self, symbol: str) -> str:
        """转换期货代码"""
        symbol_map = {
            "rb": "RB",
            "i": "I",
            "j": "J", 
            "jm": "JM",
            "cu": "CU",
            "al": "AL",
            "zn": "ZN", 
            "au": "AU",
            "ag": "AG",
        }

        if symbol.lower() in symbol_map:
            return symbol_map[symbol.lower()]
        return symbol.upper()

    async def _save_to_databases(
        self, df: pd.DataFrame, symbol: str, exchange: str, interval: str
    ):
        """保存数据到数据库"""
        for db_name, connection in self.connections.items():
            try:
                if connection.is_connected:
                    success = await connection.save_kline_data(
                        df, symbol, exchange, interval
                    )
                    if success:
                        logger.info(f"数据已保存到{db_name}")
                    else:
                        logger.warning(f"保存到{db_name}失败")
            except Exception as e:
                logger.error(f"保存到{db_name}时出错: {e}")

    def _get_cached_data(self, key: str) -> Optional[pd.DataFrame]:
        """获取缓存数据"""
        if key in self.data_cache:
            df, timestamp = self.data_cache[key]
            if (
                datetime.now() - timestamp
            ).total_seconds() < self.cache_ttl and not df.empty:
                return df
        return None

    def _cache_data(self, key: str, df: pd.DataFrame):
        """缓存数据"""
        if len(self.data_cache) >= self.cache_size:
            # 简单清除最旧的缓存
            oldest_key = min(
                self.data_cache.keys(),
                key=lambda k: self.data_cache[k][1],
                default=None,
            )
            if oldest_key:
                del self.data_cache[oldest_key]

        self.data_cache[key] = (df, datetime.now())

    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        return {
            "cache_size": len(self.data_cache),
            "max_cache_size": self.cache_size,
            "cache_ttl": self.cache_ttl,
            "keys": list(self.data_cache.keys()),
        }

    def clear_cache(self):
        """清空缓存"""
        self.data_cache.clear()
        logger.info("历史数据缓存已清空")

    async def update_cache(
        self, symbol: str, exchange: str, interval: str, days: int = 7
    ):
        """更新缓存"""
        logger.info(f"更新{symbol}.{exchange} {interval}数据缓存")
        await self.get_historical_data(
            symbol=symbol,
            exchange=exchange,
            interval=interval,
            days=days,
        )


class DatabaseConnection:
    """数据库连接基类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.is_connected = False

    async def test_connection(self) -> bool:
        """测试连接"""
        raise NotImplementedError

    async def save_kline_data(
        self, df: pd.DataFrame, symbol: str, exchange: str, interval: str
    ) -> bool:
        """保存K线数据"""
        raise NotImplementedError

    async def get_kline_data(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = None,
    ) -> pd.DataFrame:
        """获取K线数据"""
        raise NotImplementedError


class PostgreSQLConnection(DatabaseConnection):
    """PostgreSQL 连接"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.conn = None

    async def test_connection(self) -> bool:
        """测试PostgreSQL连接"""
        try:
            import asyncpg

            self.conn = await asyncpg.connect(
                host=self.config["host"],
                port=self.config["port"],
                database=self.config["database"],
                user=self.config["user"],
                password=self.config["password"],
            )

            # 测试查询
            await self.conn.fetchval("SELECT 1")
            self.is_connected = True
            logger.info("✅ PostgreSQL连接测试成功")
            return True

        except ImportError:
            logger.warning("asyncpg未安装，跳过PostgreSQL连接测试")
            return False
        except Exception as e:
            logger.error(f"PostgreSQL连接失败: {e}")
            self.is_connected = False
            return False

    async def save_kline_data(
        self, df: pd.DataFrame, symbol: str, exchange: str, interval: str
    ) -> bool:
        """保存K线数据到PostgreSQL"""
        try:
            if self.conn is None or self.conn.is_closed():
                await self.test_connection()

            # 准备数据
            records = []
            for _, row in df.iterrows():
                # 确保时间和价格是正确的格式
                datetime_obj = row["datetime"]
                if pd.isna(datetime_obj):
                    continue
                    
                records.append(
                    (
                        datetime_obj,
                        symbol,
                        exchange,
                        interval,
                        float(row["open"]),
                        float(row["high"]),
                        float(row["low"]),
                        float(row["close"]),
                        int(row["volume"]),
                        int(row.get("open_interest", 0)),
                    )
                )

            # 批量插入
            await self.conn.executemany(
                """
                INSERT INTO kline_data 
                (datetime, symbol, exchange, interval, open, high, low, close, volume, open_interest)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (datetime, symbol, exchange, interval) 
                DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    open_interest = EXCLUDED.open_interest
                """,
                records,
            )

            logger.info(
                f"✅ PostgreSQL保存 {len(records)} 条K线数据: {symbol}.{exchange}"
            )
            return True

        except Exception as e:
            logger.error(f"PostgreSQL保存数据失败: {e}")
            return False

    async def get_kline_data(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = None,
    ) -> pd.DataFrame:
        """从PostgreSQL获取K线数据"""
        try:
            if self.conn is None or self.conn.is_closed():
                await self.test_connection()

            # 构建查询
            query = """
                SELECT datetime, open, high, low, close, volume, open_interest
                FROM kline_data
                WHERE symbol = $1 AND exchange = $2 AND interval = $3
            """
            params = [symbol, exchange, interval]

            param_index = 4
            if start_time:
                query += f" AND datetime >= ${param_index}"
                params.append(start_time)
                param_index += 1
            if end_time:
                query += f" AND datetime <= ${param_index}"
                params.append(end_time)
                param_index += 1

            query += " ORDER BY datetime DESC"

            if limit:
                query += f" LIMIT ${param_index}"
                params.append(limit)

            rows = await self.conn.fetch(query, *params)

            if rows:
                # 将 asyncpg.Record 对象转换为字典列表
                data = []
                for row in rows:
                    data.append(
                        {
                            "datetime": row["datetime"],
                            "open": row["open"],
                            "high": row["high"],
                            "low": row["low"],
                            "close": row["close"],
                            "volume": row["volume"],
                            "open_interest": row.get("open_interest", 0),
                        }
                    )

                df = pd.DataFrame(data)
                df["datetime"] = pd.to_datetime(df["datetime"])
                df = df.sort_values("datetime").reset_index(drop=True)
                return df

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"PostgreSQL获取数据失败: {e}")
            return pd.DataFrame()


class InfluxDBConnection(DatabaseConnection):
    """InfluxDB 连接"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = None

    async def test_connection(self) -> bool:
        """测试InfluxDB连接"""
        try:
            from influxdb_client import InfluxDBClient

            self.client = InfluxDBClient(
                url=self.config["url"],
                token=self.config["token"],
                org=self.config["org"],
            )

            # 测试连接
            health = self.client.health()
            self.is_connected = health.status == "pass"

            if self.is_connected:
                logger.info("✅ InfluxDB连接测试成功")
            else:
                logger.warning(f"InfluxDB连接失败: {health.message}")

            return self.is_connected

        except ImportError:
            logger.warning("influxdb-client未安装，跳过InfluxDB连接")
            return False
        except Exception as e:
            logger.warning(f"InfluxDB连接失败: {e}")
            return False

    async def save_kline_data(
        self, df: pd.DataFrame, symbol: str, exchange: str, interval: str
    ) -> bool:
        """保存K线数据到InfluxDB"""
        try:
            from influxdb_client import Point
            from influxdb_client.client.write_api import SYNCHRONOUS

            if not self.client:
                await self.test_connection()

            write_api = self.client.write_api(write_options=SYNCHRONOUS)

            # 转换数据格式
            points = []
            for _, row in df.iterrows():
                point = (
                    Point("kline_data")
                    .tag("symbol", symbol)
                    .tag("exchange", exchange)
                    .tag("interval", interval)
                    .field("open", float(row["open"]))
                    .field("high", float(row["high"]))
                    .field("low", float(row["low"]))
                    .field("close", float(row["close"]))
                    .field("volume", int(row["volume"]))
                )

                if "open_interest" in row and pd.notna(row["open_interest"]):
                    point = point.field("open_interest", int(row["open_interest"]))

                # 确保 InfluxDB 可以正确处理时间戳
                datetime_obj = row["datetime"]
                if hasattr(datetime_obj, "to_pydatetime"):
                    datetime_obj = datetime_obj.to_pydatetime()
                # 处理时区 - 确保使用 UTC 时间
                if datetime_obj.tzinfo is None:
                    import pytz

                    datetime_obj = pytz.UTC.localize(datetime_obj)
                point = point.time(datetime_obj)
                points.append(point)

            write_api.write(bucket=self.config["bucket"], record=points)
            logger.info(f"✅ InfluxDB保存 {len(points)} 条K线数据: {symbol}.{exchange}")
            return True

        except Exception as e:
            logger.error(f"InfluxDB保存数据失败: {e}")
            return False

    async def get_kline_data(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = None,
    ) -> pd.DataFrame:
        """从InfluxDB获取K线数据"""
        try:
            if not self.client:
                await self.test_connection()

            query_api = self.client.query_api()

            # 构建查询
            query = f"""
                from(bucket: "{self.config["bucket"]}")
                |> range(start: {start_time or datetime.now() - timedelta(days=30)}, stop: {end_time or datetime.now()})
                |> filter(fn: (r) => r["_measurement"] == "kline_data")
                |> filter(fn: (r) => r["symbol"] == "{symbol}" and r["exchange"] == "{exchange}" and r["interval"] == "{interval}")
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
            """

            # 执行查询
            result = query_api.query(org=self.config["org"], query=query)
            data = []

            for table in result:
                for record in table.records:
                    data.append(
                        {
                            "datetime": record.get_time(),
                            "open": record.get_value("open"),
                            "high": record.get_value("high"),
                            "low": record.get_value("low"),
                            "close": record.get_value("close"),
                            "volume": record.get_value("volume"),
                            "open_interest": record.get_value("open_interest", 0),
                        }
                    )

            if data:
                df = pd.DataFrame(data)
                df["datetime"] = pd.to_datetime(df["datetime"])
                df = df.sort_values("datetime").reset_index(drop=True)
                return df
            else:
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"InfluxDB获取数据失败: {e}")
            return pd.DataFrame()