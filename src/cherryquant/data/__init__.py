"""
CherryQuant Data Module

提供完整的量化交易数据处理流程：
- 数据采集 (collectors): 从多个数据源获取市场数据
- 数据清洗 (cleaners): 验证、标准化和质量控制
- 数据存储 (storage): 高效的时间序列数据存储
- 数据查询 (query): 灵活的查询和聚合接口
- 数据管道 (pipeline): 端到端的数据处理协调器

这个模块设计用于教学，展示完整的数据管道设计模式。

使用示例：
    from cherryquant.data import (
        DataPipeline,
        TushareCollector,
        QueryBuilder,
        MarketData,
        Exchange,
        TimeFrame,
    )
"""

# Core Pipeline
from cherryquant.data.pipeline import DataPipeline

# Collectors
from cherryquant.data.collectors.base_collector import (
    BaseCollector,
    MarketData,
    ContractInfo,
    TradingDay,
    Exchange,
    TimeFrame,
    DataSource,
)
from cherryquant.data.collectors.tushare_collector import TushareCollector

# Cleaners
from cherryquant.data.cleaners.validator import (
    DataValidator,
    ValidationResult,
    ValidationIssue,
    ValidationLevel,
)
from cherryquant.data.cleaners.normalizer import DataNormalizer
from cherryquant.data.cleaners.quality_control import (
    QualityController,
    QualityMetrics,
)

# Query
from cherryquant.data.query.query_builder import QueryBuilder
from cherryquant.data.query.batch_query import (
    BatchQueryExecutor,
    BatchQueryRequest,
    BatchQueryResult,
)

# Storage (advanced users only)
from cherryquant.data.storage.timeseries_repository import TimeSeriesRepository
from cherryquant.data.storage.metadata_repository import MetadataRepository
from cherryquant.data.storage.cache_strategy import CacheStrategy, CacheLevel

# Services (advanced users only)
from cherryquant.data.services.calendar_service import CalendarService
from cherryquant.data.services.contract_service import ContractService


__all__ = [
    # === Core Pipeline ===
    "DataPipeline",

    # === Data Types ===
    "MarketData",
    "ContractInfo",
    "TradingDay",

    # === Enums ===
    "Exchange",
    "TimeFrame",
    "DataSource",

    # === Collectors ===
    "BaseCollector",
    "TushareCollector",

    # === Cleaners ===
    "DataValidator",
    "ValidationResult",
    "ValidationIssue",
    "ValidationLevel",
    "DataNormalizer",
    "QualityController",
    "QualityMetrics",

    # === Query ===
    "QueryBuilder",
    "BatchQueryExecutor",
    "BatchQueryRequest",
    "BatchQueryResult",

    # === Storage (Advanced) ===
    "TimeSeriesRepository",
    "MetadataRepository",
    "CacheStrategy",
    "CacheLevel",

    # === Services (Advanced) ===
    "CalendarService",
    "ContractService",
]

__version__ = "0.1.0-alpha"
