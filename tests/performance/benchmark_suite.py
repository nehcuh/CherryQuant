#!/usr/bin/env python3
"""
性能基准测试套件

测试新数据管道的性能，并与旧系统对比。

运行方式：
    python tests/performance/benchmark_suite.py
"""

import asyncio
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
from decimal import Decimal
import statistics

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cherryquant.data.pipeline import DataPipeline
from cherryquant.data.collectors.tushare_collector import TushareCollector
from cherryquant.data.collectors.base_collector import Exchange, TimeFrame
from cherryquant.data.query.query_builder import QueryBuilder
from cherryquant.data.query.batch_query import BatchQueryExecutor, BatchQueryRequest
from cherryquant.adapters.data_storage.mongodb_manager import MongoDBConnectionManager


class BenchmarkSuite:
    """性能基准测试套件"""

    def __init__(self, pipeline: DataPipeline):
        self.pipeline = pipeline
        self.results: Dict[str, List[float]] = {}

    async def setup(self):
        """测试准备"""
        print("\n" + "=" * 60)
        print("性能基准测试套件")
        print("=" * 60)
        print("\n📦 初始化测试环境...")

        await self.pipeline.initialize()

        # 确保有测试数据
        print("📊 准备测试数据...")
        await self._prepare_test_data()

        print("✅ 测试环境就绪\n")

    async def teardown(self):
        """清理"""
        print("\n🛑 清理测试环境...")
        await self.pipeline.shutdown()

    async def _prepare_test_data(self):
        """准备测试数据"""
        # 确保有 rb2501 的30天数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        count = await self.pipeline.timeseries_repo.count(
            symbol="rb2501",
            exchange=Exchange.SHFE,
            timeframe=TimeFrame.DAY_1,
            start_date=start_date,
            end_date=end_date,
        )

        if count < 20:
            print(f"  数据不足({count}条)，开始采集...")
            await self.pipeline.collect_and_store_market_data(
                symbol="rb2501",
                exchange=Exchange.SHFE,
                start_date=start_date,
                end_date=end_date,
                timeframe=TimeFrame.DAY_1,
            )
        else:
            print(f"  数据充足({count}条)")

    def _record_time(self, test_name: str, elapsed: float):
        """记录测试时间"""
        if test_name not in self.results:
            self.results[test_name] = []
        self.results[test_name].append(elapsed)

    async def _run_benchmark(
        self,
        name: str,
        func: callable,
        iterations: int = 10,
    ) -> Dict[str, Any]:
        """
        运行单个基准测试

        Args:
            name: 测试名称
            func: 测试函数
            iterations: 迭代次数

        Returns:
            测试统计信息
        """
        print(f"  🧪 {name}...")

        times = []

        for i in range(iterations):
            start = time.time()
            await func()
            elapsed = time.time() - start
            times.append(elapsed)
            self._record_time(name, elapsed)

        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        std_dev = statistics.stdev(times) if len(times) > 1 else 0

        print(f"    平均: {avg_time*1000:.2f}ms, 最小: {min_time*1000:.2f}ms, 最大: {max_time*1000:.2f}ms")

        return {
            "avg": avg_time,
            "min": min_time,
            "max": max_time,
            "std": std_dev,
            "times": times,
        }

    # ==================== 基准测试 ====================

    async def test_simple_query(self):
        """测试1: 简单查询性能"""
        print("\n📊 测试1: 简单查询性能")

        async def query_func():
            data = await self.pipeline.get_market_data(
                symbol="rb2501",
                exchange=Exchange.SHFE,
                start_date=datetime.now() - timedelta(days=7),
                end_date=datetime.now(),
                timeframe=TimeFrame.DAY_1,
                use_cache=False,  # 禁用缓存测试真实查询性能
            )
            return len(data)

        stats = await self._run_benchmark("simple_query", query_func)
        return stats

    async def test_cached_query(self):
        """测试2: 缓存查询性能"""
        print("\n📊 测试2: 缓存查询性能")

        # 先执行一次填充缓存
        await self.pipeline.get_market_data(
            symbol="rb2501",
            exchange=Exchange.SHFE,
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now(),
            timeframe=TimeFrame.DAY_1,
            use_cache=True,
        )

        async def query_func():
            data = await self.pipeline.get_market_data(
                symbol="rb2501",
                exchange=Exchange.SHFE,
                start_date=datetime.now() - timedelta(days=7),
                end_date=datetime.now(),
                timeframe=TimeFrame.DAY_1,
                use_cache=True,  # 启用缓存
            )
            return len(data)

        stats = await self._run_benchmark("cached_query", query_func)
        return stats

    async def test_query_builder(self):
        """测试3: QueryBuilder 性能"""
        print("\n📊 测试3: QueryBuilder 复杂查询性能")

        async def query_func():
            query = (QueryBuilder(self.pipeline.timeseries_repo)
                .symbol("rb2501")
                .exchange(Exchange.SHFE)
                .date_range(
                    datetime.now() - timedelta(days=30),
                    datetime.now()
                )
                .timeframe(TimeFrame.DAY_1)
                .volume_greater_than(10000)
                .price_range(min_price=Decimal("3000"), max_price=Decimal("4000"))
                .limit(20)
            )
            data = await query.execute()
            return len(data)

        stats = await self._run_benchmark("query_builder", query_func)
        return stats

    async def test_batch_query(self):
        """测试4: 批量查询性能"""
        print("\n📊 测试4: 批量查询性能")

        executor = BatchQueryExecutor(
            repository=self.pipeline.timeseries_repo,
            max_concurrency=5,
        )

        async def query_func():
            requests = [
                BatchQueryRequest(
                    symbol="rb2501",
                    exchange=Exchange.SHFE,
                    start_date=datetime.now() - timedelta(days=7),
                    end_date=datetime.now(),
                    timeframe=TimeFrame.DAY_1,
                )
                for _ in range(10)
            ]

            results = await executor.execute_batch(requests)
            return len(results)

        stats = await self._run_benchmark("batch_query", query_func, iterations=5)
        return stats

    async def test_data_collection(self):
        """测试5: 数据采集性能"""
        print("\n📊 测试5: 数据采集和存储性能")

        async def collect_func():
            # 采集最近3天的数据
            result = await self.pipeline.collect_and_store_market_data(
                symbol="rb2501",
                exchange=Exchange.SHFE,
                start_date=datetime.now() - timedelta(days=3),
                end_date=datetime.now(),
                timeframe=TimeFrame.DAY_1,
                skip_validation=False,
            )
            return result['stored_count']

        stats = await self._run_benchmark("data_collection", collect_func, iterations=3)
        return stats

    async def test_aggregation(self):
        """测试6: 聚合查询性能"""
        print("\n📊 测试6: 聚合查询性能")

        async def agg_func():
            query = (QueryBuilder(self.pipeline.timeseries_repo)
                .symbol("rb2501")
                .exchange(Exchange.SHFE)
                .date_range(
                    datetime.now() - timedelta(days=30),
                    datetime.now()
                )
                .timeframe(TimeFrame.DAY_1)
            )

            avg_price = await query.avg_price()
            max_price = await query.max_price()
            min_price = await query.min_price()
            total_vol = await query.total_volume()

            return avg_price, max_price, min_price, total_vol

        stats = await self._run_benchmark("aggregation", agg_func)
        return stats

    # ==================== 运行所有测试 ====================

    async def run_all(self) -> Dict[str, Any]:
        """运行所有基准测试"""
        await self.setup()

        all_stats = {}

        try:
            # 运行所有测试
            all_stats['simple_query'] = await self.test_simple_query()
            all_stats['cached_query'] = await self.test_cached_query()
            all_stats['query_builder'] = await self.test_query_builder()
            all_stats['batch_query'] = await self.test_batch_query()
            all_stats['data_collection'] = await self.test_data_collection()
            all_stats['aggregation'] = await self.test_aggregation()

            # 打印总结
            self.print_summary(all_stats)

        finally:
            await self.teardown()

        return all_stats

    def print_summary(self, all_stats: Dict[str, Any]):
        """打印测试总结"""
        print("\n" + "=" * 60)
        print("性能测试总结")
        print("=" * 60)

        for test_name, stats in all_stats.items():
            print(f"\n{test_name}:")
            print(f"  平均时间: {stats['avg']*1000:.2f} ms")
            print(f"  最小时间: {stats['min']*1000:.2f} ms")
            print(f"  最大时间: {stats['max']*1000:.2f} ms")
            print(f"  标准差: {stats['std']*1000:.2f} ms")

        # 性能对比
        print("\n" + "=" * 60)
        print("性能对比")
        print("=" * 60)

        if 'simple_query' in all_stats and 'cached_query' in all_stats:
            speedup = all_stats['simple_query']['avg'] / all_stats['cached_query']['avg']
            print(f"\n缓存加速比: {speedup:.2f}x")
            print(f"  无缓存: {all_stats['simple_query']['avg']*1000:.2f} ms")
            print(f"  有缓存: {all_stats['cached_query']['avg']*1000:.2f} ms")

        print("\n" + "=" * 60)

        # 显示缓存统计
        if self.pipeline.cache:
            print("\n缓存统计:")
            self.pipeline.cache.print_stats()


async def main():
    """主函数"""
    # 检查环境变量
    if not os.getenv("TUSHARE_TOKEN"):
        print("\n⚠️  请先设置环境变量:")
        print("export TUSHARE_TOKEN=your_token_here")
        return

    # 初始化数据管道
    db_manager = MongoDBConnectionManager(
        uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        database=os.getenv("MONGODB_DATABASE", "cherryquant"),
    )

    collector = TushareCollector(token=os.getenv("TUSHARE_TOKEN"))

    pipeline = DataPipeline(
        collector=collector,
        db_manager=db_manager,
        enable_cache=True,
        enable_validation=True,
        enable_quality_control=True,
    )

    # 运行基准测试
    suite = BenchmarkSuite(pipeline)
    results = await suite.run_all()

    return results


if __name__ == "__main__":
    asyncio.run(main())
