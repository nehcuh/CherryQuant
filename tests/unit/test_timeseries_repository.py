"""
TimeSeriesRepository 单元测试

全面测试时间序列数据仓储的所有功能：
1. 数据保存（单条和批量）
2. 数据查询（多种查询方式）
3. 数据转换（MarketData ↔ MongoDB 文档）
4. 索引管理
5. 错误处理
6. 边界条件

教学要点：
1. 单元测试的编写方法
2. 异步测试的处理
3. Mock 数据库连接
4. 测试覆盖率优化
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from pymongo.errors import BulkWriteError

from cherryquant.data.collectors.base_collector import (
    MarketData,
    Exchange,
    TimeFrame,
    DataSource,
)
from cherryquant.data.storage.timeseries_repository import TimeSeriesRepository
from cherryquant.adapters.data_storage.mongodb_manager import MongoDBConnectionManager


# ==================== Fixtures ====================

@pytest.fixture
def mock_connection_manager():
    """Mock MongoDB 连接管理器"""
    manager = Mock(spec=MongoDBConnectionManager)

    # Mock async database
    mock_db = MagicMock()
    manager._async_db = mock_db

    return manager


@pytest.fixture
def repository(mock_connection_manager):
    """创建 TimeSeriesRepository 实例"""
    return TimeSeriesRepository(
        connection_manager=mock_connection_manager,
        enable_auto_index=True,
    )


@pytest.fixture
def sample_market_data():
    """生成示例市场数据"""
    return MarketData(
        symbol="rb2501",
        exchange=Exchange.SHFE,
        datetime=datetime(2024, 1, 1, 9, 0, 0),
        timeframe=TimeFrame.DAY_1,
        open=Decimal("3500.50"),
        high=Decimal("3520.75"),
        low=Decimal("3480.25"),
        close=Decimal("3510.00"),
        volume=100000,
        open_interest=50000,
        turnover=Decimal("351000000.50"),
        source=DataSource.TUSHARE,
        collected_at=datetime(2024, 1, 1, 15, 0, 0),
    )


@pytest.fixture
def sample_market_data_list():
    """生成多条示例数据"""
    base_date = datetime(2024, 1, 1, 9, 0, 0)
    data_list = []

    for i in range(5):
        data_list.append(
            MarketData(
                symbol=f"rb250{i}",
                exchange=Exchange.SHFE,
                datetime=base_date + timedelta(days=i),
                timeframe=TimeFrame.DAY_1,
                open=Decimal(f"350{i}.00"),
                high=Decimal(f"352{i}.00"),
                low=Decimal(f"348{i}.00"),
                close=Decimal(f"351{i}.00"),
                volume=100000 + i * 1000,
                open_interest=50000 + i * 500,
                turnover=Decimal(f"{35000000 + i * 100000}.00"),
                source=DataSource.TUSHARE,
            )
        )

    return data_list


# ==================== 基础功能测试 ====================

class TestBasicFunctionality:
    """基础功能测试"""

    def test_initialization(self, mock_connection_manager):
        """测试初始化"""
        repo = TimeSeriesRepository(
            connection_manager=mock_connection_manager,
            enable_auto_index=True,
        )

        assert repo.connection_manager == mock_connection_manager
        assert repo.enable_auto_index is True
        assert repo._collections == {}
        assert repo._indexes_created == set()

    def test_collection_names_mapping(self):
        """测试集合名称映射"""
        assert TimeSeriesRepository.COLLECTION_NAMES[TimeFrame.MIN_1] == "market_data_1m"
        assert TimeSeriesRepository.COLLECTION_NAMES[TimeFrame.MIN_5] == "market_data_5m"
        assert TimeSeriesRepository.COLLECTION_NAMES[TimeFrame.MIN_15] == "market_data_15m"
        assert TimeSeriesRepository.COLLECTION_NAMES[TimeFrame.MIN_30] == "market_data_30m"
        assert TimeSeriesRepository.COLLECTION_NAMES[TimeFrame.HOUR_1] == "market_data_1h"
        assert TimeSeriesRepository.COLLECTION_NAMES[TimeFrame.DAY_1] == "market_data_1d"

    def test_database_property(self, repository, mock_connection_manager):
        """测试 database 属性"""
        db = repository.database
        assert db == mock_connection_manager._async_db

    def test_database_property_not_connected(self):
        """测试未连接时访问 database 属性"""
        manager = Mock(spec=MongoDBConnectionManager)
        manager._async_db = None

        repo = TimeSeriesRepository(connection_manager=manager)

        with pytest.raises(RuntimeError, match="数据库未连接"):
            _ = repo.database

    def test_get_collection(self, repository):
        """测试获取集合"""
        collection = repository._get_collection(TimeFrame.DAY_1)

        # 应该从数据库获取集合
        assert collection is not None

        # 集合应该被缓存
        assert "market_data_1d" in repository._collections

        # 第二次获取应该从缓存
        collection2 = repository._get_collection(TimeFrame.DAY_1)
        assert collection2 is collection

    def test_get_collection_unsupported_timeframe(self, repository):
        """测试不支持的时间周期"""
        # WEEK_1 不在映射中
        with pytest.raises(ValueError, match="不支持的时间周期"):
            repository._get_collection(TimeFrame.WEEK_1)


# ==================== 数据转换测试 ====================

class TestDataConversion:
    """数据转换测试"""

    def test_to_document(self, repository, sample_market_data):
        """测试 MarketData → MongoDB 文档转换"""
        doc = repository._to_document(sample_market_data)

        # 验证文档结构
        assert doc["datetime"] == datetime(2024, 1, 1, 9, 0, 0)
        assert doc["metadata"]["symbol"] == "rb2501"
        assert doc["metadata"]["exchange"] == "SHFE"
        assert doc["metadata"]["underlying"] == "rb"  # 去除数字

        # 验证价格转换为 float
        assert doc["open"] == 3500.50
        assert doc["high"] == 3520.75
        assert doc["low"] == 3480.25
        assert doc["close"] == 3510.00

        # 验证其他字段
        assert doc["volume"] == 100000
        assert doc["open_interest"] == 50000
        assert doc["turnover"] == 351000000.50
        assert doc["source"] == "tushare"  # DataSource enum value is lowercase
        assert doc["collected_at"] == datetime(2024, 1, 1, 15, 0, 0)

    def test_to_document_without_turnover(self, repository):
        """测试没有 turnover 的数据转换"""
        data = MarketData(
            symbol="rb2501",
            exchange=Exchange.SHFE,
            datetime=datetime(2024, 1, 1),
            timeframe=TimeFrame.DAY_1,
            open=Decimal("3500"),
            high=Decimal("3520"),
            low=Decimal("3480"),
            close=Decimal("3510"),
            volume=100000,
            open_interest=50000,
            turnover=None,  # None
            source=DataSource.TUSHARE,
        )

        doc = repository._to_document(data)
        assert doc["turnover"] is None

    def test_to_document_without_collected_at(self, repository):
        """测试没有 collected_at 的数据转换"""
        data = MarketData(
            symbol="rb2501",
            exchange=Exchange.SHFE,
            datetime=datetime(2024, 1, 1),
            timeframe=TimeFrame.DAY_1,
            open=Decimal("3500"),
            high=Decimal("3520"),
            low=Decimal("3480"),
            close=Decimal("3510"),
            volume=100000,
            open_interest=50000,
            source=DataSource.TUSHARE,
            collected_at=None,
        )

        doc = repository._to_document(data)
        assert doc["collected_at"] is not None  # 应该使用当前时间

    def test_from_document(self, repository):
        """测试 MongoDB 文档 → MarketData 转换"""
        doc = {
            "datetime": datetime(2024, 1, 1, 9, 0, 0),
            "metadata": {
                "symbol": "rb2501",
                "exchange": "SHFE",
                "underlying": "rb",
            },
            "open": 3500.50,
            "high": 3520.75,
            "low": 3480.25,
            "close": 3510.00,
            "volume": 100000,
            "open_interest": 50000,
            "turnover": 351000000.50,
            "source": "tushare",  # Lowercase enum value
            "collected_at": datetime(2024, 1, 1, 15, 0, 0),
        }

        market_data = repository._from_document(doc, TimeFrame.DAY_1)

        # 验证 MarketData 对象
        assert market_data.symbol == "rb2501"
        assert market_data.exchange == Exchange.SHFE
        assert market_data.datetime == datetime(2024, 1, 1, 9, 0, 0)
        assert market_data.timeframe == TimeFrame.DAY_1

        # 验证价格转换为 Decimal
        assert market_data.open == Decimal("3500.50")
        assert market_data.high == Decimal("3520.75")
        assert market_data.low == Decimal("3480.25")
        assert market_data.close == Decimal("3510.00")

        # 验证其他字段
        assert market_data.volume == 100000
        assert market_data.open_interest == 50000
        assert market_data.turnover == Decimal("351000000.50")
        assert market_data.source == DataSource.TUSHARE
        assert market_data.collected_at == datetime(2024, 1, 1, 15, 0, 0)

    def test_from_document_without_turnover(self, repository):
        """测试没有 turnover 的文档转换"""
        doc = {
            "datetime": datetime(2024, 1, 1),
            "metadata": {"symbol": "rb2501", "exchange": "SHFE"},
            "open": 3500.0,
            "high": 3520.0,
            "low": 3480.0,
            "close": 3510.0,
            "volume": 100000,
            "open_interest": 50000,
            "turnover": None,
            "source": "tushare",
        }

        market_data = repository._from_document(doc, TimeFrame.DAY_1)
        assert market_data.turnover is None

    def test_roundtrip_conversion(self, repository, sample_market_data):
        """测试往返转换（MarketData → 文档 → MarketData）"""
        # 转换为文档
        doc = repository._to_document(sample_market_data)

        # 转换回 MarketData
        restored_data = repository._from_document(doc, sample_market_data.timeframe)

        # 验证数据一致性
        assert restored_data.symbol == sample_market_data.symbol
        assert restored_data.exchange == sample_market_data.exchange
        assert restored_data.datetime == sample_market_data.datetime
        assert restored_data.timeframe == sample_market_data.timeframe
        assert restored_data.open == sample_market_data.open
        assert restored_data.high == sample_market_data.high
        assert restored_data.low == sample_market_data.low
        assert restored_data.close == sample_market_data.close
        assert restored_data.volume == sample_market_data.volume
        assert restored_data.open_interest == sample_market_data.open_interest


# ==================== 索引管理测试 ====================

class TestIndexManagement:
    """索引管理测试"""

    @pytest.mark.asyncio
    async def test_ensure_indexes(self, repository):
        """测试索引创建"""
        # Mock collection
        mock_collection = AsyncMock()
        repository._get_collection = Mock(return_value=mock_collection)

        await repository.ensure_indexes(TimeFrame.DAY_1)

        # 验证 create_indexes 被调用
        mock_collection.create_indexes.assert_called_once()

        # 验证索引被标记为已创建
        assert "market_data_1d" in repository._indexes_created

    @pytest.mark.asyncio
    async def test_ensure_indexes_only_once(self, repository):
        """测试索引只创建一次"""
        mock_collection = AsyncMock()
        repository._get_collection = Mock(return_value=mock_collection)

        # 第一次创建
        await repository.ensure_indexes(TimeFrame.DAY_1)

        # 第二次调用应该跳过
        await repository.ensure_indexes(TimeFrame.DAY_1)

        # 只应该调用一次
        assert mock_collection.create_indexes.call_count == 1

    @pytest.mark.asyncio
    async def test_ensure_indexes_error_handling(self, repository):
        """测试索引创建错误处理"""
        mock_collection = AsyncMock()
        mock_collection.create_indexes.side_effect = Exception("索引创建失败")
        repository._get_collection = Mock(return_value=mock_collection)

        # 应该不抛出异常（只记录警告）
        await repository.ensure_indexes(TimeFrame.DAY_1)


# ==================== 数据保存测试 ====================

class TestDataSaving:
    """数据保存测试"""

    @pytest.mark.asyncio
    async def test_save_single(self, repository, sample_market_data):
        """测试保存单条数据"""
        # Mock save_batch
        repository.save_batch = AsyncMock(return_value=1)

        result = await repository.save(sample_market_data)

        assert result is True
        repository.save_batch.assert_called_once_with([sample_market_data])

    @pytest.mark.asyncio
    async def test_save_batch_empty_list(self, repository):
        """测试保存空列表"""
        result = await repository.save_batch([])
        assert result == 0

    @pytest.mark.asyncio
    async def test_save_batch_success(self, repository, sample_market_data_list):
        """测试批量保存成功"""
        # Mock collection
        mock_collection = AsyncMock()
        mock_result = Mock()
        mock_result.inserted_ids = [f"id_{i}" for i in range(5)]
        mock_collection.insert_many.return_value = mock_result

        repository._get_collection = Mock(return_value=mock_collection)
        repository.ensure_indexes = AsyncMock()

        result = await repository.save_batch(sample_market_data_list)

        assert result == 5
        mock_collection.insert_many.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_batch_with_duplicates(self, repository, sample_market_data_list):
        """测试批量保存时遇到重复数据"""
        # Mock collection with BulkWriteError
        mock_collection = AsyncMock()

        bulk_error = BulkWriteError({
            "nInserted": 3,
            "writeErrors": [
                {"index": 0, "errmsg": "duplicate key"},
                {"index": 1, "errmsg": "duplicate key"},
            ]
        })
        mock_collection.insert_many.side_effect = bulk_error

        repository._get_collection = Mock(return_value=mock_collection)
        repository.ensure_indexes = AsyncMock()

        # 应该返回成功插入的数量
        result = await repository.save_batch(sample_market_data_list)
        assert result == 3

    @pytest.mark.asyncio
    async def test_save_batch_disable_auto_index(self, mock_connection_manager, sample_market_data_list):
        """测试禁用自动索引"""
        repo = TimeSeriesRepository(
            connection_manager=mock_connection_manager,
            enable_auto_index=False,
        )

        mock_collection = AsyncMock()
        mock_result = Mock()
        mock_result.inserted_ids = [f"id_{i}" for i in range(5)]
        mock_collection.insert_many.return_value = mock_result

        repo._get_collection = Mock(return_value=mock_collection)
        repo.ensure_indexes = AsyncMock()

        await repo.save_batch(sample_market_data_list)

        # 不应该调用 ensure_indexes
        repo.ensure_indexes.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_batch_mixed_timeframes(self, repository):
        """测试混合时间周期的批量保存"""
        data_list = [
            MarketData(
                symbol="rb2501",
                exchange=Exchange.SHFE,
                datetime=datetime(2024, 1, 1),
                timeframe=TimeFrame.DAY_1,
                open=Decimal("3500"),
                high=Decimal("3520"),
                low=Decimal("3480"),
                close=Decimal("3510"),
                volume=100000,
                open_interest=50000,
                source=DataSource.TUSHARE,
            ),
            MarketData(
                symbol="rb2501",
                exchange=Exchange.SHFE,
                datetime=datetime(2024, 1, 1, 9, 0),
                timeframe=TimeFrame.MIN_1,
                open=Decimal("3500"),
                high=Decimal("3520"),
                low=Decimal("3480"),
                close=Decimal("3510"),
                volume=10000,
                open_interest=50000,
                source=DataSource.TUSHARE,
            ),
        ]

        mock_collection_day = AsyncMock()
        mock_collection_min = AsyncMock()

        mock_result = Mock()
        mock_result.inserted_ids = ["id_1"]

        mock_collection_day.insert_many.return_value = mock_result
        mock_collection_min.insert_many.return_value = mock_result

        def get_collection(timeframe):
            if timeframe == TimeFrame.DAY_1:
                return mock_collection_day
            else:
                return mock_collection_min

        repository._get_collection = get_collection
        repository.ensure_indexes = AsyncMock()

        result = await repository.save_batch(data_list)

        # 应该分别插入到不同的集合
        assert result == 2
        mock_collection_day.insert_many.assert_called_once()
        mock_collection_min.insert_many.assert_called_once()


# ==================== 数据查询测试 ====================

class TestDataQuerying:
    """数据查询测试"""

    @pytest.mark.asyncio
    async def test_query(self, repository):
        """测试基本查询"""
        # Mock collection and cursor
        mock_cursor = Mock()
        mock_cursor.sort = Mock(return_value=mock_cursor)
        mock_cursor.limit = Mock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=[
            {
                "datetime": datetime(2024, 1, 1),
                "metadata": {"symbol": "rb2501", "exchange": "SHFE"},
                "open": 3500.0,
                "high": 3520.0,
                "low": 3480.0,
                "close": 3510.0,
                "volume": 100000,
                "open_interest": 50000,
                "turnover": 351000000.0,
                "source": "tushare",
            }
        ])

        mock_collection = Mock()
        mock_collection.find.return_value = mock_cursor

        repository._get_collection = Mock(return_value=mock_collection)

        results = await repository.query(
            symbol="rb2501",
            exchange=Exchange.SHFE,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            timeframe=TimeFrame.DAY_1,
        )

        assert len(results) == 1
        assert results[0].symbol == "rb2501"
        assert results[0].exchange == Exchange.SHFE

    @pytest.mark.asyncio
    async def test_query_with_limit(self, repository):
        """测试带限制的查询"""
        mock_cursor = Mock()
        mock_cursor.sort = Mock(return_value=mock_cursor)
        mock_cursor.limit = Mock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=[])

        mock_collection = Mock()
        mock_collection.find.return_value = mock_cursor

        repository._get_collection = Mock(return_value=mock_collection)

        await repository.query(
            symbol="rb2501",
            exchange=Exchange.SHFE,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            timeframe=TimeFrame.DAY_1,
            limit=10,
        )

        # 验证 limit 被调用
        mock_cursor.limit.assert_called_once_with(10)

    @pytest.mark.asyncio
    async def test_query_by_underlying(self, repository):
        """测试按标的代码查询"""
        mock_cursor = Mock()
        mock_cursor.sort = Mock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=[])

        mock_collection = Mock()
        mock_collection.find.return_value = mock_cursor

        repository._get_collection = Mock(return_value=mock_collection)

        results = await repository.query_by_underlying(
            underlying="rb",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            timeframe=TimeFrame.DAY_1,
            exchange=Exchange.SHFE,
        )

        # 验证查询条件
        call_args = mock_collection.find.call_args[0][0]
        assert call_args["metadata.underlying"] == "rb"
        assert call_args["metadata.exchange"] == "SHFE"

    @pytest.mark.asyncio
    async def test_get_latest(self, repository):
        """测试获取最新数据"""
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = {
            "datetime": datetime(2024, 1, 31),
            "metadata": {"symbol": "rb2501", "exchange": "SHFE"},
            "open": 3600.0,
            "high": 3620.0,
            "low": 3580.0,
            "close": 3610.0,
            "volume": 100000,
            "open_interest": 50000,
            "turnover": 361000000.0,
            "source": "tushare",
        }

        repository._get_collection = Mock(return_value=mock_collection)

        result = await repository.get_latest(
            symbol="rb2501",
            exchange=Exchange.SHFE,
            timeframe=TimeFrame.DAY_1,
        )

        assert result is not None
        assert result.symbol == "rb2501"
        assert result.datetime == datetime(2024, 1, 31)

    @pytest.mark.asyncio
    async def test_get_latest_not_found(self, repository):
        """测试获取最新数据（不存在）"""
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = None

        repository._get_collection = Mock(return_value=mock_collection)

        result = await repository.get_latest(
            symbol="nonexistent",
            exchange=Exchange.SHFE,
            timeframe=TimeFrame.DAY_1,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_count(self, repository):
        """测试数据计数"""
        mock_collection = AsyncMock()
        mock_collection.count_documents.return_value = 100

        repository._get_collection = Mock(return_value=mock_collection)

        count = await repository.count(
            symbol="rb2501",
            exchange=Exchange.SHFE,
            timeframe=TimeFrame.DAY_1,
        )

        assert count == 100

    @pytest.mark.asyncio
    async def test_count_with_date_range(self, repository):
        """测试带日期范围的计数"""
        mock_collection = AsyncMock()
        mock_collection.count_documents.return_value = 30

        repository._get_collection = Mock(return_value=mock_collection)

        count = await repository.count(
            symbol="rb2501",
            exchange=Exchange.SHFE,
            timeframe=TimeFrame.DAY_1,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert count == 30

        # 验证查询包含日期过滤
        call_args = mock_collection.count_documents.call_args[0][0]
        assert "datetime" in call_args
        assert "$gte" in call_args["datetime"]
        assert "$lte" in call_args["datetime"]


# ==================== 数据操作测试 ====================

class TestDataOperations:
    """数据操作测试"""

    @pytest.mark.asyncio
    async def test_delete_range(self, repository):
        """测试删除日期范围内的数据"""
        mock_collection = AsyncMock()
        mock_result = Mock()
        mock_result.deleted_count = 10
        mock_collection.delete_many.return_value = mock_result

        repository._get_collection = Mock(return_value=mock_collection)

        deleted = await repository.delete_range(
            symbol="rb2501",
            exchange=Exchange.SHFE,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 10),
            timeframe=TimeFrame.DAY_1,
        )

        assert deleted == 10
        mock_collection.delete_many.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_date_range(self, repository):
        """测试获取数据的日期范围"""
        mock_cursor = AsyncMock()
        mock_cursor.to_list.return_value = [
            {
                "_id": None,
                "min_date": datetime(2024, 1, 1),
                "max_date": datetime(2024, 1, 31),
            }
        ]

        mock_collection = Mock()
        mock_collection.aggregate.return_value = mock_cursor

        repository._get_collection = Mock(return_value=mock_collection)

        date_range = await repository.get_date_range(
            symbol="rb2501",
            exchange=Exchange.SHFE,
            timeframe=TimeFrame.DAY_1,
        )

        assert date_range is not None
        assert date_range[0] == datetime(2024, 1, 1)
        assert date_range[1] == datetime(2024, 1, 31)

    @pytest.mark.asyncio
    async def test_get_date_range_no_data(self, repository):
        """测试获取日期范围（无数据）"""
        mock_cursor = AsyncMock()
        mock_cursor.to_list.return_value = []

        mock_collection = Mock()
        mock_collection.aggregate.return_value = mock_cursor

        repository._get_collection = Mock(return_value=mock_collection)

        date_range = await repository.get_date_range(
            symbol="nonexistent",
            exchange=Exchange.SHFE,
            timeframe=TimeFrame.DAY_1,
        )

        assert date_range is None

    @pytest.mark.asyncio
    async def test_upsert_insert(self, repository, sample_market_data):
        """测试 upsert（插入新数据）"""
        mock_collection = AsyncMock()
        mock_result = Mock()
        mock_result.upserted_id = "new_id"
        mock_result.modified_count = 0
        mock_collection.replace_one.return_value = mock_result

        repository._get_collection = Mock(return_value=mock_collection)

        result = await repository.upsert(sample_market_data)

        assert result is True
        mock_collection.replace_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_update(self, repository, sample_market_data):
        """测试 upsert（更新现有数据）"""
        mock_collection = AsyncMock()
        mock_result = Mock()
        mock_result.upserted_id = None
        mock_result.modified_count = 1
        mock_collection.replace_one.return_value = mock_result

        repository._get_collection = Mock(return_value=mock_collection)

        result = await repository.upsert(sample_market_data)

        assert result is True

        # 验证查询条件包含唯一标识
        call_args = mock_collection.replace_one.call_args
        filter_query = call_args[0][0]
        assert filter_query["metadata.symbol"] == "rb2501"
        assert filter_query["metadata.exchange"] == "SHFE"
        assert filter_query["datetime"] == datetime(2024, 1, 1, 9, 0, 0)


# ==================== 运行测试 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
