"""
批量查询执行器

提供高效的批量查询功能，通过并发控制和连接池优化性能。

教学要点：
1. 批量操作模式
2. 并发控制（Semaphore）
3. 连接池管理
4. 性能优化策略
"""

import asyncio
import logging
from typing import Any, Callable
from datetime import datetime
from dataclasses import dataclass

from cherryquant.data.collectors.base_collector import MarketData, Exchange, TimeFrame
from cherryquant.data.storage.timeseries_repository import TimeSeriesRepository

logger = logging.getLogger(__name__)


@dataclass
class BatchQueryRequest:
    """批量查询请求"""
    symbol: str
    exchange: Exchange
    start_date: datetime
    end_date: datetime
    timeframe: TimeFrame = TimeFrame.DAY_1
    filters: list[Callable | None] = None


@dataclass
class BatchQueryResult:
    """批量查询结果"""
    request: BatchQueryRequest
    data: list[MarketData]
    success: bool
    error: str | None = None
    execution_time: float = 0.0  # 秒


class BatchQueryExecutor:
    """
    批量查询执行器

    提供高效的批量查询功能。

    教学要点：
    1. 并发控制策略
    2. 资源池管理
    3. 错误处理和降级
    4. 性能监控
    """

    def __init__(
        self,
        repository: TimeSeriesRepository,
        max_concurrency: int = 10,
        timeout: float = 30.0,
    ):
        """
        初始化批量查询执行器

        Args:
            repository: 时间序列仓储
            max_concurrency: 最大并发数
            timeout: 单个查询超时时间（秒）

        教学要点：
        1. 并发参数配置
        2. 超时控制
        """
        self.repository = repository
        self.max_concurrency = max_concurrency
        self.timeout = timeout

        # 统计信息
        self.stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "total_time": 0.0,
        }

    async def execute_batch(
        self,
        requests: list[BatchQueryRequest],
    ) -> list[BatchQueryResult]:
        """
        执行批量查询

        Args:
            requests: 查询请求列表

        Returns:
            list[BatchQueryResult]: 查询结果列表

        教学要点：
        1. 信号量控制并发
        2. 批量操作模式
        3. 错误隔离（一个失败不影响其他）
        """
        logger.info(f"📦 开始批量查询: {len(requests)} 个请求")

        start_time = datetime.now()

        # 创建信号量控制并发
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def execute_one(request: BatchQueryRequest) -> BatchQueryResult:
            """执行单个查询"""
            async with semaphore:
                return await self._execute_single(request)

        # 并发执行所有查询
        results = await asyncio.gather(
            *[execute_one(req) for req in requests],
            return_exceptions=True,
        )

        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # 查询失败，创建错误结果
                processed_results.append(
                    BatchQueryResult(
                        request=requests[i],
                        data=[],
                        success=False,
                        error=str(result),
                    )
                )
            else:
                processed_results.append(result)

        # 更新统计
        elapsed = (datetime.now() - start_time).total_seconds()
        self.stats["total_queries"] += len(requests)
        self.stats["successful_queries"] += sum(
            1 for r in processed_results if r.success
        )
        self.stats["failed_queries"] += sum(
            1 for r in processed_results if not r.success
        )
        self.stats["total_time"] += elapsed

        logger.info(
            f"✅ 批量查询完成: {self.stats['successful_queries']}/{len(requests)} 成功, "
            f"耗时 {elapsed:.2f}s"
        )

        return processed_results

    async def _execute_single(
        self,
        request: BatchQueryRequest,
    ) -> BatchQueryResult:
        """
        执行单个查询

        教学要点：
        1. 超时控制
        2. 错误处理
        3. 性能监控
        """
        start_time = datetime.now()

        try:
            # 执行查询（带超时）
            data = await asyncio.wait_for(
                self.repository.query(
                    symbol=request.symbol,
                    exchange=request.exchange,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    timeframe=request.timeframe,
                ),
                timeout=self.timeout,
            )

            # 应用过滤器（如果有）
            if request.filters:
                for filter_func in request.filters:
                    data = [d for d in data if filter_func(d)]

            execution_time = (datetime.now() - start_time).total_seconds()

            return BatchQueryResult(
                request=request,
                data=data,
                success=True,
                execution_time=execution_time,
            )

        except asyncio.TimeoutError:
            logger.warning(
                f"⚠️ 查询超时: {request.symbol}.{request.exchange.value}"
            )
            return BatchQueryResult(
                request=request,
                data=[],
                success=False,
                error="Timeout",
                execution_time=self.timeout,
            )

        except Exception as e:
            logger.error(
                f"❌ 查询失败: {request.symbol}.{request.exchange.value} - {e}"
            )
            execution_time = (datetime.now() - start_time).total_seconds()

            return BatchQueryResult(
                request=request,
                data=[],
                success=False,
                error=str(e),
                execution_time=execution_time,
            )

    async def execute_symbols(
        self,
        symbols: list[str],
        exchange: Exchange,
        start_date: datetime,
        end_date: datetime,
        timeframe: TimeFrame = TimeFrame.DAY_1,
    ) -> dict[str, list[MarketData]]:
        """
        批量查询多个合约的数据

        Args:
            symbols: 合约代码列表
            exchange: 交易所
            start_date: 开始日期
            end_date: 结束日期
            timeframe: 时间周期

        Returns:
            dict[str, list[MarketData]]: symbol -> 数据列表的映射

        教学要点：
        1. 便捷方法封装
        2. 结果映射
        """
        # 构建请求
        requests = [
            BatchQueryRequest(
                symbol=symbol,
                exchange=exchange,
                start_date=start_date,
                end_date=end_date,
                timeframe=timeframe,
            )
            for symbol in symbols
        ]

        # 执行批量查询
        results = await self.execute_batch(requests)

        # 映射结果
        return {
            result.request.symbol: result.data
            for result in results
            if result.success
        }

    async def execute_timeframes(
        self,
        symbol: str,
        exchange: Exchange,
        start_date: datetime,
        end_date: datetime,
        timeframes: list[TimeFrame],
    ) -> dict[TimeFrame, list[MarketData]]:
        """
        批量查询同一合约的多个时间周期

        Returns:
            dict[TimeFrame, list[MarketData]]: timeframe -> 数据列表的映射

        教学要点：
        1. 多维度查询
        2. 结果组织
        """
        # 构建请求
        requests = [
            BatchQueryRequest(
                symbol=symbol,
                exchange=exchange,
                start_date=start_date,
                end_date=end_date,
                timeframe=timeframe,
            )
            for timeframe in timeframes
        ]

        # 执行批量查询
        results = await self.execute_batch(requests)

        # 映射结果
        return {
            result.request.timeframe: result.data
            for result in results
            if result.success
        }

    def get_stats(self) -> dict[str, Any]:
        """
        获取统计信息

        教学要点：
        1. 性能指标计算
        2. 监控数据收集
        """
        total = self.stats["total_queries"]
        successful = self.stats["successful_queries"]
        failed = self.stats["failed_queries"]
        total_time = self.stats["total_time"]

        return {
            "total_queries": total,
            "successful_queries": successful,
            "failed_queries": failed,
            "success_rate": f"{successful / total * 100:.2f}%" if total > 0 else "N/A",
            "total_time": f"{total_time:.2f}s",
            "avg_time_per_query": f"{total_time / total:.3f}s" if total > 0 else "N/A",
        }

    def print_stats(self) -> None:
        """打印统计信息"""
        stats = self.get_stats()

        print("\n" + "=" * 60)
        print("批量查询统计")
        print("=" * 60)
        print(f"总查询数: {stats['total_queries']}")
        print(f"成功: {stats['successful_queries']}")
        print(f"失败: {stats['failed_queries']}")
        print(f"成功率: {stats['success_rate']}")
        print(f"总耗时: {stats['total_time']}")
        print(f"平均耗时: {stats['avg_time_per_query']}")
        print("=" * 60 + "\n")

    def reset_stats(self) -> None:
        """重置统计信息"""
        self.stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "total_time": 0.0,
        }
        logger.info("📊 批量查询统计已重置")
