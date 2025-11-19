# CherryQuant 数据库迁移规划

## 📋 概述

本文档描述了 CherryQuant 从 PostgreSQL + MongoDB 双数据库架构到统一 MongoDB 架构的渐进式迁移方案。

## 🎯 迁移目标

- **简化架构**: 统一使用 MongoDB，减少维护复杂度
- **提升性能**: 利用 MongoDB 在时序数据方面的优势
- **降低成本**: 减少数据库服务器资源占用
- **改善一致性**: 统一的数据模型和查询接口

## 📊 当前架构分析

### PostgreSQL 数据表
```sql
-- AI 决策相关
ai_decisions                 -- AI 交易决策记录
strategy_performance        -- 策略性能统计
ai_signals                  -- AI 信号历史

-- 交易相关
trades                      -- 交易执行记录
portfolio_status            -- 组合状态
strategy_trades             -- 策略交易记录

-- 市场数据（待迁移）
market_data                 -- K线数据
technical_indicators        -- 技术指标
```

### MongoDB 集合 (通过 QuantBox)
```javascript
// 市场数据
trade_date                  -- 交易日历
future_contracts           -- 期货合约
future_daily               -- 期货日线
future_holdings            -- 期货持仓

// 缓存数据
cache_*                     -- 各类缓存数据
```

## 🚀 分阶段迁移方案

### 第一阶段：现状稳定期 (1-2个月)

**目标**: 保持当前双数据库架构，确保系统稳定

**任务**:
- [x] 集成 QuantBox，验证 MongoDB 市场数据处理
- [ ] 监控双数据库性能和稳定性
- [ ] 收集数据访问模式和性能指标
- [ ] 准备数据迁移工具

**风险评估**: 🟢 低风险

### 第二阶段：市场数据统一 (2-3个月)

**目标**: 将所有市场数据从 PostgreSQL 迁移到 MongoDB

**迁移数据**:
```sql
-- 从 PostgreSQL 迁移到 MongoDB
market_data → quantbox.market_data
technical_indicators → quantbox.technical_indicators
```

**实施步骤**:
1. **数据备份**:
```bash
# 备份 PostgreSQL 数据
pg_dump cherryquant > backup_20241212.sql

# 备份 MongoDB 数据
mongodump --db quantbox
```

2. **数据迁移脚本**:
```python
# scripts/migrate_market_data.py
async def migrate_market_data():
    """迁移市场数据到 MongoDB"""

    # 1. 从 PostgreSQL 读取数据
    pg_data = await postgres_manager.get_market_data()

    # 2. 转换格式
    mongo_docs = convert_to_mongo_format(pg_data)

    # 3. 写入 MongoDB
    await quantbox_adapter.batch_insert(mongo_docs)
```

3. **双写验证**:
```python
# 在迁移期间同时写入两个数据库
async def save_market_data_dual(data):
    # 写入 PostgreSQL (现有)
    await postgres_manager.save_market_data(data)

    # 写入 MongoDB (新增)
    await quantbox_adapter.save_market_data(data)
```

4. **切换读取源**:
```python
# 逐步切换读取优先级
manager = HistoryDataManager(
    prefer_quantbox=True,    # 优先从 MongoDB 读取
    enable_dual_write=True   # 同时写入两个数据库
)
```

**风险评估**: 🟡 中等风险

### 第三阶段：AI/交易数据迁移 (3-4个月)

**目标**: 将 AI 决策和交易数据迁移到 MongoDB

**迁移数据**:
```sql
ai_decisions → quantbox.ai_decisions
strategy_performance → quantbox.strategy_performance
trades → quantbox.trades
portfolio_status → quantbox.portfolio_status
```

**数据模型设计**:
```javascript
// MongoDB 集合设计
{
  _id: ObjectId,
  decision_time: ISODate,
  symbol: String,
  exchange: String,
  action: String,  // "buy", "sell", "hold"
  quantity: Number,
  confidence: Number,
  ai_model: String,
  market_conditions: Object,
  technical_signals: Array,
  risk_factors: Array,
  execution_result: Object
}
```

**风险评估**: 🟠 中高风险

### 第四阶段：完全统一 (1个月)

**目标**: 完全移除 PostgreSQL 依赖

**任务**:
- [ ] 移除 PostgreSQL 连接和依赖
- [ ] 更新所有配置文件
- [ ] 清理 PostgreSQL 数据库
- [ ] 性能测试和优化

**风险评估**: 🔴 高风险

## 📈 迁移收益分析

### 当前双数据库架构
```
优势:
✅ 数据隔离，风险分散
✅ 各数据库发挥特长

劣势:
❌ 维护复杂度高
❌ 成本高（两套数据库）
❌ 数据一致性挑战
❌ 开发复杂度高
```

### 统一 MongoDB 架构
```
优势:
✅ 架构简化，维护容易
✅ 成本降低
✅ 数据一致性好
✅ 开发效率高
✅ 时序数据性能优

劣势:
❌ 单点故障风险
❌ 需要数据备份策略
```

## 🛡️ 风险控制措施

### 1. 数据安全
```bash
# 迁移前完整备份
pg_dump --format=custom cherryquant > pg_backup.dump
mongodump --db quantbox --out mongo_backup/

# 定期增量备份
pg_dump --format=custom --incremental cherryquant > pg_incremental.dump
```

### 2. 回滚计划
```python
# 快速回滚开关
ENABLE_MONGODB = os.getenv("ENABLE_MONGODB", "true") == "true"
ENABLE_POSTGRES = os.getenv("ENABLE_POSTGRES", "false") == "true"

class DatabaseManager:
    def __init__(self):
        self.use_mongodb = ENABLE_MONGODB
        self.use_postgres = ENABLE_POSTGRES
```

### 3. 渐进式切换
```python
# 支持细粒度控制
class DataSourceConfig:
    market_data = "mongodb"      # 或 "postgres"
    ai_decisions = "postgres"     # 或 "mongodb"
    trades = "postgres"           # 或 "mongodb"
    user_data = "postgres"        # 或 "mongodb"
```

### 4. 监控和告警
```python
# 数据一致性检查
async def check_data_consistency():
    """检查两个数据库的数据一致性"""
    pg_count = await postgres_manager.count_market_data()
    mongo_count = await mongo_manager.count_market_data()

    if abs(pg_count - mongo_count) > 1000:
        send_alert("数据不一致告警")
```

## 📅 时间规划

| 阶段 | 时间 | 主要任务 | 风险等级 |
|------|------|----------|----------|
| 第一阶段 | 1-2月 | 稳定集成，收集指标 | 🟢 低 |
| 第二阶段 | 3-4月 | 市场数据迁移 | 🟡 中 |
| 第三阶段 | 5-6月 | AI/交易数据迁移 | 🟠 中高 |
| 第四阶段 | 7月 | 完全统一，清理 | 🔴 高 |

## 🎯 建议

### 推荐方案：**渐进式迁移**

**理由**:
1. **风险可控**: 分阶段实施，每个阶段都可以回滚
2. **收益明确**: 每个阶段都有明确的收益
3. **影响最小**: 对现有系统影响最小
4. **经验积累**: 每个阶段都能积累迁移经验

### 不推荐的方案：

**激进迁移** (一次性全部迁移)
- 风险太高，影响业务连续性
- 没有回滚余地
- 缺乏迁移经验

**保持现状** (不迁移)
- 维护成本持续增加
- 错失性能优化机会
- 技术债务积累

## 📋 检查清单

### 迁移前准备
- [ ] 完整数据备份
- [ ] 迁移工具开发测试
- [ ] 性能基准测试
- [ ] 回滚方案准备
- [ ] 团队培训

### 迁移过程
- [ ] 数据一致性验证
- [ ] 性能监控
- [ ] 错误日志收集
- [ ] 用户反馈收集

### 迁移后
- [ ] 性能对比测试
- [ ] 数据清理
- [ ] 文档更新
- [ ] 经验总结

---

**建议**: 优先完成第二阶段（市场数据统一），这是收益最大、风险最小的方案。第三阶段可以根据第二阶段的效果决定是否继续。