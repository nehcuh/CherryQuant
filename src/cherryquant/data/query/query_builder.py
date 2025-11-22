"""
查询构建器

提供流畅的 API 来构建复杂的市场数据查询。

教学要点：
1. Builder 模式的应用
2. 方法链式调用
3. 查询条件组合
4. 类型安全的查询构建
"""

import logging
from typing import Any
from datetime import datetime
from decimal import Decimal

from cherryquant.data.collectors.base_collector import (
    MarketData,
    Exchange,
    TimeFrame,
)
from cherryquant.data.storage.timeseries_repository import TimeSeriesRepository

logger = logging.getLogger(__name__)


class QueryBuilder:
    """
    查询构建器

    提供流畅的 API 来构建复杂查询。

    使用示例：
    ```python
    query = (QueryBuilder(repository)
        .symbol("rb2501")
        .exchange(Exchange.SHFE)
        .date_range(start_date, end_date)
        .timeframe(TimeFrame.DAY_1)
        .price_range(min_price=3500, max_price=4000)
        .volume_greater_than(10000)
        .limit(100)
    )

    results = await query.execute()
    ```

    教学要点：
    1. Builder 模式
    2. 方法链式调用
    3. 延迟执行（Lazy Evaluation）
    """

    def __init__(self, repository: TimeSeriesRepository):
        """
        初始化查询构建器

        Args:
            repository: 时间序列仓储

        教学要点：
        1. 依赖注入
        2. 状态初始化
        """
        self.repository = repository

        # 查询条件
        self._symbol: str | None = None
        self._exchange: Exchange | None = None
        self._start_date: datetime | None = None
        self._end_date: datetime | None = None
        self._timeframe: TimeFrame = TimeFrame.DAY_1

        # 过滤条件
        self._filters: list[callable] = []

        # 排序和限制
        self._limit: int | None = None
        self._offset: int = 0
        self._sort_by: str = "datetime"
        self._sort_desc: bool = False

    # ==================== 基础查询条件 ====================

    def symbol(self, symbol: str) -> "QueryBuilder":
        """
        设置合约代码

        Args:
            symbol: 合约代码

        Returns:
            self: 支持链式调用

        教学要点：
        1. 流畅接口（Fluent Interface）
        2. 返回 self 实现方法链
        """
        self._symbol = symbol
        return self

    def exchange(self, exchange: Exchange) -> "QueryBuilder":
        """设置交易所"""
        self._exchange = exchange
        return self

    def date_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> "QueryBuilder":
        """
        设置日期范围

        教学要点：
        1. 参数验证
        2. 边界检查
        """
        if start_date > end_date:
            raise ValueError("start_date 必须早于 end_date")

        self._start_date = start_date
        self._end_date = end_date
        return self

    def timeframe(self, timeframe: TimeFrame) -> "QueryBuilder":
        """设置时间周期"""
        self._timeframe = timeframe
        return self

    # ==================== 高级过滤条件 ====================

    def price_range(
        self,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
    ) -> "QueryBuilder":
        """
        按价格范围过滤

        教学要点：
        1. 闭包的使用
        2. 延迟执行
        """
        def filter_func(data: MarketData) -> bool:
            if min_price and data.close < min_price:
                return False
            if max_price and data.close > max_price:
                return False
            return True

        self._filters.append(filter_func)
        return self

    def volume_greater_than(self, min_volume: int) -> "QueryBuilder":
        """按成交量过滤"""
        def filter_func(data: MarketData) -> bool:
            return data.volume >= min_volume

        self._filters.append(filter_func)
        return self

    def volume_range(
        self,
        min_volume: int | None = None,
        max_volume: int | None = None,
    ) -> "QueryBuilder":
        """按成交量范围过滤"""
        def filter_func(data: MarketData) -> bool:
            if min_volume and data.volume < min_volume:
                return False
            if max_volume and data.volume > max_volume:
                return False
            return True

        self._filters.append(filter_func)
        return self

    def price_change_greater_than(self, min_change: float) -> "QueryBuilder":
        """
        按涨跌幅过滤

        教学要点：
        1. 计算逻辑封装
        2. 百分比计算
        """
        def filter_func(data: MarketData) -> bool:
            if data.open == 0:
                return False
            change = float((data.close - data.open) / data.open)
            return abs(change) >= min_change

        self._filters.append(filter_func)
        return self

    def custom_filter(self, filter_func: callable) -> "QueryBuilder":
        """
        自定义过滤条件

        Args:
            filter_func: 过滤函数，接收 MarketData，返回 bool

        教学要点：
        1. 高阶函数
        2. 策略模式
        3. 可扩展性
        """
        self._filters.append(filter_func)
        return self

    # ==================== 排序和分页 ====================

    def order_by(self, field: str, descending: bool = False) -> "QueryBuilder":
        """
        设置排序字段

        Args:
            field: 排序字段（datetime, close, volume, etc.）
            descending: 是否降序

        教学要点：
        1. 排序策略
        2. 字段名映射
        """
        self._sort_by = field
        self._sort_desc = descending
        return self

    def limit(self, limit: int) -> "QueryBuilder":
        """
        限制返回数量

        教学要点：
        1. 分页第一步
        2. 性能优化
        """
        self._limit = limit
        return self

    def offset(self, offset: int) -> "QueryBuilder":
        """
        设置偏移量（分页）

        教学要点：
        1. 分页实现
        2. offset + limit 模式
        """
        self._offset = offset
        return self

    def page(self, page_num: int, page_size: int) -> "QueryBuilder":
        """
        设置分页

        Args:
            page_num: 页码（从1开始）
            page_size: 每页大小

        教学要点：
        1. 分页计算
        2. 用户友好的API
        """
        if page_num < 1:
            raise ValueError("page_num 必须 >= 1")

        self._offset = (page_num - 1) * page_size
        self._limit = page_size
        return self

    # ==================== 执行查询 ====================

    async def execute(self) -> list[MarketData]:
        """
        执行查询

        Returns:
            list[MarketData]: 查询结果

        教学要点：
        1. 延迟执行
        2. 两阶段查询（数据库 + 内存过滤）
        3. 性能优化
        """
        # 验证必要条件
        if not self._symbol:
            raise ValueError("必须设置 symbol")
        if not self._exchange:
            raise ValueError("必须设置 exchange")
        if not self._start_date or not self._end_date:
            raise ValueError("必须设置日期范围")

        # 1. 从数据库查询（基础条件）
        logger.debug(
            f"执行查询: {self._symbol}.{self._exchange.value} "
            f"({self._start_date.date()} 到 {self._end_date.date()})"
        )

        data = await self.repository.query(
            symbol=self._symbol,
            exchange=self._exchange,
            start_date=self._start_date,
            end_date=self._end_date,
            timeframe=self._timeframe,
        )

        # 2. 应用内存过滤
        if self._filters:
            original_count = len(data)
            for filter_func in self._filters:
                data = [d for d in data if filter_func(d)]

            logger.debug(
                f"过滤后: {len(data)}/{original_count} 条"
            )

        # 3. 排序
        if self._sort_by:
            data = self._sort_data(data)

        # 4. 分页
        if self._offset or self._limit:
            data = self._paginate_data(data)

        logger.info(f"✅ 查询完成: {len(data)} 条数据")

        return data

    async def count(self) -> int:
        """
        统计符合条件的数据量（不执行查询）

        教学要点：
        1. 优化的计数查询
        2. 避免加载全部数据
        """
        if not self._filters:
            # 如果没有内存过滤，直接用数据库统计
            return await self.repository.count(
                symbol=self._symbol,
                exchange=self._exchange,
                timeframe=self._timeframe,
                start_date=self._start_date,
                end_date=self._end_date,
            )

        # 有内存过滤，需要执行查询
        results = await self.execute()
        return len(results)

    async def first(self) -> MarketData | None:
        """
        获取第一条数据

        教学要点：
        1. 限制查询优化
        2. 快速返回
        """
        original_limit = self._limit
        self._limit = 1

        results = await self.execute()

        # 恢复原始限制
        self._limit = original_limit

        return results[0] if results else None

    async def last(self) -> MarketData | None:
        """获取最后一条数据"""
        original_sort = (self._sort_by, self._sort_desc)
        self._sort_by = "datetime"
        self._sort_desc = True
        self._limit = 1

        results = await self.execute()

        # 恢复原始设置
        self._sort_by, self._sort_desc = original_sort

        return results[0] if results else None

    # ==================== 聚合操作 ====================

    async def aggregate(self, func: str) -> Any:
        """
        执行聚合操作

        Args:
            func: 聚合函数（avg, sum, max, min）

        Returns:
            聚合结果

        教学要点：
        1. 聚合函数实现
        2. 统计计算
        """
        data = await self.execute()

        if not data:
            return None

        if func == "avg":
            return sum(float(d.close) for d in data) / len(data)
        elif func == "sum":
            return sum(float(d.close) for d in data)
        elif func == "max":
            return max(float(d.close) for d in data)
        elif func == "min":
            return min(float(d.close) for d in data)
        else:
            raise ValueError(f"不支持的聚合函数: {func}")

    async def avg_price(self) -> Decimal | None:
        """计算平均价格"""
        result = await self.aggregate("avg")
        return Decimal(str(result)) if result else None

    async def max_price(self) -> Decimal | None:
        """获取最高价"""
        result = await self.aggregate("max")
        return Decimal(str(result)) if result else None

    async def min_price(self) -> Decimal | None:
        """获取最低价"""
        result = await self.aggregate("min")
        return Decimal(str(result)) if result else None

    async def total_volume(self) -> int:
        """计算总成交量"""
        data = await self.execute()
        return sum(d.volume for d in data)

    # ==================== 辅助方法 ====================

    def _sort_data(self, data: list[MarketData]) -> list[MarketData]:
        """
        排序数据

        教学要点：
        1. 动态属性访问
        2. 排序键函数
        """
        def get_sort_key(d: MarketData):
            # 根据字段名获取属性值
            if self._sort_by == "datetime":
                return d.datetime
            elif self._sort_by == "close":
                return d.close
            elif self._sort_by == "volume":
                return d.volume
            elif self._sort_by == "open_interest":
                return d.open_interest or 0
            else:
                return getattr(d, self._sort_by, 0)

        return sorted(
            data,
            key=get_sort_key,
            reverse=self._sort_desc,
        )

    def _paginate_data(self, data: list[MarketData]) -> list[MarketData]:
        """
        分页数据

        教学要点：
        1. 列表切片
        2. 边界处理
        """
        start = self._offset
        end = start + self._limit if self._limit else None

        return data[start:end]

    def clone(self) -> "QueryBuilder":
        """
        克隆查询构建器

        Returns:
            新的查询构建器实例

        教学要点：
        1. 深拷贝 vs 浅拷贝
        2. 原型模式
        """
        new_builder = QueryBuilder(self.repository)

        # 复制所有条件
        new_builder._symbol = self._symbol
        new_builder._exchange = self._exchange
        new_builder._start_date = self._start_date
        new_builder._end_date = self._end_date
        new_builder._timeframe = self._timeframe
        new_builder._filters = self._filters.copy()
        new_builder._limit = self._limit
        new_builder._offset = self._offset
        new_builder._sort_by = self._sort_by
        new_builder._sort_desc = self._sort_desc

        return new_builder

    def __repr__(self) -> str:
        """字符串表示"""
        conditions = []

        if self._symbol:
            conditions.append(f"symbol={self._symbol}")
        if self._exchange:
            conditions.append(f"exchange={self._exchange.value}")
        if self._start_date and self._end_date:
            conditions.append(
                f"date_range={self._start_date.date()}~{self._end_date.date()}"
            )
        if self._filters:
            conditions.append(f"filters={len(self._filters)}")
        if self._limit:
            conditions.append(f"limit={self._limit}")

        return f"<QueryBuilder({', '.join(conditions)})>"
