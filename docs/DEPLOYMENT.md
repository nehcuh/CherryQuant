# CherryQuant 生产部署指南

**版本**: v0.5-beta
**更新日期**: 2024年
**状态**: Production Ready ✅

---

## 📋 目录

- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [详细配置](#详细配置)
- [数据库设置](#数据库设置)
- [运行和监控](#运行和监控)
- [性能调优](#性能调优)
- [故障排查](#故障排查)
- [安全建议](#安全建议)

---

## 🔧 环境要求

### 系统要求

| 组件 | 最低要求 | 推荐配置 |
|------|---------|---------|
| **OS** | Linux/macOS | Ubuntu 20.04+ / CentOS 8+ |
| **Python** | 3.7+ | 3.10+ |
| **MongoDB** | 4.4+ | 5.0+ (支持时间序列) |
| **Redis** (可选) | 6.0+ | 7.0+ |
| **内存** | 2GB | 8GB+ |
| **存储** | 10GB | 100GB+ SSD |
| **CPU** | 2核 | 4核+ |

### Python依赖

```bash
# 核心依赖
python >= 3.7
motor >= 3.0  # MongoDB异步驱动
pymongo >= 4.0
redis >= 4.0  # 可选：用于L2缓存
aioredis >= 2.0  # 可选：异步Redis

# 数据采集依赖
tushare >= 1.2  # Tushare数据源
pandas >= 1.3
```

---

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-org/CherryQuant.git
cd CherryQuant
```

### 2. 创建虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -e .

# 或使用requirements.txt
pip install -r requirements.txt
```

### 4. 配置环境变量

创建 `.env` 文件：

```bash
cp .env.example .env
```

编辑 `.env`：

```ini
# MongoDB 配置
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=cherryquant_prod

# Redis 配置 (可选)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# Tushare API
TUSHARE_TOKEN=your_token_here

# 应用配置
APP_ENV=production
LOG_LEVEL=INFO
```

### 5. 启动MongoDB

```bash
# Docker方式（推荐）
docker run -d \
  --name mongodb \
  -p 27017:27017 \
  -v mongodb_data:/data/db \
  -e MONGO_INITDB_ROOT_USERNAME=admin \
  -e MONGO_INITDB_ROOT_PASSWORD=your_password \
  mongo:5.0

# 或使用docker-compose
docker-compose up -d mongodb
```

### 6. 初始化数据库

```python
from cherryquant.data import DataPipeline
import asyncio

async def init_database():
    pipeline = DataPipeline()
    await pipeline.initialize()
    print("✅ 数据库初始化完成")

asyncio.run(init_database())
```

### 7. 验证安装

```bash
# 运行测试
pytest tests/integration/ -v

# 检查数据管道
python -c "
from cherryquant.data import DataPipeline
print('✅ 导入成功')
"
```

---

## ⚙️ 详细配置

### 环境变量说明

#### MongoDB 配置

```ini
# 基础连接
MONGODB_URI=mongodb://user:pass@host:port/?authSource=admin
MONGODB_DATABASE=cherryquant_prod

# 连接池配置
MONGODB_MAX_POOL_SIZE=100  # 最大连接数
MONGODB_MIN_POOL_SIZE=10   # 最小连接数
MONGODB_TIMEOUT=30000      # 连接超时（毫秒）
```

#### Redis 配置（L2缓存）

```ini
# 基础配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
REDIS_DB=0

# 缓存配置
CACHE_L1_SIZE=1000          # L1内存缓存大小
CACHE_L1_TTL=300            # L1缓存过期时间（秒）
CACHE_L2_TTL=3600           # L2缓存过期时间（秒）
```

#### Tushare API配置

```ini
# API认证
TUSHARE_TOKEN=your_token_here

# 速率限制
TUSHARE_RATE_LIMIT=100      # 每分钟最大调用次数
```

#### 重试和容错配置

```ini
# 重试配置
RETRY_MAX_ATTEMPTS=3        # 最大重试次数
RETRY_BASE_DELAY=1.0        # 基础延迟（秒）
RETRY_MAX_DELAY=60.0        # 最大延迟（秒）

# 断路器配置
CIRCUIT_FAILURE_THRESHOLD=5      # 失败阈值
CIRCUIT_SUCCESS_THRESHOLD=2      # 成功阈值
CIRCUIT_TIMEOUT=60.0             # 断路器超时（秒）
```

---

## 💾 数据库设置

### MongoDB 时间序列集合

CherryQuant 使用 MongoDB 时间序列集合存储市场数据，性能优异。

#### 创建时间序列集合

```javascript
// 在MongoDB shell中执行
use cherryquant_prod;

// 创建1分钟K线集合
db.createCollection("market_data_1m", {
  timeseries: {
    timeField: "datetime",
    metaField: "metadata",
    granularity: "minutes"
  }
});

// 创建日线集合
db.createCollection("market_data_1d", {
  timeseries: {
    timeField: "datetime",
    metaField: "metadata",
    granularity: "hours"
  }
});

// 创建索引
db.market_data_1d.createIndex(
  { "metadata.symbol": 1, "datetime": 1 },
  { name: "symbol_time_idx" }
);
```

#### 自动初始化（推荐）

使用Python自动创建：

```python
from cherryquant.data.storage.timeseries_repository import TimeSeriesRepository
from cherryquant.data.collectors.base_collector import TimeFrame
import asyncio

async def setup_database():
    repo = TimeSeriesRepository(connection_manager)

    # 为所有时间周期创建索引
    for timeframe in TimeFrame:
        await repo.ensure_indexes(timeframe)
        print(f"✅ 索引创建完成: {timeframe.value}")

asyncio.run(setup_database())
```

### MongoDB 性能优化

#### 1. 索引优化

```javascript
// 复合索引（查询优化）
db.market_data_1d.createIndex(
  {
    "metadata.exchange": 1,
    "metadata.symbol": 1,
    "datetime": 1
  },
  { background: true }
);

// 查看索引使用情况
db.market_data_1d.aggregate([
  { $indexStats: {} }
]);
```

#### 2. 连接池配置

```python
from cherryquant.adapters.data_storage.mongodb_manager import MongoDBConnectionManager

manager = MongoDBConnectionManager(
    uri="mongodb://localhost:27017",
    database="cherryquant_prod",
    max_pool_size=100,  # 根据并发量调整
    min_pool_size=10,
    max_idle_time_ms=60000,
)
```

#### 3. 写入性能优化

```python
# 使用批量插入
from cherryquant.data.storage.timeseries_repository import TimeSeriesRepository

repo = TimeSeriesRepository(manager)

# 批量保存（性能提升10-100倍）
await repo.save_batch(
    market_data_list,
    ordered=False  # 允许部分失败，继续插入
)
```

---

## 🔄 运行和监控

### 基础使用示例

#### 1. 数据采集

```python
from cherryquant.data import DataPipeline, TushareCollector, Exchange, TimeFrame
from datetime import datetime, timedelta
import asyncio

async def collect_data():
    # 初始化管道
    pipeline = DataPipeline()
    await pipeline.initialize()

    # 采集数据
    result = await pipeline.collect_and_save(
        symbols=["rb2501", "hc2501"],
        exchange=Exchange.SHFE,
        start_date=datetime.now() - timedelta(days=30),
        end_date=datetime.now(),
        timeframe=TimeFrame.DAY_1,
    )

    print(f"✅ 采集完成: {result['total_saved']} 条数据")

asyncio.run(collect_data())
```

#### 2. 数据查询

```python
from cherryquant.data import QueryBuilder
import asyncio

async def query_data():
    builder = QueryBuilder(timeseries_repo)

    # 构建查询
    data = await (builder
        .symbol("rb2501")
        .exchange(Exchange.SHFE)
        .date_range(
            datetime(2024, 1, 1),
            datetime(2024, 1, 31)
        )
        .timeframe(TimeFrame.DAY_1)
        .execute()
    )

    print(f"📊 查询结果: {len(data)} 条")
    return data

asyncio.run(query_data())
```

### 定时任务设置

#### 使用 cron 定时采集

创建 `scripts/daily_collect.py`:

```python
#!/usr/bin/env python
"""每日数据采集脚本"""
import asyncio
from datetime import datetime, timedelta
from cherryquant.data import DataPipeline, Exchange, TimeFrame

async def main():
    pipeline = DataPipeline()
    await pipeline.initialize()

    # 采集昨日数据
    yesterday = datetime.now() - timedelta(days=1)

    result = await pipeline.collect_and_save(
        symbols=["rb", "hc", "cu"],  # 主力合约
        exchange=Exchange.SHFE,
        start_date=yesterday,
        end_date=yesterday,
        timeframe=TimeFrame.DAY_1,
    )

    print(f"✅ 日线采集完成: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

配置 crontab:

```bash
# 编辑crontab
crontab -e

# 每天16:00执行数据采集
0 16 * * 1-5 cd /path/to/CherryQuant && /path/to/.venv/bin/python scripts/daily_collect.py >> logs/collect.log 2>&1
```

### 日志配置

创建 `logging_config.py`:

```python
import logging.config

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'detailed',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/cherryquant.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'detailed',
            'level': 'DEBUG',
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'file'],
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
```

### 监控指标

#### 关键指标

1. **数据采集指标**
   - 采集成功率
   - 采集延迟
   - API调用次数
   - 重试次数

2. **数据库指标**
   - 写入QPS
   - 查询延迟
   - 连接池使用率
   - 慢查询日志

3. **缓存指标**
   - L1命中率
   - L2命中率
   - 缓存大小
   - 淘汰次数

#### 监控脚本示例

```python
from cherryquant.data import DataPipeline
import asyncio

async def monitor_stats():
    pipeline = DataPipeline()

    # 获取缓存统计
    cache_stats = pipeline.cache_strategy.stats
    print(f"L1 命中率: {cache_stats['l1_hits'] / (cache_stats['l1_hits'] + cache_stats['l1_misses']):.2%}")

    # 获取数据库统计
    # (需要从MongoDB获取)

asyncio.run(monitor_stats())
```

---

## ⚡ 性能调优

### 1. 批量操作优化

```python
# ❌ 不推荐：逐条插入
for data in data_list:
    await repo.save(data)

# ✅ 推荐：批量插入
await repo.save_batch(data_list)  # 性能提升10-100倍
```

### 2. 缓存策略

```python
from cherryquant.data.storage.cache_strategy import CacheStrategy

# 配置三级缓存
cache = CacheStrategy(
    enable_l1=True,
    enable_l2=True,
    l1_max_size=1000,     # 根据内存调整
    l1_ttl=300,           # 5分钟
    l2_ttl=3600,          # 1小时
    redis_client=redis_client,
)
```

### 3. 连接复用

```python
# ✅ 使用连接池，自动管理
from cherryquant.adapters.data_storage.mongodb_manager import MongoDBConnectionManager

manager = MongoDBConnectionManager(
    uri="mongodb://localhost:27017",
    database="cherryquant_prod",
    max_pool_size=100,
)

# 复用同一个manager实例
repo1 = TimeSeriesRepository(manager)
repo2 = MetadataRepository(manager)
```

### 4. 并发控制

```python
import asyncio
from cherryquant.data import BatchQueryExecutor

# 批量并发查询
executor = BatchQueryExecutor(repo, max_concurrent=10)

requests = [
    {"symbol": f"rb250{i}", "exchange": Exchange.SHFE, ...}
    for i in range(12)
]

results = await executor.execute_batch(requests)
```

---

## 🐛 故障排查

### 常见问题

#### 1. MongoDB 连接失败

**错误**: `pymongo.errors.ServerSelectionTimeoutError`

**解决方案**:
```bash
# 检查MongoDB是否运行
docker ps | grep mongodb

# 检查连接字符串
ping <mongodb_host>

# 检查认证
mongo --host <host> --username <user> --password <pass>

# 检查防火墙
telnet <host> 27017
```

#### 2. Tushare API 限流

**错误**: `抱歉，您每分钟最多访问该接口100次`

**解决方案**:
```python
# 调整速率限制
collector = TushareCollector(
    token="your_token",
    call_limit_per_minute=50  # 降低调用频率
)

# 或使用重试机制（已内置）
# 系统会自动重试
```

#### 3. 内存不足

**症状**: 程序崩溃或OOM错误

**解决方案**:
```python
# 减小缓存大小
cache = CacheStrategy(
    l1_max_size=500,  # 从1000降至500
)

# 分批处理
BATCH_SIZE = 1000
for i in range(0, len(data_list), BATCH_SIZE):
    batch = data_list[i:i+BATCH_SIZE]
    await repo.save_batch(batch)
```

#### 4. 查询慢

**诊断**:
```javascript
// MongoDB慢查询日志
db.setProfilingLevel(1, { slowms: 100 })

// 查看慢查询
db.system.profile.find().sort({ts: -1}).limit(5)
```

**优化**:
```javascript
// 创建适当的索引
db.market_data_1d.createIndex(
  { "metadata.symbol": 1, "datetime": 1 }
)

// 使用查询计划分析
db.market_data_1d.find({...}).explain("executionStats")
```

### 调试技巧

#### 启用详细日志

```python
import logging

logging.basicConfig(level=logging.DEBUG)

# 或针对特定模块
logging.getLogger("cherryquant.data").setLevel(logging.DEBUG)
```

#### 性能分析

```python
import cProfile
import pstats

async def main():
    # your code here
    pass

# 性能分析
cProfile.run('asyncio.run(main())', 'stats')

# 查看统计
p = pstats.Stats('stats')
p.sort_stats('cumulative').print_stats(20)
```

---

## 🔐 安全建议

### 1. 敏感信息管理

```bash
# ❌ 不要提交到版本控制
.env
*.env.local
secrets/

# ✅ 使用环境变量
export TUSHARE_TOKEN="xxx"
export MONGODB_PASSWORD="xxx"
```

### 2. 数据库访问控制

```javascript
// 创建只读用户
use cherryquant_prod;

db.createUser({
  user: "readonly",
  pwd: "secure_password",
  roles: [{ role: "read", db: "cherryquant_prod" }]
})

// 创建读写用户
db.createUser({
  user: "readwrite",
  pwd: "secure_password",
  roles: [{ role: "readWrite", db: "cherryquant_prod" }]
})
```

### 3. 网络隔离

```yaml
# docker-compose.yml
services:
  mongodb:
    networks:
      - backend
    # 不暴露到公网
    ports:
      - "127.0.0.1:27017:27017"

networks:
  backend:
    driver: bridge
```

### 4. 备份策略

```bash
# 每日备份
0 2 * * * mongodump --uri="mongodb://user:pass@localhost:27017/cherryquant_prod" --out=/backup/$(date +\%Y\%m\%d)

# 保留最近7天的备份
find /backup -type d -mtime +7 -exec rm -rf {} \;
```

---

## 📚 其他资源

- [API 文档](API_REFERENCE.md)
- [架构设计](ARCHITECTURE.md)
- [生产就绪状态](PRODUCTION_READY_STATUS.md)
- [FAQ](FAQ.md)

---

## 🆘 获取帮助

遇到问题？

1. 查看 [FAQ](FAQ.md)
2. 搜索 [Issues](https://github.com/your-org/CherryQuant/issues)
3. 提交新 [Issue](https://github.com/your-org/CherryQuant/issues/new)

---

**祝部署顺利！** 🎉
