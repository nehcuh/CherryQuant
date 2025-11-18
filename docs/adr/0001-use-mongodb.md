# ADR-0001: 使用 MongoDB 作为主数据库

## 状态
Accepted

## 背景

CherryQuant 是一个 AI 驱动的期货交易系统，需要存储和查询大量的时间序列数据：
- 历史 K 线数据（分钟级、日级）
- 实时行情数据
- 交易决策记录
- 持仓和资金变化历史

### 当前挑战

1. **数据量大**：每天产生数百万条行情数据
2. **写入频率高**：实时行情需要高频写入（每秒数千条）
3. **查询模式多样**：
   - 时间范围查询（某品种在某时间段的数据）
   - 聚合查询（计算技术指标）
   - 最新数据查询（当前价格、持仓）

4. **QuantBox 集成**：我们计划集成 QuantBox 进行高性能数据管理，QuantBox 原生支持 MongoDB

### 技术约束

- 需要支持异步 I/O（async/await）
- 希望避免复杂的 schema 迁移
- 团队对 NoSQL 有一定经验

## 决策

我们将使用 **MongoDB** 作为 CherryQuant 的主数据库，用于存储：
- 历史市场数据（时间序列集合）
- 交易决策记录
- 策略配置
- 系统状态

### 关键设计要素

1. **使用 Time Series Collections**
   ```python
   db.create_collection(
       "market_data",
       timeseries={
           "timeField": "timestamp",
           "metaField": "symbol",
           "granularity": "minutes"
       }
   )
   ```

2. **异步访问**
   - 使用 `motor` 作为异步 MongoDB 驱动
   - 所有数据库操作都是 async/await

3. **连接池管理**
   - 实现 `MongoDBConnectionPool` 单例模式
   - 配置合理的池大小（min: 10, max: 100）

4. **索引策略**
   ```python
   # 符号 + 时间复合索引
   db.market_data.create_index([("symbol", 1), ("timestamp", -1)])

   # TTL 索引（自动清理旧数据）
   db.market_data.create_index("timestamp", expireAfterSeconds=86400*365)
   ```

## 考虑的备选方案

### 方案 A：PostgreSQL with TimescaleDB
**描述**：使用 PostgreSQL + TimescaleDB 扩展处理时间序列数据

**优点**：
- 强大的 SQL 查询能力
- ACID 事务支持
- 团队熟悉 SQL
- 优秀的数据完整性保证

**缺点**：
- Schema 更改需要迁移
- TimescaleDB 学习曲线
- QuantBox 不原生支持 PostgreSQL
- 水平扩展相对困难

**为什么不选择**：
- QuantBox 集成是关键需求，原生支持 MongoDB
- 时间序列数据不需要严格的 ACID
- 灵活的 schema 更适合快速迭代

### 方案 B：InfluxDB
**描述**：专门的时间序列数据库

**优点**：
- 为时间序列优化
- 高效的压缩
- 强大的查询语言（InfluxQL）
- 内置降采样和保留策略

**缺点**：
- 不适合存储非时间序列数据（如配置、状态）
- 团队需要学习新的查询语言
- 社区和生态相对较小
- QuantBox 不支持

**为什么不选择**：
- 需要额外的数据库来存储非时间序列数据
- QuantBox 集成是核心需求
- 增加运维复杂度

### 方案 C：Redis + PostgreSQL 组合
**描述**：Redis 存储实时数据，PostgreSQL 存储历史数据

**优点**：
- Redis 提供极快的读写性能
- PostgreSQL 适合复杂查询
- 可以利用两者的优势

**缺点**：
- 需要维护两个数据库
- 数据同步复杂性
- 运维成本高
- QuantBox 不支持这种组合

**为什么不选择**：
- 架构复杂度显著增加
- 数据一致性难以保证
- 不符合 QuantBox 的要求

## 后果

### 正面影响

1. **高性能写入**
   - MongoDB 时间序列集合优化了写入性能
   - 实测：每秒可写入 10,000+ 条行情数据

2. **QuantBox 无缝集成**
   - QuantBox 原生支持 MongoDB
   - 性能提升 10-20x（根据 QuantBox 文档）
   - 简化数据管道

3. **灵活的 Schema**
   - 无需预定义严格的表结构
   - 可以快速添加新字段
   - 适合快速迭代开发

4. **水平扩展能力**
   - MongoDB 支持分片（Sharding）
   - 可以根据 symbol 或时间范围分片
   - 为未来增长做好准备

5. **异步支持**
   - Motor 提供优秀的 async/await 支持
   - 与 FastAPI、asyncio 生态完美集成

### 负面影响

1. **事务能力有限**
   - MongoDB 多文档事务性能不如 PostgreSQL
   - 对于交易系统的一致性要求需要额外注意
   - **缓解**：使用 MongoDB 4.2+ 的事务功能，关键操作使用事务

2. **查询语言学习曲线**
   - 团队需要学习 MongoDB 查询语法
   - 复杂的聚合查询需要时间掌握
   - **缓解**：提供详细的查询示例和文档

3. **数据完整性**
   - 没有外键约束
   - 需要在应用层保证数据一致性
   - **缓解**：使用 Pydantic 模型进行严格的数据验证

4. **内存使用**
   - MongoDB 工作集需要在内存中
   - 对服务器内存要求较高
   - **缓解**：
     - 使用 TTL 索引自动清理旧数据
     - 合理设置连接池大小
     - 监控内存使用

### 风险和缓解措施

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 数据一致性问题 | 中 | 高 | 使用事务，应用层验证，定期数据校验 |
| 查询性能不达预期 | 低 | 中 | 建立合理索引，使用查询分析器优化 |
| 内存不足导致性能下降 | 中 | 中 | TTL 索引清理，监控告警，扩容预案 |
| 团队学习曲线 | 中 | 低 | 培训文档，代码示例，结对编程 |

## 实施计划

1. ✅ **阶段 1：基础设施搭建**（已完成）
   - 安装 MongoDB 4.4+
   - 配置副本集（生产环境）
   - 创建数据库和用户权限

2. ✅ **阶段 2：连接管理**（已完成）
   - 实现 `MongoDBConnectionManager`
   - 实现 `MongoDBConnectionPool` 单例
   - 集成到 `DatabaseManager`

3. ✅ **阶段 3：数据模型和索引**（已完成）
   - 创建时间序列集合
   - 建立索引策略
   - 实现 TTL 自动清理

4. ✅ **阶段 4：QuantBox 集成**（已完成）
   - 集成 QuantBox 库
   - 实现数据桥接层
   - 性能测试和优化

5. **阶段 5：生产环境优化**（进行中）
   - 监控和告警设置
   - 备份策略实施
   - 性能基准测试

## 参考资料

- [MongoDB Time Series Collections](https://docs.mongodb.com/manual/core/timeseries-collections/)
- [Motor (Async MongoDB Driver)](https://motor.readthedocs.io/)
- [QuantBox MongoDB Integration Guide](https://quantbox.cn/docs/mongodb)
- [MongoDB Best Practices for Time Series Data](https://www.mongodb.com/blog/post/time-series-data-and-mongodb-part-1)
- [Team Discussion: PostgreSQL vs MongoDB](链接到内部讨论)

## 变更历史

- 2025-10-15: 初始决策文档（CherryQuant Team）
- 2025-10-18: 添加 QuantBox 集成细节（CherryQuant Team）
- 2025-10-20: 状态更改为 Accepted，添加实施进展（CherryQuant Team）
- 2025-11-18: 添加到 ADR 系统（CherryQuant Team）
