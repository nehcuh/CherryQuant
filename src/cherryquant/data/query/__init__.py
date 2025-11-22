"""数据查询模块

提供灵活的查询和聚合功能：
- 查询构建器 (query_builder): 复杂查询条件构建
- 数据聚合器 (aggregator): 数据聚合和计算
- 批量查询优化 (batch_query): 批量查询性能优化

教学价值：
1. Builder 模式应用
2. 查询优化策略
3. 批量操作模式
"""

from cherryquant.data.query.query_builder import QueryBuilder
from cherryquant.data.query.batch_query import BatchQueryExecutor

__all__ = [
    "QueryBuilder",
    "BatchQueryExecutor",
]
