"""
CherryQuant 数据管道集成测试

测试完整的数据流程，确保生产环境可用性：
1. 端到端数据流 (collection → cleaning → storage → query)
2. 错误恢复场景 (retry, circuit breaker, fallback)
3. 并发操作 (thread safety)
4. 缓存行为 (L1, L2, L3)
5. 断路器状态转换

教学要点：
1. 集成测试 vs 单元测试
2. 生产环境测试策略
3. 异步测试最佳实践
4. Mock 外部依赖
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch
import threading
import time

from cherryquant.data import (
    DataPipeline,
    TushareCollector,
    MarketData,
    Exchange,
    TimeFrame,
    DataSource,
    QueryBuilder,
    DataValidator,
    DataNormalizer,
    QualityController,
)
from cherryquant.data.storage.timeseries_repository import TimeSeriesRepository
from cherryquant.data.storage.metadata_repository import MetadataRepository
from cherryquant.data.storage.cache_strategy import CacheStrategy, CacheLevel
from cherryquant.data.utils import (
    retry_async,
    retry_sync,
    RetryConfig,
    RetryStrategy,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitBreakerOpenError,
    FallbackStrategy,
)


# ==================== Fixtures ====================

@pytest.fixture
def sample_market_data():
    """生成测试用的市场数据"""
    base_date = datetime(2024, 1, 1, 9, 0, 0)
    data = []

    for i in range(10):
        data.append(
            MarketData(
                symbol="rb2501",
                exchange=Exchange.SHFE,
                datetime=base_date + timedelta(minutes=i),
                timeframe=TimeFrame.MIN_1,
                open=Decimal("3500") + Decimal(i),
                high=Decimal("3520") + Decimal(i),
                low=Decimal("3480") + Decimal(i),
                close=Decimal("3510") + Decimal(i),
                volume=10000 + i * 100,
                open_interest=5000,
                turnover=Decimal("35000000") + Decimal(i * 10000),
                source=DataSource.TUSHARE,
            )
        )

    return data


@pytest.fixture
def mock_tushare_collector():
    """Mock Tushare 数据采集器"""
    collector = Mock(spec=TushareCollector)
    collector.fetch_market_data = AsyncMock()
    collector.fetch_contract_info = AsyncMock()
    collector.fetch_trading_days = AsyncMock()
    return collector


@pytest.fixture
async def mock_timeseries_repo():
    """Mock 时间序列仓储"""
    repo = Mock(spec=TimeSeriesRepository)
    repo.save_batch = AsyncMock()
    repo.query = AsyncMock()
    repo.count = AsyncMock()
    repo.ensure_indexes = AsyncMock()
    return repo


@pytest.fixture
async def mock_metadata_repo():
    """Mock 元数据仓储"""
    repo = Mock(spec=MetadataRepository)
    repo.save_contract = AsyncMock()
    repo.get_contract = AsyncMock()
    repo.list_contracts = AsyncMock()
    repo.ensure_indexes = AsyncMock()
    return repo


# ==================== 端到端测试 ====================

class TestEndToEndDataFlow:
    """端到端数据流测试"""

    @pytest.mark.asyncio
    async def test_complete_data_pipeline(
        self,
        sample_market_data,
        mock_tushare_collector,
        mock_timeseries_repo,
    ):
        """
        测试完整的数据管道流程：采集 → 清洗 → 存储 → 查询

        教学要点：
        1. 集成测试验证组件协作
        2. Mock 外部依赖（数据库、API）
        3. 验证数据流转正确性
        """
        # 1. 采集数据（Mock）
        mock_tushare_collector.fetch_market_data.return_value = sample_market_data

        raw_data = await mock_tushare_collector.fetch_market_data(
            symbol="rb2501",
            exchange=Exchange.SHFE,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 10),
            timeframe=TimeFrame.MIN_1,
        )

        assert len(raw_data) == 10

        # 2. 清洗数据
        validator = DataValidator()
        normalizer = DataNormalizer()

        # 验证数据
        for data in raw_data:
            result = validator.validate_market_data(data)
            assert result.is_valid

        # 标准化数据
        cleaned_data = normalizer.normalize_batch(
            raw_data,
            deduplicate=True,
            fill_missing=False,
        )

        assert len(cleaned_data) == 10

        # 3. 存储数据（Mock）
        await mock_timeseries_repo.save_batch(cleaned_data)

        # 验证存储调用
        mock_timeseries_repo.save_batch.assert_called_once_with(cleaned_data)

        # 4. 查询数据（Mock）
        mock_timeseries_repo.query.return_value = cleaned_data[:5]

        query_builder = QueryBuilder(mock_timeseries_repo)
        results = await (query_builder
            .symbol("rb2501")
            .exchange(Exchange.SHFE)
            .date_range(datetime(2024, 1, 1), datetime(2024, 1, 5))
            .execute()
        )

        assert len(results) == 5
        assert results[0].symbol == "rb2501"

    @pytest.mark.asyncio
    async def test_data_validation_and_quality_control(self, sample_market_data):
        """
        测试数据验证和质量控制流程

        教学要点：
        1. 数据质量保障机制
        2. 验证失败的处理策略
        3. 质量指标的计算
        """
        validator = DataValidator()
        quality_controller = QualityController()

        # 验证所有数据
        validation_results = [
            validator.validate_market_data(data)
            for data in sample_market_data
        ]

        # 所有数据应该有效
        assert all(r.is_valid for r in validation_results)

        # 评估质量指标
        metrics = quality_controller.assess_data_quality(sample_market_data)

        # 验证质量指标
        assert metrics.total_count == 10
        assert metrics.valid_count == 10
        assert metrics.completeness_rate > 0.9
        assert metrics.accuracy_rate > 0.9
        assert metrics.overall_score > 0.8

    @pytest.mark.asyncio
    async def test_data_normalization_workflow(self):
        """
        测试数据标准化工作流

        教学要点：
        1. 不同数据源的标准化
        2. 符号和交易所代码的统一
        3. 去重和填充缺失值
        """
        normalizer = DataNormalizer()

        # 测试符号标准化
        assert normalizer.normalize_symbol("RB2501") == "rb2501"
        assert normalizer.normalize_symbol("rb2501.SHFE") == "rb2501"
        assert normalizer.normalize_symbol("RB2501.SHF") == "rb2501"

        # 测试交易所标准化
        assert normalizer.normalize_exchange("SHFE") == Exchange.SHFE
        assert normalizer.normalize_exchange("SHF") == Exchange.SHFE
        assert normalizer.normalize_exchange("上期所") == Exchange.SHFE

        # 测试时间周期标准化
        assert normalizer.normalize_timeframe("1min") == TimeFrame.MIN_1
        assert normalizer.normalize_timeframe("5m") == TimeFrame.MIN_5
        assert normalizer.normalize_timeframe("1h") == TimeFrame.HOUR_1
        assert normalizer.normalize_timeframe("1d") == TimeFrame.DAY_1
        assert normalizer.normalize_timeframe("1M") == TimeFrame.MONTH_1

        # 测试价格标准化
        price = normalizer.normalize_price(3500.123456, precision=2)
        assert price == Decimal("3500.12")


# ==================== 错误恢复测试 ====================

class TestErrorRecovery:
    """错误恢复机制测试"""

    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff(self):
        """
        测试指数退避重试

        教学要点：
        1. 重试机制的必要性
        2. 指数退避算法
        3. 重试次数控制
        """
        call_count = 0

        @retry_async(RetryConfig(
            max_attempts=3,
            base_delay=0.1,
            strategy=RetryStrategy.EXPONENTIAL,
        ))
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("网络错误")
            return "成功"

        # 应该在第3次尝试成功
        result = await flaky_function()
        assert result == "成功"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_failure_after_max_attempts(self):
        """
        测试达到最大重试次数后失败

        教学要点：
        1. 避免无限重试
        2. 最终失败的处理
        """
        call_count = 0

        @retry_async(RetryConfig(
            max_attempts=3,
            base_delay=0.1,
        ))
        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("持续错误")

        # 应该在3次尝试后抛出异常
        with pytest.raises(ConnectionError):
            await always_fail()

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_non_retriable_exception(self):
        """
        测试不可重试的异常

        教学要点：
        1. 快速失败原则
        2. 异常分类处理
        """
        call_count = 0

        @retry_async(RetryConfig(
            max_attempts=3,
            retriable_exceptions=(ConnectionError, TimeoutError),
            non_retriable_exceptions=(ValueError, TypeError),
        ))
        async def validation_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("参数错误")

        # 不应该重试，立即失败
        with pytest.raises(ValueError):
            await validation_error()

        assert call_count == 1

    def test_circuit_breaker_state_transitions(self):
        """
        测试断路器状态转换

        教学要点：
        1. 断路器的三种状态
        2. 状态转换条件
        3. 自动恢复机制
        """
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout=1.0,
            half_open_max_calls=2,  # 允许2次调用来测试恢复
        )
        breaker = CircuitBreaker(config)

        # 初始状态：CLOSED
        assert breaker.state == CircuitState.CLOSED

        # 模拟3次失败
        def failing_func():
            raise ConnectionError("失败")

        for i in range(3):
            try:
                breaker.call(failing_func)
            except ConnectionError:
                pass

        # 应该转换到 OPEN 状态
        assert breaker.state == CircuitState.OPEN

        # OPEN 状态应该拒绝调用
        with pytest.raises(CircuitBreakerOpenError):
            breaker.call(failing_func)

        # 等待超时
        time.sleep(1.1)

        # 应该转换到 HALF_OPEN 状态（尝试恢复）
        def success_func():
            return "成功"

        # 第一次成功调用会转换到 HALF_OPEN
        result = breaker.call(success_func)
        assert result == "成功"
        assert breaker.state == CircuitState.HALF_OPEN

        # 再次成功，应该转换回 CLOSED（达到成功阈值2）
        result = breaker.call(success_func)
        assert result == "成功"
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_retry(self):
        """
        测试断路器与重试的集成

        教学要点：
        1. 多层防护机制
        2. 断路器与重试的协作
        """
        config = CircuitBreakerConfig(
            failure_threshold=5,  # 设置较高的阈值，允许重试完成
            timeout=0.5,
        )
        breaker = CircuitBreaker(config)

        call_count = 0

        @retry_async(
            RetryConfig(max_attempts=3, base_delay=0.1),
            circuit_breaker=breaker,
        )
        async def protected_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:  # 第2次尝试成功
                raise ConnectionError("错误")
            return "成功"

        # 应该在重试后成功
        result = await protected_function()
        assert result == "成功"
        assert call_count == 2  # 失败1次，成功1次

    @pytest.mark.asyncio
    async def test_fallback_strategy(self):
        """
        测试降级策略

        教学要点：
        1. 服务降级
        2. 优雅失败
        3. 用户体验保障
        """
        async def primary_service():
            raise ConnectionError("主服务不可用")

        async def fallback_service():
            return "降级数据"

        result = await FallbackStrategy.with_fallback(
            primary=primary_service,
            fallback=fallback_service,
        )

        assert result == "降级数据"


# ==================== 并发测试 ====================

class TestConcurrentOperations:
    """并发操作测试"""

    @pytest.mark.asyncio
    async def test_cache_strategy_thread_safety(self):
        """
        测试缓存策略的线程安全性

        教学要点：
        1. 并发访问的风险
        2. 锁机制的使用
        3. 线程安全的验证
        """
        cache = CacheStrategy(
            enable_l1=True,
            enable_l2=False,
            l1_max_size=100,
            l1_ttl=60,
        )

        results = []
        errors = []

        async def worker(worker_id: int):
            try:
                for i in range(100):
                    key = f"key_{i % 10}"
                    value = f"worker_{worker_id}_value_{i}"

                    # 写入
                    await cache.set(key, value)

                    # 读取
                    cached = await cache.get(key)

                    # 记录结果
                    results.append((worker_id, key, cached))

                    # 短暂延迟
                    await asyncio.sleep(0.001)
            except Exception as e:
                errors.append((worker_id, e))

        # 创建10个并发任务
        tasks = [worker(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # 不应该有错误
        assert len(errors) == 0, f"并发错误: {errors}"

        # 应该有大量结果
        assert len(results) == 1000

    @pytest.mark.asyncio
    async def test_concurrent_data_queries(self, mock_timeseries_repo, sample_market_data):
        """
        测试并发查询

        教学要点：
        1. 异步并发查询
        2. 数据一致性
        3. 性能优化
        """
        mock_timeseries_repo.query.return_value = sample_market_data

        async def query_data(symbol: str):
            builder = QueryBuilder(mock_timeseries_repo)
            return await (builder
                .symbol(symbol)
                .exchange(Exchange.SHFE)
                .date_range(datetime(2024, 1, 1), datetime(2024, 1, 10))
                .execute()
            )

        # 并发执行10个查询
        symbols = [f"rb250{i}" for i in range(10)]
        tasks = [query_data(symbol) for symbol in symbols]

        results = await asyncio.gather(*tasks)

        # 所有查询都应该成功
        assert len(results) == 10
        for result in results:
            assert len(result) == 10

    @pytest.mark.asyncio
    async def test_concurrent_writes_with_retry(self):
        """
        测试带重试的并发写入

        教学要点：
        1. 并发写入冲突
        2. 重试机制的并发安全性
        3. 数据完整性保障
        """
        write_count = 0
        write_lock = threading.Lock()

        @retry_async(RetryConfig(max_attempts=3, base_delay=0.1))
        async def write_data(data_id: int):
            nonlocal write_count

            # 模拟偶尔失败
            if data_id % 3 == 0:
                raise ConnectionError("写入失败")

            # 记录写入
            with write_lock:
                write_count += 1

            await asyncio.sleep(0.01)
            return f"data_{data_id}"

        # 并发写入20条数据
        tasks = [write_data(i) for i in range(20)]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计成功的写入
        success_count = sum(1 for r in results if not isinstance(r, Exception))

        assert success_count >= 13  # 至少有2/3成功（非3的倍数）


# ==================== 缓存行为测试 ====================

class TestCacheBehavior:
    """缓存行为测试"""

    @pytest.mark.asyncio
    async def test_l1_cache_lru_eviction(self):
        """
        测试 L1 缓存的 LRU 淘汰策略

        教学要点：
        1. LRU 算法原理
        2. 缓存容量管理
        3. 缓存淘汰策略
        """
        cache = CacheStrategy(
            enable_l1=True,
            enable_l2=False,
            l1_max_size=5,  # 只保留5个条目
            l1_ttl=60,
        )

        # 写入10个条目
        for i in range(10):
            await cache.set(f"key_{i}", f"value_{i}")

        # 只有最后5个应该在缓存中
        for i in range(5):
            assert await cache.get(f"key_{i}") is None

        for i in range(5, 10):
            assert await cache.get(f"key_{i}") == f"value_{i}"

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self):
        """
        测试缓存 TTL 过期

        教学要点：
        1. TTL（Time To Live）机制
        2. 缓存失效策略
        3. 时间敏感数据的处理
        """
        cache = CacheStrategy(
            enable_l1=True,
            enable_l2=False,
            l1_max_size=10,
            l1_ttl=1,  # 1秒过期
        )

        # 写入数据
        await cache.set("key", "value")

        # 立即读取应该成功
        assert await cache.get("key") == "value"

        # 等待过期
        await asyncio.sleep(1.1)

        # 过期后应该读取不到
        assert await cache.get("key") is None

    @pytest.mark.asyncio
    async def test_cache_clear_operations(self):
        """
        测试缓存清空操作

        教学要点：
        1. 缓存管理接口
        2. 批量操作
        3. 缓存一致性
        """
        cache = CacheStrategy(
            enable_l1=True,
            enable_l2=False,
            l1_max_size=10,
            l1_ttl=60,
        )

        # 写入多个条目
        for i in range(5):
            await cache.set(f"key_{i}", f"value_{i}")

        # 删除单个
        await cache.delete("key_0")
        assert await cache.get("key_0") is None
        assert await cache.get("key_1") == "value_1"

        # 清空所有
        await cache.clear()
        for i in range(1, 5):
            assert await cache.get(f"key_{i}") is None


# ==================== 性能测试 ====================

class TestPerformance:
    """性能测试"""

    @pytest.mark.asyncio
    async def test_query_performance(self, mock_timeseries_repo):
        """
        测试查询性能

        教学要点：
        1. 性能基准测试
        2. 响应时间测量
        3. 性能优化验证
        """
        # 生成大量测试数据
        large_dataset = []
        base_date = datetime(2024, 1, 1)

        for i in range(1000):
            large_dataset.append(
                MarketData(
                    symbol="rb2501",
                    exchange=Exchange.SHFE,
                    datetime=base_date + timedelta(minutes=i),
                    timeframe=TimeFrame.MIN_1,
                    open=Decimal("3500"),
                    high=Decimal("3520"),
                    low=Decimal("3480"),
                    close=Decimal("3510"),
                    volume=10000,
                    open_interest=5000,
                    turnover=Decimal("35000000"),
                    source=DataSource.TUSHARE,
                )
            )

        mock_timeseries_repo.query.return_value = large_dataset

        # 测试查询性能
        start_time = time.time()

        builder = QueryBuilder(mock_timeseries_repo)
        results = await (builder
            .symbol("rb2501")
            .exchange(Exchange.SHFE)
            .date_range(base_date, base_date + timedelta(days=1))
            .limit(100)
            .execute()
        )

        end_time = time.time()
        duration = end_time - start_time

        # 查询应该在合理时间内完成（< 1秒）
        assert duration < 1.0
        assert len(results) == 100

    @pytest.mark.asyncio
    async def test_cache_performance(self):
        """
        测试缓存性能

        教学要点：
        1. 缓存命中率
        2. 读写性能
        3. 内存使用
        """
        cache = CacheStrategy(
            enable_l1=True,
            enable_l2=False,
            l1_max_size=1000,
            l1_ttl=60,
        )

        # 写入性能测试
        write_start = time.time()
        for i in range(1000):
            await cache.set(f"key_{i}", f"value_{i}" * 100)  # 较大的值
        write_end = time.time()
        write_duration = write_end - write_start

        # 写入应该很快（< 0.1秒）
        assert write_duration < 0.1

        # 读取性能测试
        read_start = time.time()
        for i in range(1000):
            value = await cache.get(f"key_{i}")
            assert value is not None
        read_end = time.time()
        read_duration = read_end - read_start

        # 读取应该更快（< 0.05秒）
        assert read_duration < 0.05


# ==================== 运行测试 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
