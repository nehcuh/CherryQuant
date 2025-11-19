# 02 数据获取与处理

## 概述

本目录包含数据管道相关的示例，演示如何从不同数据源获取期货市场数据，以及如何进行数据处理和存储。

## 学习目标

- 📡 理解适配器模式（Adapter Pattern）
- 🔌 掌握多数据源集成方法
- 💾 学习数据持久化策略
- 🔄 了解数据同步机制

## 示例列表

### `fetch_historical_data.py` (即将添加)
**难度**: ⭐⭐ 初级

**描述**: 演示如何获取历史 K 线数据。

**学习要点**:
- Tushare 数据源使用
- 数据适配器模式
- 异步数据获取
- 数据验证和清洗

**运行方式**:
```bash
uv run python examples/02_data/fetch_historical_data.py
```

---

### `realtime_data_stream.py` (即将添加)
**难度**: ⭐⭐ 初级

**描述**: 演示实时行情数据流获取。

**学习要点**:
- VNPy 实时数据接口
- 数据流处理
- 回调函数设计
- 数据缓存策略

---

### `multi_source_demo.py` (即将添加)
**难度**: ⭐⭐⭐ 中级

**描述**: 演示多数据源切换和容错机制。

**学习要点**:
- 多数据源适配
- 降级策略
- 数据源健康检查
- 故障切换

---

### `data_storage.py` (即将添加)
**难度**: ⭐⭐ 初级

**描述**: 演示数据存储到 MongoDB。

**学习要点**:
- MongoDB 时间序列集合
- 批量插入优化
- 索引设计
- 数据去重

---

## 架构说明

### 数据适配器层次结构

```
DataAdapter (接口)
    ├── TushareAdapter (Tushare 数据源)
    ├── VNPyAdapter (VNPy 实时数据)
    └── QuantBoxAdapter (QuantBox 高性能数据)
```

### 数据流向

```
数据源 → 适配器 → 数据管理器 → MongoDB/Redis → AI 引擎
```

## 前置要求

### 环境变量配置

在 `.env` 文件中配置以下内容：

```bash
# Tushare Token (用于历史数据)
TUSHARE_TOKEN=your_token_here

# MongoDB 配置
MONGO_HOST=localhost
MONGO_PORT=27017
MONGO_DB_NAME=cherryquant

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 数据源准备

1. **Tushare Token 获取**:
   - 访问 https://tushare.pro
   - 注册并获取 API Token
   - 将 Token 配置到 `.env` 文件

2. **启动数据库服务**:
   ```bash
   # 启动 MongoDB
   docker-compose up -d mongodb

   # 启动 Redis
   docker-compose up -d redis
   ```

## 相关课程模块

- **Module 2**: 数据管道设计
- **Lab 02**: 追踪数据流

## 常见问题

**Q: Tushare 数据获取失败?**

A: 检查以下几点：
- Token 是否正确配置
- 积分是否足够（免费用户有限制）
- 网络连接是否正常

**Q: MongoDB 连接失败?**

A: 确保 MongoDB 服务已启动：
```bash
docker-compose ps mongodb
```

**Q: 数据获取速度慢?**

A: 考虑以下优化：
- 使用批量获取
- 启用 Redis 缓存
- 调整数据获取频率

**Q: 如何验证数据质量?**

A: 示例代码包含数据验证逻辑，会检查：
- 数据完整性（必填字段）
- 数据合理性（价格、成交量范围）
- 数据时间序列连续性

## 数据规范

### K 线数据格式

```python
{
    "symbol": "rb2501",          # 合约代码
    "datetime": "2024-01-01 09:00:00",  # 时间戳
    "open": 3500.0,              # 开盘价
    "high": 3520.0,              # 最高价
    "low": 3490.0,               # 最低价
    "close": 3510.0,             # 收盘价
    "volume": 12345,             # 成交量
    "open_interest": 54321       # 持仓量
}
```

## 下一步

完成本目录示例后，继续学习：
- **03_ai**: AI 决策引擎
- **04_trading**: 交易执行
- **complete_system**: 完整系统集成

---

💡 **学习提示**: 数据质量是量化交易的基础，务必理解每个数据字段的含义和数据验证的重要性。
