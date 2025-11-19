# CherryQuant 课程讲义 - 第2章：数据管道

## 2.1 数据管道的重要性
在量化交易系统中，数据是"燃料"。高质量、低延迟的数据是 AI 做出正确决策的前提。CherryQuant 的数据管道设计旨在解决以下问题：
- **多源异构**: 如何统一处理来自 Tushare (API)、SimNow (CTP)、数据库 (SQL) 的数据？
- **实时性**: 如何在 Live 模式下保证数据的实时性？
- **容错性**: 当某个数据源挂掉时，系统如何继续运行？

## 2.2 核心组件：Market Data Manager

`MarketDataManager` (`src/cherryquant/adapters/data_adapter/market_data_manager.py`) 是数据管道的核心枢纽。它定义了统一的接口 `MarketDataSource`，并管理着多个具体的数据源实现。

### 架构图
```mermaid
graph LR
    Client[AI Engine / Strategy] --> MDM[Market Data Manager]
    
    subgraph "Data Sources"
        MDM --> |Priority 1| DB[Database (TimescaleDB)]
        MDM --> |Priority 2| SimNow[SimNow (Live Price)]
        MDM --> |Priority 3| Tushare[Tushare Pro (History)]
    end
    
    SimNow --> CTP[CTP Gateway]
    Tushare --> HTTP[HTTP API]
```

### 关键代码解析
```python
async def get_realtime_data(self, symbol: str) -> Dict[str, Any]:
    """获取实时数据（带降级机制）"""
    # 1. 尝试从主数据源获取
    data = await self.primary_source.get_price(symbol)
    if data:
        return data
        
    # 2. 失败则尝试备用数据源
    logger.warning(f"主数据源失效，切换到备用源: {symbol}")
    for source in self.fallback_sources:
        data = await source.get_price(symbol)
        if data:
            return data
            
    raise DataError(f"所有数据源均无法获取 {symbol} 的数据")
```

## 2.3 合约解析器 (Contract Resolver)

期货交易的一个特殊痛点是**主力合约换月**。例如，螺纹钢的主力合约可能是 `rb2501`，下个月可能变成 `rb2505`。

`ContractResolver` (`src/cherryquant/adapters/data_adapter/contract_resolver.py`) 解决了这个问题：
1.  **动态查询**: 通过 Tushare API 查询当前交易所规定的主力合约。
2.  **智能缓存**: 将查询结果缓存 1 小时，避免频繁请求 API。
3.  **规则推断**: 如果 API 不可用，根据日期规则（如"螺纹钢主力通常是 1 月、5 月、10 月"）进行推断。

## 2.4 数据流转实战

### 场景：AI 请求 "螺纹钢" 的最新行情

1.  **请求**: AI Engine 调用 `get_market_data("rb")`。
2.  **解析**: `ContractResolver` 将 `rb` 解析为 `rb2501.SHFE`。
3.  **路由**: `MarketDataManager` 根据当前模式 (`Dev` vs `Live`) 选择数据源。
    - **Dev 模式**: 调用 `TushareDataSource` 获取历史 K 线（模拟实时）。
    - **Live 模式**: 调用 `SimNowDataSource` 通过 `VNPyGateway` 获取内存中的最新 Tick。
4.  **标准化**: 将不同来源的数据统一格式化为标准字典（包含 `open`, `high`, `low`, `close`, `volume` 等）。
5.  **返回**: AI Engine 收到标准化的数据。

## 2.5 思考题
1.  如果我们在盘中（交易时间）重启了系统，`MarketDataManager` 如何保证数据的连续性？
2.  `SimNowDataSource` 为什么不能提供长周期的 K 线数据？我们该如何解决这个问题？
