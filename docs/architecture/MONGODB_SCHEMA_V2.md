# MongoDB Schema 设计 v2.0

> 优化后的时间序列数据库架构
>
> 作者：CherryQuant Team
> 更新日期：2025-11-21

## 概述

本文档描述了 CherryQuant 项目中 MongoDB 数据库的优化架构设计。相比 v1.0，v2.0 版本重点优化了：

1. **时间序列集合优化**：充分利用 MongoDB 5.0+ 的时间序列特性
2. **索引策略改进**：针对量化交易场景优化查询性能
3. **数据分片设计**：支持大规模数据的水平扩展
4. **压缩策略**：减少存储空间占用

## 数据库结构

```
CherryQuant MongoDB Database
│
├── 时间序列集合 (Time Series Collections)
│   ├── market_data_1m       # 1分钟K线数据
│   ├── market_data_5m       # 5分钟K线数据
│   ├── market_data_15m      # 15分钟K线数据
│   ├── market_data_1h       # 1小时K线数据
│   ├── market_data_1d       # 日线数据
│   └── technical_indicators # 技术指标数据
│
├── 元数据集合 (Metadata Collections)
│   ├── futures_contracts    # 期货合约信息
│   ├── trading_calendar     # 交易日历
│   └── contract_specs       # 合约规格
│
├── 交易数据集合 (Trading Collections)
│   ├── trades               # 交易记录
│   ├── positions            # 持仓记录
│   └── portfolio_states     # 组合状态快照
│
└── AI数据集合 (AI Collections)
    ├── ai_decisions         # AI决策记录
    ├── training_features    # 特征工程数据
    └── model_predictions    # 模型预测结果
```

## 时间序列集合设计

### 1. market_data_1d (日线数据)

**集合类型：** Time Series Collection

**时间字段：** `datetime`
**元数据字段：** `{ symbol, exchange }`

#### Schema 定义

```javascript
{
  // 时间戳 (timeseries timeField)
  datetime: ISODate("2024-01-15T00:00:00Z"),

  // 元数据 (timeseries metaField)
  metadata: {
    symbol: "rb2501",        // 合约代码
    exchange: "SHFE",        // 交易所
    underlying: "rb"         // 标的代码
  },

  // OHLCV 数据
  open: NumberDecimal("3500.0"),
  high: NumberDecimal("3520.0"),
  low: NumberDecimal("3480.0"),
  close: NumberDecimal("3510.0"),
  volume: NumberLong(10000),

  // 期货特有数据
  open_interest: NumberLong(5000),
  turnover: NumberDecimal("175000000.0"),

  // 数据来源
  source: "tushare",         // 数据源：tushare, vnpy, quantbox
  collected_at: ISODate("2024-01-15T15:00:00Z"),

  // 数据质量标记
  quality_score: NumberDecimal("0.95"),  // 0-1
  is_validated: true,
  validation_issues: []      // 如果有问题，记录详情
}
```

#### 索引策略

```javascript
// 1. 复合索引：symbol + exchange + datetime (最常用查询)
db.market_data_1d.createIndex(
  { "metadata.symbol": 1, "metadata.exchange": 1, datetime: 1 },
  { name: "symbol_exchange_datetime" }
)

// 2. 单字段索引：datetime (时间范围查询)
db.market_data_1d.createIndex(
  { datetime: 1 },
  { name: "datetime" }
)

// 3. 复合索引：underlying + datetime (品种级别查询)
db.market_data_1d.createIndex(
  { "metadata.underlying": 1, datetime: 1 },
  { name: "underlying_datetime" }
)

// 4. 复合索引：source + datetime (数据源追踪)
db.market_data_1d.createIndex(
  { source: 1, datetime: 1 },
  { name: "source_datetime", sparse: true }
)
```

#### 集合选项

```javascript
db.createCollection("market_data_1d", {
  timeseries: {
    timeField: "datetime",
    metaField: "metadata",
    granularity: "hours"     // 日线数据按小时粒度聚合
  },
  expireAfterSeconds: 31536000,  // 1年后自动删除旧数据
  storageEngine: {
    wiredTiger: {
      configString: "block_compressor=zstd"  // 使用 zstd 压缩
    }
  }
})
```

### 2. market_data_1m (分钟线数据)

**设计思路：** 分钟线数据量巨大，需要特别优化

#### Schema 定义

```javascript
{
  datetime: ISODate("2024-01-15T09:30:00Z"),

  metadata: {
    symbol: "rb2501",
    exchange: "SHFE",
    underlying: "rb"
  },

  // OHLCV (与日线相同)
  open: NumberDecimal("3500.0"),
  high: NumberDecimal("3502.0"),
  low: NumberDecimal("3498.0"),
  close: NumberDecimal("3501.0"),
  volume: NumberLong(100),

  // 期货数据
  open_interest: NumberLong(5000),
  turnover: NumberDecimal("1750000.0"),

  // Tick 级别的额外信息（可选）
  tick_count: NumberInt(120),  // 本分钟内的 tick 数量
  bid_ask_spread: NumberDecimal("1.0"),  // 平均买卖价差

  source: "vnpy",
  collected_at: ISODate("2024-01-15T09:30:05Z")
}
```

#### 索引策略

```javascript
// 1. 主索引：symbol + exchange + datetime
db.market_data_1m.createIndex(
  { "metadata.symbol": 1, "metadata.exchange": 1, datetime: 1 },
  { name: "symbol_exchange_datetime" }
)

// 2. 仅 datetime（时间范围扫描）
db.market_data_1m.createIndex(
  { datetime: 1 },
  { name: "datetime" }
)
```

#### 集合选项

```javascript
db.createCollection("market_data_1m", {
  timeseries: {
    timeField: "datetime",
    metaField: "metadata",
    granularity: "minutes"   // 分钟级粒度
  },
  expireAfterSeconds: 7776000,  // 90天后删除（存储压力大）
  storageEngine: {
    wiredTiger: {
      configString: "block_compressor=zstd"
    }
  }
})
```

### 3. technical_indicators (技术指标)

**设计思路：** 技术指标与市场数据分开存储，便于独立管理

#### Schema 定义

```javascript
{
  datetime: ISODate("2024-01-15T00:00:00Z"),

  metadata: {
    symbol: "rb2501",
    exchange: "SHFE",
    timeframe: "1d"          // 指标对应的K线周期
  },

  // 趋势指标
  ma_5: NumberDecimal("3495.0"),
  ma_10: NumberDecimal("3490.0"),
  ma_20: NumberDecimal("3485.0"),
  ma_60: NumberDecimal("3480.0"),
  ema_12: NumberDecimal("3496.0"),
  ema_26: NumberDecimal("3488.0"),

  // 动量指标
  rsi_6: NumberDecimal("55.3"),
  rsi_12: NumberDecimal("58.1"),
  rsi_24: NumberDecimal("52.7"),

  // MACD
  macd_value: NumberDecimal("12.5"),
  macd_signal: NumberDecimal("10.2"),
  macd_hist: NumberDecimal("2.3"),

  // 波动率指标
  atr_14: NumberDecimal("25.5"),
  bollinger_upper: NumberDecimal("3530.0"),
  bollinger_middle: NumberDecimal("3500.0"),
  bollinger_lower: NumberDecimal("3470.0"),

  // 成交量指标
  volume_ma_5: NumberDecimal("120000.0"),
  obv: NumberDecimal("5000000.0"),

  // 计算信息
  calculated_at: ISODate("2024-01-15T15:00:00Z"),
  algorithm_version: "v1.0"
}
```

#### 索引策略

```javascript
// 主索引
db.technical_indicators.createIndex(
  { "metadata.symbol": 1, "metadata.timeframe": 1, datetime: 1 },
  { name: "symbol_timeframe_datetime" }
)
```

## 元数据集合设计

### 4. futures_contracts (期货合约)

**集合类型：** 普通集合（非时间序列）

#### Schema 定义

```javascript
{
  _id: ObjectId("..."),

  // 基本信息
  symbol: "rb2501",                    // 合约代码
  name: "螺纹钢2501",                  // 合约名称
  exchange: "SHFE",                    // 交易所
  underlying: "rb",                    // 标的代码

  // 合约规格
  multiplier: NumberInt(10),           // 合约乘数
  price_tick: NumberDecimal("1.0"),    // 最小变动价位
  price_unit: "元/吨",                  // 价格单位
  contract_size: NumberInt(10),        // 合约大小（吨）

  // 日期信息
  list_date: ISODate("2024-01-15"),    // 上市日期
  first_trade_date: ISODate("2024-01-15"),  // 首个交易日
  last_trade_date: ISODate("2025-01-14"),   // 最后交易日
  expire_date: ISODate("2025-01-15"),  // 到期日期
  delivery_month: "2501",              // 交割月份

  // 交易规则
  margin_rate: NumberDecimal("0.08"),  // 保证金比率
  commission_rate: NumberDecimal("0.0001"),  // 手续费率
  price_limit_up: NumberDecimal("0.05"),     // 涨停限制
  price_limit_down: NumberDecimal("0.05"),   // 跌停限制

  // 状态
  is_active: true,                     // 是否在交易
  is_main_contract: true,              // 是否主力合约

  // 元数据
  created_at: ISODate("2024-01-01"),
  updated_at: ISODate("2024-01-15"),
  data_source: "tushare"
}
```

#### 索引策略

```javascript
// 1. 唯一索引：symbol + exchange
db.futures_contracts.createIndex(
  { symbol: 1, exchange: 1 },
  { name: "symbol_exchange", unique: true }
)

// 2. underlying + is_main_contract（查询主力合约）
db.futures_contracts.createIndex(
  { underlying: 1, is_main_contract: 1 },
  { name: "underlying_main" }
)

// 3. expire_date（查询即将到期合约）
db.futures_contracts.createIndex(
  { expire_date: 1 },
  { name: "expire_date" }
)

// 4. is_active（过滤活跃合约）
db.futures_contracts.createIndex(
  { is_active: 1 },
  { name: "is_active", sparse: true }
)
```

### 5. trading_calendar (交易日历)

#### Schema 定义

```javascript
{
  _id: ObjectId("..."),

  date: ISODate("2024-01-15"),         // 日期
  exchange: "SHFE",                    // 交易所
  is_trading_day: true,                // 是否交易日

  // 交易时段
  trading_sessions: [
    {
      name: "morning",
      start_time: "09:00:00",
      end_time: "10:15:00"
    },
    {
      name: "morning_2",
      start_time: "10:30:00",
      end_time: "11:30:00"
    },
    {
      name: "afternoon",
      start_time: "13:30:00",
      end_time: "15:00:00"
    },
    {
      name: "night",
      start_time: "21:00:00",
      end_time: "23:00:00"
    }
  ],

  // 相邻交易日
  prev_trading_day: ISODate("2024-01-12"),
  next_trading_day: ISODate("2024-01-16"),

  // 假日信息
  is_holiday: false,
  holiday_name: null,

  created_at: ISODate("2024-01-01"),
  data_source: "tushare"
}
```

#### 索引策略

```javascript
// 1. 复合唯一索引：date + exchange
db.trading_calendar.createIndex(
  { date: 1, exchange: 1 },
  { name: "date_exchange", unique: true }
)

// 2. is_trading_day（快速查询交易日）
db.trading_calendar.createIndex(
  { is_trading_day: 1, date: 1 },
  { name: "is_trading_day_date" }
)
```

## 交易数据集合设计

### 6. trades (交易记录)

#### Schema 定义

```javascript
{
  _id: ObjectId("..."),

  // 交易标识
  trade_id: "T20240115093001",         // 交易ID
  order_id: "O20240115093000",         // 订单ID

  // 合约信息
  symbol: "rb2501",
  exchange: "SHFE",

  // 交易细节
  direction: "LONG",                   // LONG, SHORT
  offset: "OPEN",                      // OPEN, CLOSE
  price: NumberDecimal("3510.0"),      // 成交价
  volume: NumberInt(2),                // 成交量（手）

  // 时间
  trade_datetime: ISODate("2024-01-15T09:30:01Z"),

  // 策略信息
  strategy_id: "ai_selection_01",
  strategy_version: "v1.0",

  // AI 决策关联
  ai_decision_id: ObjectId("..."),     // 关联的AI决策

  // 费用
  commission: NumberDecimal("7.02"),   // 手续费
  slippage: NumberDecimal("1.0"),      // 滑点

  // PnL（如果是平仓）
  pnl: NumberDecimal("300.0"),         // 盈亏
  pnl_rate: NumberDecimal("0.0285"),   // 盈亏率

  // 状态
  status: "FILLED",                    // PENDING, PARTIAL, FILLED, CANCELLED

  created_at: ISODate("2024-01-15T09:30:01Z")
}
```

#### 索引策略

```javascript
// 1. trade_id 唯一索引
db.trades.createIndex(
  { trade_id: 1 },
  { name: "trade_id", unique: true }
)

// 2. symbol + trade_datetime（查询特定合约交易历史）
db.trades.createIndex(
  { symbol: 1, trade_datetime: 1 },
  { name: "symbol_datetime" }
)

// 3. strategy_id + trade_datetime（策略级别分析）
db.trades.createIndex(
  { strategy_id: 1, trade_datetime: 1 },
  { name: "strategy_datetime" }
)
```

### 7. ai_decisions (AI决策记录)

#### Schema 定义

```javascript
{
  _id: ObjectId("..."),

  // 决策信息
  decision_id: "D20240115093000",
  timestamp: ISODate("2024-01-15T09:30:00Z"),

  // 合约信息
  symbol: "rb2501",
  exchange: "SHFE",

  // 决策结果
  decision: "BUY",                     // BUY, SELL, HOLD
  confidence: NumberDecimal("0.85"),   // 置信度 0-1
  recommended_volume: NumberInt(2),    // 建议手数

  // AI 模型信息
  model: "gpt-4",
  model_version: "gpt-4-1106-preview",

  // Prompt 和 Reasoning
  prompt: "分析 rb2501 的市场趋势...",
  reasoning: "基于技术分析，当前RSI为55.3，MACD金叉...",
  raw_response: "{...}",               // AI 原始响应

  // 输入数据快照
  input_data: {
    market_data: {
      close: NumberDecimal("3510.0"),
      volume: NumberLong(10000),
      // ... 其他数据
    },
    technical_indicators: {
      rsi_14: NumberDecimal("55.3"),
      macd_value: NumberDecimal("12.5"),
      // ... 其他指标
    }
  },

  // 成本信息
  token_usage: {
    prompt_tokens: NumberInt(1200),
    completion_tokens: NumberInt(350),
    total_tokens: NumberInt(1550)
  },
  cost_usd: NumberDecimal("0.025"),

  // 执行结果（如果已执行）
  execution_status: "EXECUTED",        // PENDING, EXECUTED, REJECTED, FAILED
  actual_trade_id: "T20240115093001",

  // 回测评估（如果有）
  backtesting_pnl: NumberDecimal("300.0"),

  created_at: ISODate("2024-01-15T09:30:00Z")
}
```

#### 索引策略

```javascript
// 1. decision_id 唯一索引
db.ai_decisions.createIndex(
  { decision_id: 1 },
  { name: "decision_id", unique: true }
)

// 2. symbol + timestamp（查询特定合约的决策历史）
db.ai_decisions.createIndex(
  { symbol: 1, timestamp: 1 },
  { name: "symbol_timestamp" }
)

// 3. model + timestamp（模型性能分析）
db.ai_decisions.createIndex(
  { model: 1, timestamp: 1 },
  { name: "model_timestamp" }
)

// 4. decision + confidence（决策分布分析）
db.ai_decisions.createIndex(
  { decision: 1, confidence: 1 },
  { name: "decision_confidence" }
)
```

## 数据分片策略（可选）

当数据量达到TB级别时，考虑分片：

### 分片键选择

```javascript
// 1. market_data 集合：按 { metadata.symbol, datetime } 分片
sh.shardCollection("cherryquant.market_data_1d", {
  "metadata.symbol": 1,
  "datetime": 1
})

// 2. trades 集合：按 { symbol, trade_datetime } 分片
sh.shardCollection("cherryquant.trades", {
  "symbol": 1,
  "trade_datetime": 1
})
```

## 数据生命周期管理

### TTL 策略

```javascript
// 1. 分钟线数据：90天后删除
db.market_data_1m.createIndex(
  { "datetime": 1 },
  { expireAfterSeconds: 7776000 }  // 90天
)

// 2. 日线数据：1年后删除
db.market_data_1d.createIndex(
  { "datetime": 1 },
  { expireAfterSeconds: 31536000 }  // 1年
)

// 3. AI 决策：6个月后删除
db.ai_decisions.createIndex(
  { "timestamp": 1 },
  { expireAfterSeconds: 15552000 }  // 6个月
)
```

### 归档策略

```javascript
// 对于重要的历史数据，定期归档到冷存储
// 1. 导出到 S3/OSS
// 2. 压缩为 Parquet 格式
// 3. 保留元数据索引
```

## 性能优化建议

### 1. 查询优化

```javascript
// ✅ 好的查询（使用索引）
db.market_data_1d.find({
  "metadata.symbol": "rb2501",
  "metadata.exchange": "SHFE",
  "datetime": {
    $gte: ISODate("2024-01-01"),
    $lte: ISODate("2024-01-31")
  }
})

// ❌ 差的查询（全表扫描）
db.market_data_1d.find({
  "close": { $gt: 3500 }
})
```

### 2. 聚合优化

```javascript
// 使用聚合管道计算指标
db.market_data_1d.aggregate([
  {
    $match: {
      "metadata.symbol": "rb2501",
      "datetime": { $gte: ISODate("2024-01-01") }
    }
  },
  {
    $group: {
      _id: null,
      avg_volume: { $avg: "$volume" },
      max_high: { $max: "$high" },
      min_low: { $min: "$low" }
    }
  }
])
```

### 3. 批量写入优化

```python
# Python 示例：使用 bulk_write
from pymongo import InsertOne

operations = [
    InsertOne(data.to_dict())
    for data in market_data_list
]

result = collection.bulk_write(
    operations,
    ordered=False  # 无序写入更快
)
```

## 监控指标

### 关键监控点

1. **存储空间**：
   - 每个集合的大小
   - 索引大小占比
   - 压缩率

2. **查询性能**：
   - 平均查询时间
   - 慢查询（>100ms）
   - 索引命中率

3. **写入性能**：
   - 写入TPS
   - 批量写入延迟
   - 写冲突率

### 监控命令

```javascript
// 1. 查看集合统计
db.market_data_1d.stats()

// 2. 查看索引使用情况
db.market_data_1d.aggregate([
  { $indexStats: {} }
])

// 3. 查看慢查询
db.system.profile.find({
  millis: { $gt: 100 }
}).sort({ ts: -1 }).limit(10)
```

## 教学要点总结

本 Schema 设计展示了以下数据库设计原则：

1. **时间序列优化**：利用 MongoDB 原生时间序列特性
2. **索引策略**：根据查询模式设计复合索引
3. **数据分离**：市场数据、元数据、交易数据分开存储
4. **生命周期管理**：TTL 索引自动清理过期数据
5. **性能优化**：批量操作、压缩、分片
6. **可观测性**：完整的监控指标

学生可以通过实际操作这些集合，学习：
- NoSQL 数据库设计
- 时间序列数据处理
- 查询优化技巧
- 数据生命周期管理
- 生产环境最佳实践

---

**版本历史**

- v1.0 (2024-11): 初始版本，基于 PostgreSQL 迁移
- v2.0 (2024-11-21): 重新设计，优化教学和性能
