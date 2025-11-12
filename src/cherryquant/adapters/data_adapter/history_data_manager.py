"""
历史数据管理器 - QuantBox 增强版
用于获取和存储期货历史K线数据
集成 QuantBox 高性能数据管理系统
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import pandas as pd

logger = logging.getLogger(__name__)

try:
    # 导入 QuantBox 适配器
    from ..quantbox_adapter.cherryquant_adapter import CherryQuantQuantBoxAdapter
    from ..quantbox_adapter.data_bridge import DataBridge
    QUANTBOX_AVAILABLE = True
except ImportError:
    logger.warning("QuantBox 不可用，将使用原始实现")
    QUANTBOX_AVAILABLE = False
    CherryQuantQuantBoxAdapter = None
    DataBridge = None


class HistoryDataManager:
    """历史数据管理器 - QuantBox 增强版"""

    def __init__(
        self,
        cache_size: int = 1000,
        cache_ttl: int = 3600,
        enable_quantbox: bool = True,
        use_async: bool = True,
        enable_dual_write: bool = False
    ):
        """
        初始化历史数据管理器

        Args:
            cache_size: 缓存大小
            cache_ttl: 缓存TTL（秒）
            enable_quantbox: 是否启用 QuantBox 集成
            use_async: 是否使用异步操作
            enable_dual_write: 是否启用双写机制
        """
        self.cache_size = cache_size
        self.cache_ttl = cache_ttl
        self.data_cache = {}

        # QuantBox 集成配置
        self.enable_quantbox = enable_quantbox and QUANTBOX_AVAILABLE
        self.use_async = use_async
        self.enable_dual_write = enable_dual_write

        # 初始化 QuantBox 组件
        if self.enable_quantbox:
            try:
                self.quantbox_adapter = CherryQuantQuantBoxAdapter(
                    use_async=self.use_async,
                    auto_warm=True
                )
                self.data_bridge = DataBridge(
                    adapter=self.quantbox_adapter,
                    enable_dual_write=self.enable_dual_write,
                    cache_ttl=self.cache_ttl
                )
                logger.info("✅ QuantBox 集成已启用")
            except Exception as e:
                logger.error(f"❌ QuantBox 初始化失败: {e}")
                self.enable_quantbox = False

        # 保留原始数据库连接作为后备
        if not self.enable_quantbox or self.enable_dual_write:
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



    async def get_historical_data(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        start_date: str = None,
        end_date: str = None,
        days: int = 30,
        prefer_quantbox: bool = True
    ) -> pd.DataFrame:
        """
        获取历史数据 - QuantBox 增强版

        Args:
            symbol: 期货合约代码
            exchange: 交易所
            interval: 时间间隔
            start_date: 开始日期
            end_date: 结束日期
            days: 获取天数
            prefer_quantbox: 优先使用 QuantBox（默认 True）

        Returns:
            历史数据DataFrame
        """
        # 解析日期参数
        start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else datetime.now() - timedelta(days=days)
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()

        # 先从缓存获取
        cache_key = f"{symbol}_{exchange}_{interval}_{start_date}_{end_date}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data is not None:
            logger.debug(f"从缓存获取历史数据: {cache_key}")
            return cached_data

        # 选择数据源策略
        if prefer_quantbox and self.enable_quantbox:
            return await self._get_from_quantbox(
                symbol, exchange, interval, start_dt, end_dt, cache_key
            )
        else:
            return await self._get_from_legacy_system(
                symbol, exchange, interval, start_date, end_date, days, cache_key
            )

    async def _get_from_quantbox(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        start_dt: datetime,
        end_dt: datetime,
        cache_key: str
    ) -> pd.DataFrame:
        """从 QuantBox 获取数据"""
        try:
            logger.info(f"使用 QuantBox 获取历史数据: {symbol}.{exchange} {interval}")

            # 使用数据桥接器获取数据
            data_points = await self.data_bridge.get_kline_data(
                symbol=symbol,
                exchange=exchange,
                interval=interval,
                start_time=start_dt,
                end_time=end_dt
            )

            if not data_points:
                logger.warning(f"QuantBox 未获取到数据，回退到传统系统")
                return await self._get_from_legacy_system(
                    symbol, exchange, interval,
                    start_dt.strftime("%Y-%m-%d"),
                    end_dt.strftime("%Y-%m-%d"),
                    (end_dt - start_dt).days,
                    cache_key
                )

            # 转换为 DataFrame
            df = self._data_points_to_dataframe(data_points)

            # 缓存数据
            self._cache_data(cache_key, df)

            # 双写机制：同时保存到传统数据库
            if self.enable_dual_write:
                await self._save_to_databases(df, symbol, exchange, interval)

            logger.info(f"✅ QuantBox 获取历史数据成功: {len(df)}条记录")
            return df

        except Exception as e:
            logger.error(f"❌ QuantBox 获取数据失败: {e}")
            # 回退到传统系统
            return await self._get_from_legacy_system(
                symbol, exchange, interval,
                start_dt.strftime("%Y-%m-%d"),
                end_dt.strftime("%Y-%m-%d"),
                (end_dt - start_dt).days,
                cache_key
            )

    async def _get_from_legacy_system(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        start_date: str,
        end_date: str,
        days: int,
        cache_key: str
    ) -> pd.DataFrame:
        """从传统系统获取数据"""
        try:
            logger.info(f"使用传统系统获取历史数据: {symbol}.{exchange} {interval}")

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

        except Exception as e:
            logger.error(f"传统系统获取数据失败: {e}")
            return pd.DataFrame()

    def _data_points_to_dataframe(self, data_points: List) -> pd.DataFrame:
        """将数据点列表转换为 DataFrame"""
        if not data_points:
            return pd.DataFrame()

        try:
            data = []
            for point in data_points:
                data.append({
                    'datetime': point.timestamp,
                    'open': point.open,
                    'high': point.high,
                    'low': point.low,
                    'close': point.close,
                    'volume': point.volume,
                    'open_interest': point.open_interest
                })

            df = pd.DataFrame(data)
            df['datetime'] = pd.to_datetime(df['datetime'])
            return df.sort_values('datetime').reset_index(drop=True)

        except Exception as e:
            logger.error(f"数据点转换为 DataFrame 失败: {e}")
            return pd.DataFrame()

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
                from cherryquant.adapters.data_adapter.market_data_manager import TushareDataSource
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
        """获取缓存信息 - 增强版"""
        cache_info = {
            "cache_size": len(self.data_cache),
            "max_cache_size": self.cache_size,
            "cache_ttl": self.cache_ttl,
            "keys": list(self.data_cache.keys()),
        }

        # 添加 QuantBox 缓存信息
        if self.enable_quantbox:
            cache_info.update({
                "quantbox_enabled": True,
                "quantbox_cache": self.data_bridge.get_cache_status() if hasattr(self, 'data_bridge') else {},
                "adapter_info": self.quantbox_adapter.get_adapter_info() if hasattr(self, 'quantbox_adapter') else {}
            })
        else:
            cache_info["quantbox_enabled"] = False

        return cache_info

    # ==================== 新增功能方法 ====================

    async def get_contract_info(self, symbol: str, exchange: str) -> Dict[str, Any]:
        """
        获取合约信息

        Args:
            symbol: 合约代码
            exchange: 交易所

        Returns:
            合约信息字典
        """
        if self.enable_quantbox:
            try:
                return await self.data_bridge.get_contract_info(symbol, exchange)
            except Exception as e:
                logger.error(f"获取合约信息失败: {e}")
                return {}
        return {}

    async def is_trading_day(self, date: datetime, exchange: str = "SHFE") -> bool:
        """
        检查是否为交易日

        Args:
            date: 日期
            exchange: 交易所

        Returns:
            是否为交易日
        """
        if self.enable_quantbox:
            try:
                return await self.data_bridge.is_trading_day(date, exchange)
            except Exception as e:
                logger.error(f"检查交易日失败: {e}")
                return False
        return True  # 默认返回 True

    async def batch_get_historical_data(
        self,
        requests: List[Dict[str, Any]],
        prefer_quantbox: bool = True
    ) -> Dict[str, pd.DataFrame]:
        """
        批量获取历史数据

        Args:
            requests: 请求列表，每个请求包含symbol、exchange、interval等参数
            prefer_quantbox: 优先使用 QuantBox

        Returns:
            批量数据结果
        """
        results = {}

        if self.enable_quantbox and prefer_quantbox:
            try:
                # 使用 QuantBox 批量获取
                batch_requests = []
                request_keys = []

                for req in requests:
                    batch_requests.append({
                        'symbol': req.get('symbol'),
                        'exchange': req.get('exchange'),
                        'interval': req.get('interval'),
                        'start_time': datetime.strptime(req['start_date'], "%Y-%m-%d") if req.get('start_date') else None,
                        'end_time': datetime.strptime(req['end_date'], "%Y-%m-%d") if req.get('end_date') else None,
                        'limit': req.get('limit')
                    })
                    request_keys.append(f"{req.get('symbol')}.{req.get('exchange')}.{req.get('interval')}")

                data_points_dict = await self.data_bridge.batch_get_kline_data(batch_requests)

                # 转换为 DataFrame
                for key, data_points in data_points_dict.items():
                    results[key] = self._data_points_to_dataframe(data_points)

            except Exception as e:
                logger.error(f"批量获取数据失败，回退到单独获取: {e}")

        # 回退到单独获取
        for req in requests:
            key = f"{req.get('symbol')}.{req.get('exchange')}.{req.get('interval')}"
            if key not in results:
                df = await self.get_historical_data(
                    symbol=req.get('symbol'),
                    exchange=req.get('exchange'),
                    interval=req.get('interval'),
                    start_date=req.get('start_date'),
                    end_date=req.get('end_date'),
                    prefer_quantbox=prefer_quantbox
                )
                results[key] = df

        return results

    async def test_quantbox_connection(self) -> bool:
        """
        测试 QuantBox 连接

        Returns:
            是否连接成功
        """
        if not self.enable_quantbox:
            return False

        try:
            return await self.quantbox_adapter.test_connection()
        except Exception as e:
            logger.error(f"测试 QuantBox 连接失败: {e}")
            return False

    def get_system_status(self) -> Dict[str, Any]:
        """
        获取系统状态

        Returns:
            系统状态信息
        """
        status = {
            "history_data_manager": "正常",
            "cache_system": "正常" if self.data_cache else "空",
            "database_connections": []
        }

        # 检查数据库连接
        if hasattr(self, 'connections'):
            for db_name, connection in self.connections.items():
                try:
                    is_connected = connection.is_connected
                    status["database_connections"].append({
                        "name": db_name,
                        "status": "已连接" if is_connected else "未连接"
                    })
                except:
                    status["database_connections"].append({
                        "name": db_name,
                        "status": "错误"
                    })

        # 添加 QuantBox 状态
        if self.enable_quantbox:
            status.update({
                "quantbox_integration": "已启用",
                "quantbox_adapter": "正常",
                "data_bridge": "正常"
            })
        else:
            status.update({
                "quantbox_integration": "未启用",
                "reason": "QuantBox 不可用或被禁用"
            })

        return status

    def clear_all_caches(self):
        """清空所有缓存"""
        # 清空本地缓存
        self.data_cache.clear()
        logger.info("本地缓存已清空")

        # 清空 QuantBox 缓存
        if self.enable_quantbox and hasattr(self, 'data_bridge'):
            self.data_bridge.clear_cache()
            logger.info("QuantBox 缓存已清空")

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
