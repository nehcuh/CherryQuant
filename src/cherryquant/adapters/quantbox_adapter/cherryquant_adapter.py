"""
CherryQuant-QuantBox 桥接适配器

将 QuantBox 的高性能数据管理功能集成到 CherryQuant 中
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
import pandas as pd

from quantbox.services import MarketDataService, AsyncMarketDataService
from quantbox.services import DataSaverService, AsyncDataSaverService

from ..data_storage.timeframe_data_manager import TimeFrame, MarketDataPoint, TechnicalIndicators

logger = logging.getLogger(__name__)


class CherryQuantQuantBoxAdapter:
    """
    CherryQuant-QuantBox 桥接适配器

    提供：
    1. 统一的数据获取接口
    2. 异步高性能数据操作
    3. 智能缓存和数据源选择
    4. 与现有 CherryQuant 架构的无缝集成
    """

    def __init__(
        self,
        use_async: bool = True,
        auto_warm: bool = True,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化适配器

        Args:
            use_async: 是否使用异步服务（推荐）
            auto_warm: 是否自动预热缓存
            config: 配置参数
        """
        self.use_async = use_async
        self.config = config or {}

        # 初始化 QuantBox 服务
        if use_async:
            self.market_service = AsyncMarketDataService()
            self.saver_service = AsyncDataSaverService()
        else:
            self.market_service = MarketDataService()
            self.saver_service = DataSaverService()

        # 缓存预热
        if auto_warm:
            self._warm_caches()

    def _warm_caches(self):
        """预热 QuantBox 缓存"""
        try:
            import quantbox
            stats = quantbox.init(auto_warm=True, warm_verbose=False)
            logger.info(f"QuantBox 缓存预热完成，耗时: {stats['total_time']:.3f}s")
        except Exception as e:
            logger.warning(f"QuantBox 缓存预热失败: {e}")

    # ==================== 交易日历相关 ====================

    async def get_trade_calendar_async(
        self,
        exchanges: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        异步获取交易日历

        Args:
            exchanges: 交易所代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            交易日历 DataFrame
        """
        try:
            if not self.use_async:
                # 如果是同步服务，在线程池中运行
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    self.market_service.get_trade_calendar,
                    exchanges, start_date, end_date
                )

            return await self.market_service.get_trade_calendar(
                exchanges=exchanges,
                start_date=start_date,
                end_date=end_date
            )
        except Exception as e:
            logger.error(f"获取交易日历失败: {e}")
            return pd.DataFrame()

    def get_trade_calendar(
        self,
        exchanges: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        同步获取交易日历

        Args:
            exchanges: 交易所代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            交易日历 DataFrame
        """
        if self.use_async:
            return asyncio.run(self.get_trade_calendar_async(
                exchanges=exchanges,
                start_date=start_date,
                end_date=end_date
            ))
        else:
            return self.market_service.get_trade_calendar(
                exchanges=exchanges,
                start_date=start_date,
                end_date=end_date
            )

    # ==================== 期货合约相关 ====================

    async def get_future_contracts_async(
        self,
        exchanges: Optional[Union[str, List[str]]] = None,
        date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        异步获取期货合约信息

        Args:
            exchanges: 交易所代码
            date: 查询日期

        Returns:
            期货合约信息 DataFrame
        """
        try:
            if not self.use_async:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    self.market_service.get_future_contracts,
                    exchanges, date
                )

            return await self.market_service.get_future_contracts(
                exchanges=exchanges,
                date=date
            )
        except Exception as e:
            logger.error(f"获取期货合约信息失败: {e}")
            return pd.DataFrame()

    def get_future_contracts(
        self,
        exchanges: Optional[Union[str, List[str]]] = None,
        date: Optional[str] = None,
    ) -> pd.DataFrame:
        """同步获取期货合约信息"""
        if self.use_async:
            return asyncio.run(self.get_future_contracts_async(
                exchanges=exchanges,
                date=date
            ))
        else:
            return self.market_service.get_future_contracts(
                exchanges=exchanges,
                date=date
            )

    # ==================== 期货日线数据相关 ====================

    async def get_future_daily_async(
        self,
        symbols: Optional[Union[str, List[str]]] = None,
        exchanges: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        异步获取期货日线数据

        Args:
            symbols: 合约代码
            exchanges: 交易所代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            期货日线数据 DataFrame
        """
        try:
            if not self.use_async:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    self.market_service.get_future_daily,
                    symbols, exchanges, start_date, end_date
                )

            return await self.market_service.get_future_daily(
                symbols=symbols,
                exchanges=exchanges,
                start_date=start_date,
                end_date=end_date
            )
        except Exception as e:
            logger.error(f"获取期货日线数据失败: {e}")
            return pd.DataFrame()

    def get_future_daily(
        self,
        symbols: Optional[Union[str, List[str]]] = None,
        exchanges: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """同步获取期货日线数据"""
        if self.use_async:
            return asyncio.run(self.get_future_daily_async(
                symbols=symbols,
                exchanges=exchanges,
                start_date=start_date,
                end_date=end_date
            ))
        else:
            return self.market_service.get_future_daily(
                symbols=symbols,
                exchanges=exchanges,
                start_date=start_date,
                end_date=end_date
            )

    # ==================== 数据保存相关 ====================

    async def save_trade_calendar_async(
        self,
        exchanges: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        异步保存交易日历

        Args:
            exchanges: 交易所代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            保存结果
        """
        try:
            if not self.use_async:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    self.saver_service.save_trade_calendar,
                    exchanges, start_date, end_date
                )

            return await self.saver_service.save_trade_calendar(
                exchanges=exchanges,
                start_date=start_date,
                end_date=end_date
            )
        except Exception as e:
            logger.error(f"保存交易日历失败: {e}")
            return {"success": False, "error": str(e)}

    def save_trade_calendar(
        self,
        exchanges: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """同步保存交易日历"""
        if self.use_async:
            return asyncio.run(self.save_trade_calendar_async(
                exchanges=exchanges,
                start_date=start_date,
                end_date=end_date
            ))
        else:
            return self.saver_service.save_trade_calendar(
                exchanges=exchanges,
                start_date=start_date,
                end_date=end_date
            )

    # ==================== 数据格式转换 ====================

    def quantbox_to_cherryquant_data(self, df: pd.DataFrame) -> List[MarketDataPoint]:
        """
        将 QuantBox 数据格式转换为 CherryQuant 格式

        Args:
            df: QuantBox 数据 DataFrame

        Returns:
            CherryQuant MarketDataPoint 列表
        """
        data_points = []

        if df.empty:
            return data_points

        try:
            # 处理不同的数据结构
            required_columns = ['open', 'high', 'low', 'close']
            if not all(col in df.columns for col in required_columns):
                logger.warning(f"数据缺少必要列: {required_columns}")
                return data_points

            # 获取时间列（可能是不同名称）
            time_col = 'datetime'
            if time_col not in df.columns:
                time_col = 'date'
                if time_col not in df.columns:
                    time_col = 'time'
                    if time_col not in df.columns:
                        time_col = df.index.name or 'index'

            # 获取成交量列
            volume_col = 'volume'
            if volume_col not in df.columns:
                volume_col = 'vol'
                if volume_col not in df.columns:
                    volume_col = 'amount'

            for _, row in df.iterrows():
                timestamp = row[time_col] if time_col in row else row.name
                if not isinstance(timestamp, datetime):
                    timestamp = pd.to_datetime(timestamp)

                point = MarketDataPoint(
                    timestamp=timestamp,
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=int(row.get(volume_col, 0)),
                    open_interest=int(row.get('oi', row.get('open_interest', 0))),
                    turnover=float(row.get('turnover', 0.0))
                )
                data_points.append(point)

            return data_points

        except Exception as e:
            logger.error(f"数据格式转换失败: {e}")
            return data_points

    # ==================== 性能和状态 ====================

    def get_adapter_info(self) -> Dict[str, Any]:
        """
        获取适配器信息

        Returns:
            适配器状态信息
        """
        return {
            "adapter_type": "CherryQuant-QuantBox Bridge",
            "use_async": self.use_async,
            "quantbox_version": "0.2.0",
            "features": [
                "智能数据源选择（本地优先）",
                "异步高性能操作",
                "缓存预热系统",
                "多数据源支持（Tushare、掘金量化、MongoDB）",
                "批量操作和去重优化"
            ],
            "supported_data_types": [
                "交易日历",
                "期货合约信息",
                "期货日线数据",
                "期货持仓数据"
            ]
        }

    async def test_connection(self) -> bool:
        """
        测试 QuantBox 连接

        Returns:
            是否连接成功
        """
        try:
            # 尝试获取少量数据来测试连接
            test_data = await self.get_trade_calendar_async(
                exchanges=["SHFE"],
                start_date="2024-01-01",
                end_date="2024-01-05"
            )
            return not test_data.empty
        except Exception as e:
            logger.error(f"QuantBox 连接测试失败: {e}")
            return False

    def close(self):
        """关闭适配器资源"""
        try:
            if hasattr(self.market_service, 'close'):
                self.market_service.close()
            if hasattr(self.saver_service, 'close'):
                self.saver_service.close()
            logger.info("QuantBox 适配器已关闭")
        except Exception as e:
            logger.error(f"关闭 QuantBox 适配器失败: {e}")