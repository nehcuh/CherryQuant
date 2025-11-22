"""
QueryBuilder 单元测试

教学要点：
1. 单元测试的组织结构
2. Mock 和 Stub 的使用
3. 异步测试
4. 测试覆盖率
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

from cherryquant.data.query.query_builder import QueryBuilder
from cherryquant.data.collectors.base_collector import (
    MarketData,
    Exchange,
    TimeFrame,
    DataSource,
)


# ==================== Fixtures ====================

@pytest.fixture
def mock_repository():
    """Mock 仓储"""
    repo = Mock()
    repo.query = AsyncMock()
    repo.count = AsyncMock()
    return repo


@pytest.fixture
def sample_market_data():
    """示例市场数据"""
    base_date = datetime(2024, 1, 1)

    data = []
    for i in range(30):
        data.append(
            MarketData(
                symbol="rb2501",
                exchange=Exchange.SHFE,
                datetime=base_date + timedelta(days=i),
                timeframe=TimeFrame.DAY_1,
                open=Decimal("3500") + Decimal(i),
                high=Decimal("3520") + Decimal(i),
                low=Decimal("3480") + Decimal(i),
                close=Decimal("3510") + Decimal(i),
                volume=10000 + i * 100,
                open_interest=5000,
                source=DataSource.TUSHARE,
            )
        )

    return data


# ==================== 测试类 ====================

class TestQueryBuilder:
    """QueryBuilder 测试类"""

    def test_initialization(self, mock_repository):
        """测试初始化"""
        builder = QueryBuilder(mock_repository)

        assert builder.repository == mock_repository
        assert builder._symbol is None
        assert builder._exchange is None
        assert builder._limit is None

    def test_fluent_interface(self, mock_repository):
        """测试流畅接口（方法链）"""
        builder = QueryBuilder(mock_repository)

        # 方法链应该返回自身
        result = (builder
            .symbol("rb2501")
            .exchange(Exchange.SHFE)
            .timeframe(TimeFrame.DAY_1)
        )

        assert result is builder
        assert builder._symbol == "rb2501"
        assert builder._exchange == Exchange.SHFE
        assert builder._timeframe == TimeFrame.DAY_1

    def test_date_range_validation(self, mock_repository):
        """测试日期范围验证"""
        builder = QueryBuilder(mock_repository)

        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        builder.date_range(start, end)

        assert builder._start_date == start
        assert builder._end_date == end

        # 测试无效范围
        with pytest.raises(ValueError):
            builder.date_range(end, start)  # 结束日期早于开始日期

    @pytest.mark.asyncio
    async def test_execute_basic_query(self, mock_repository, sample_market_data):
        """测试基础查询执行"""
        # 设置 mock 返回值
        mock_repository.query.return_value = sample_market_data

        builder = (QueryBuilder(mock_repository)
            .symbol("rb2501")
            .exchange(Exchange.SHFE)
            .date_range(
                datetime(2024, 1, 1),
                datetime(2024, 1, 31)
            )
        )

        results = await builder.execute()

        # 验证结果
        assert len(results) == 30
        assert results[0].symbol == "rb2501"

        # 验证 repository 被正确调用
        mock_repository.query.assert_called_once()
        call_args = mock_repository.query.call_args[1]
        assert call_args['symbol'] == "rb2501"
        assert call_args['exchange'] == Exchange.SHFE

    @pytest.mark.asyncio
    async def test_execute_missing_required_fields(self, mock_repository):
        """测试缺少必要字段时的错误"""
        builder = QueryBuilder(mock_repository)

        # 缺少 symbol
        with pytest.raises(ValueError, match="必须设置 symbol"):
            await builder.execute()

        # 只设置 symbol，缺少 exchange
        builder.symbol("rb2501")
        with pytest.raises(ValueError, match="必须设置 exchange"):
            await builder.execute()

        # 只设置 symbol 和 exchange，缺少日期范围
        builder.exchange(Exchange.SHFE)
        with pytest.raises(ValueError, match="必须设置日期范围"):
            await builder.execute()

    @pytest.mark.asyncio
    async def test_price_range_filter(self, mock_repository, sample_market_data):
        """测试价格范围过滤"""
        mock_repository.query.return_value = sample_market_data

        builder = (QueryBuilder(mock_repository)
            .symbol("rb2501")
            .exchange(Exchange.SHFE)
            .date_range(
                datetime(2024, 1, 1),
                datetime(2024, 1, 31)
            )
            .price_range(
                min_price=Decimal("3500"),
                max_price=Decimal("3520")
            )
        )

        results = await builder.execute()

        # 验证过滤结果
        assert len(results) < len(sample_market_data)
        for data in results:
            assert Decimal("3500") <= data.close <= Decimal("3520")

    @pytest.mark.asyncio
    async def test_volume_filter(self, mock_repository, sample_market_data):
        """测试成交量过滤"""
        mock_repository.query.return_value = sample_market_data

        builder = (QueryBuilder(mock_repository)
            .symbol("rb2501")
            .exchange(Exchange.SHFE)
            .date_range(
                datetime(2024, 1, 1),
                datetime(2024, 1, 31)
            )
            .volume_greater_than(10500)
        )

        results = await builder.execute()

        # 验证成交量过滤
        for data in results:
            assert data.volume >= 10500

    @pytest.mark.asyncio
    async def test_limit_and_offset(self, mock_repository, sample_market_data):
        """测试分页功能"""
        mock_repository.query.return_value = sample_market_data

        builder = (QueryBuilder(mock_repository)
            .symbol("rb2501")
            .exchange(Exchange.SHFE)
            .date_range(
                datetime(2024, 1, 1),
                datetime(2024, 1, 31)
            )
            .limit(10)
            .offset(5)
        )

        results = await builder.execute()

        # 验证分页
        assert len(results) == 10
        # 验证偏移（应该跳过前5条）
        assert results[0] == sample_market_data[5]

    @pytest.mark.asyncio
    async def test_page_method(self, mock_repository, sample_market_data):
        """测试页码方法"""
        mock_repository.query.return_value = sample_market_data

        # 第2页，每页10条
        builder = (QueryBuilder(mock_repository)
            .symbol("rb2501")
            .exchange(Exchange.SHFE)
            .date_range(
                datetime(2024, 1, 1),
                datetime(2024, 1, 31)
            )
            .page(page_num=2, page_size=10)
        )

        results = await builder.execute()

        # 验证
        assert len(results) == 10
        assert results[0] == sample_market_data[10]  # 第2页从第10条开始

    @pytest.mark.asyncio
    async def test_sorting(self, mock_repository, sample_market_data):
        """测试排序功能"""
        # 打乱数据顺序
        import random
        shuffled_data = sample_market_data.copy()
        random.shuffle(shuffled_data)

        mock_repository.query.return_value = shuffled_data

        # 按日期升序
        builder = (QueryBuilder(mock_repository)
            .symbol("rb2501")
            .exchange(Exchange.SHFE)
            .date_range(
                datetime(2024, 1, 1),
                datetime(2024, 1, 31)
            )
            .order_by("datetime", descending=False)
        )

        results = await builder.execute()

        # 验证排序
        for i in range(len(results) - 1):
            assert results[i].datetime <= results[i + 1].datetime

        # 按日期降序
        builder_desc = (QueryBuilder(mock_repository)
            .symbol("rb2501")
            .exchange(Exchange.SHFE)
            .date_range(
                datetime(2024, 1, 1),
                datetime(2024, 1, 31)
            )
            .order_by("datetime", descending=True)
        )

        results_desc = await builder_desc.execute()

        # 验证降序
        for i in range(len(results_desc) - 1):
            assert results_desc[i].datetime >= results_desc[i + 1].datetime

    @pytest.mark.asyncio
    async def test_first_and_last(self, mock_repository, sample_market_data):
        """测试 first 和 last 方法"""
        mock_repository.query.return_value = sample_market_data

        builder = (QueryBuilder(mock_repository)
            .symbol("rb2501")
            .exchange(Exchange.SHFE)
            .date_range(
                datetime(2024, 1, 1),
                datetime(2024, 1, 31)
            )
        )

        # 测试 first
        first = await builder.first()
        assert first is not None
        assert first == sample_market_data[0]

        # 测试 last
        last = await builder.last()
        assert last is not None
        assert last == sample_market_data[-1]

    @pytest.mark.asyncio
    async def test_count(self, mock_repository, sample_market_data):
        """测试计数功能"""
        # 无过滤器时，使用数据库计数
        mock_repository.count.return_value = 30

        builder = (QueryBuilder(mock_repository)
            .symbol("rb2501")
            .exchange(Exchange.SHFE)
            .date_range(
                datetime(2024, 1, 1),
                datetime(2024, 1, 31)
            )
        )

        count = await builder.count()

        assert count == 30
        mock_repository.count.assert_called_once()

    @pytest.mark.asyncio
    async def test_aggregation_functions(self, mock_repository, sample_market_data):
        """测试聚合函数"""
        mock_repository.query.return_value = sample_market_data

        builder = (QueryBuilder(mock_repository)
            .symbol("rb2501")
            .exchange(Exchange.SHFE)
            .date_range(
                datetime(2024, 1, 1),
                datetime(2024, 1, 31)
            )
        )

        # 测试平均价
        avg_price = await builder.avg_price()
        assert avg_price is not None
        assert isinstance(avg_price, Decimal)

        # 测试最高价
        max_price = await builder.max_price()
        assert max_price is not None
        assert max_price == max(d.close for d in sample_market_data)

        # 测试最低价
        min_price = await builder.min_price()
        assert min_price is not None
        assert min_price == min(d.close for d in sample_market_data)

        # 测试总成交量
        total_vol = await builder.total_volume()
        assert total_vol == sum(d.volume for d in sample_market_data)

    @pytest.mark.asyncio
    async def test_custom_filter(self, mock_repository, sample_market_data):
        """测试自定义过滤器"""
        mock_repository.query.return_value = sample_market_data

        # 自定义过滤器：只保留偶数天的数据
        def even_day_filter(data: MarketData) -> bool:
            return data.datetime.day % 2 == 0

        builder = (QueryBuilder(mock_repository)
            .symbol("rb2501")
            .exchange(Exchange.SHFE)
            .date_range(
                datetime(2024, 1, 1),
                datetime(2024, 1, 31)
            )
            .custom_filter(even_day_filter)
        )

        results = await builder.execute()

        # 验证过滤结果
        for data in results:
            assert data.datetime.day % 2 == 0

    def test_clone(self, mock_repository):
        """测试克隆功能"""
        builder = (QueryBuilder(mock_repository)
            .symbol("rb2501")
            .exchange(Exchange.SHFE)
            .date_range(
                datetime(2024, 1, 1),
                datetime(2024, 1, 31)
            )
            .limit(10)
        )

        # 克隆
        cloned = builder.clone()

        # 验证克隆是独立的
        assert cloned is not builder
        assert cloned._symbol == builder._symbol
        assert cloned._exchange == builder._exchange
        assert cloned._limit == builder._limit

        # 修改克隆不影响原对象
        cloned.limit(20)
        assert builder._limit == 10
        assert cloned._limit == 20

    def test_repr(self, mock_repository):
        """测试字符串表示"""
        builder = (QueryBuilder(mock_repository)
            .symbol("rb2501")
            .exchange(Exchange.SHFE)
            .date_range(
                datetime(2024, 1, 1),
                datetime(2024, 1, 31)
            )
        )

        repr_str = repr(builder)

        assert "QueryBuilder" in repr_str
        assert "rb2501" in repr_str
        assert "SHFE" in repr_str


# ==================== 运行测试 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
