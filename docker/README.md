# CherryQuant Docker 数据库配置

本文档介绍如何在 macOS 上使用 OrbStack 运行 CherryQuant 数据库服务。

## 🐳 系统架构

CherryQuant 使用多数据库架构，每个数据库都有特定用途：

- **PostgreSQL + TimescaleDB**: 主要时序数据库，存储市场数据、技术指标、交易记录
- **Redis**: 内存缓存，存储实时数据和AI决策缓存
- **InfluxDB**: 备选时序数据库，用于高频数据存储
- **Grafana**: 数据可视化面板
- **pgAdmin**: PostgreSQL 管理界面

## 🚀 快速启动

### 1. 启动所有服务

```bash
# 进入项目根目录
cd /Users/huchen/Projects/CherryQuant

# 启动所有数据库服务
docker-compose -f docker/docker-compose.yml up -d

# 查看服务状态
docker-compose -f docker/docker-compose.yml ps
```

### 2. 服务访问地址

| 服务 | 地址 | 用户名 | 密码 |
|------|------|--------|------|
| PostgreSQL (主库) | localhost:5432 | cherryquant | cherryquant123 |
| Redis | localhost:6379 | - | - |
| InfluxDB | localhost:8086 | admin | admin123456 |
| Grafana | localhost:3000 | admin | cherryquant123 |
| pgAdmin | localhost:5050 | admin@cherryquant.com | cherryquant123 |

### 3. 数据库连接配置

更新 `.env` 文件：

```env
# PostgreSQL 数据库配置
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=cherryquant
POSTGRES_USER=cherryquant
POSTGRES_PASSWORD=cherryquant123

# Redis 缓存配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# InfluxDB 配置（可选）
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=cherryquant-super-secret-token
INFLUXDB_ORG=cherryquant
INFLUXDB_BUCKET=market_data
```

## 📊 数据库表结构

### 核心数据表

1. **futures_contracts** - 期货合约基础信息
2. **market_data** - 市场行情数据（时序表）
3. **technical_indicators** - 技术指标数据（时序表）
4. **ai_decisions** - AI决策记录
5. **trades** - 交易记录
6. **portfolio** - 投资组合状态
7. **market_statistics** - 市场统计信息

### 时序数据策略

- **高频数据** (1分钟): 保留3天
- **中频数据** (5分钟): 保留30天
- **低频数据** (1小时): 保留1年
- **日线数据**: 永久保留

## 🔧 管理命令

### 查看日志
```bash
# 查看所有服务日志
docker-compose -f docker/docker-compose.yml logs -f

# 查看特定服务日志
docker-compose -f docker/docker-compose.yml logs -f postgresql
docker-compose -f docker/docker-compose.yml logs -f redis
```

### 数据库操作
```bash
# 连接到 PostgreSQL
docker-compose -f docker/docker-compose.yml exec postgresql psql -U cherryquant -d cherryquant

# 连接到 Redis
docker-compose -f docker/docker-compose.yml exec redis redis-cli

# 备份数据库
docker-compose -f docker/docker-compose.yml exec postgresql pg_dump -U cherryquant cherryquant > backup.sql

# 恢复数据库
docker-compose -f docker/docker-compose.yml exec -T postgresql psql -U cherryquant cherryquant < backup.sql
```

### 停止和清理
```bash
# 停止所有服务
docker-compose -f docker/docker-compose.yml down

# 停止并删除数据卷（⚠️ 会删除所有数据）
docker-compose -f docker/docker-compose.yml down -v
```

## 📈 Grafana 配置

### 访问 Grafana
1. 打开浏览器访问 http://localhost:3000
2. 用户名: `admin`，密码: `cherryquant123`
3. 添加 PostgreSQL 数据源

### 数据源配置
```json
{
  "host": "postgresql",
  "port": 5432,
  "database": "cherryquant",
  "user": "cherryquant",
  "password": "cherryquant123"
}
```

## 🔍 监控指标

### 数据库性能监控
- PostgreSQL: TimescaleDB 时序性能
- Redis: 内存使用和缓存命中率
- InfluxDB: 高频数据写入性能

### 业务指标监控
- 实时行情更新频率
- AI决策执行状态
- 交易盈亏统计
- 系统风险指标

## 🛠️ 开发和调试

### 测试数据库连接
```python
import psycopg2
import redis

# 测试 PostgreSQL 连接
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="cherryquant",
    user="cherryquant",
    password="cherryquant123"
)

# 测试 Redis 连接
r = redis.Redis(host='localhost', port=6379, db=0)
r.ping()
```

### 查看表结构
```sql
-- 查看所有表
\dt

-- 查看表结构
\d market_data

-- 查看时序表信息
SELECT * FROM timescaledb_information.hypertables;
```

## 📝 数据迁移

### 从 AKShare 导入数据
```python
# 使用 Python 脚本导入历史数据
python scripts/import_historical_data.py --symbol rb --exchange SHFE --days 365
```

### 数据导出
```bash
# 导出特定时间范围的数据
docker-compose exec postgresql psql -U cherryquant -d cherryquant -c "
COPY (
    SELECT * FROM market_data
    WHERE time >= '2024-01-01' AND time < '2024-02-01'
) TO stdout WITH CSV HEADER;
" > january_2024_data.csv
```

## ⚡ 性能优化

### PostgreSQL 优化
- 时序数据自动分区
- 连续聚合视图
- 数据压缩策略
- 索引优化

### Redis 优化
- LRU 淘汰策略
- 内存限制 512MB
- 持久化配置

### 查询优化
- 使用 TimescaleDB 的时序函数
- 合理的数据保留策略
- 连续聚合预计算

## 🔒 安全配置

### 网络安全
- 使用 Docker 网络隔离
- 仅暴露必要端口
- 防火墙配置

### 数据安全
- 定期数据备份
- 密码管理
- 访问权限控制

## 🚨 故障排除

### 常见问题

1. **端口冲突**
   ```bash
   # 检查端口占用
   lsof -i :5432
   # 修改 docker-compose.yml 中的端口映射
   ```

2. **内存不足**
   ```bash
   # 增加 Docker 内存限制
   # 在 OrbStack 设置中调整内存分配
   ```

3. **数据连接失败**
   ```bash
   # 检查网络连接
   docker network ls
   docker network inspect cherryquant_cherryquant-network
   ```

### 日志分析
```bash
# 查看错误日志
docker-compose -f docker/docker-compose.yml logs postgresql | grep ERROR

# 查看性能日志
docker-compose -f docker/docker-compose.yml exec postgresql tail -f /var/log/postgresql/postgresql.log
```

## 📞 技术支持

如有问题，请检查：
1. Docker 服务状态
2. 网络连接
3. 日志文件
4. 配置文件

---

🍒 CherryQuant Database Infrastructure
Built with TimescaleDB + Redis + InfluxDB