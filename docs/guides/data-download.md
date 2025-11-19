# CherryQuant 历史数据下载指南

## 快速开始

### 方式1：交互式下载（推荐）

最简单的方式，启动系统时会自动提示：

```bash
uv run run_cherryquant_complete.py
```

系统会检测到数据库为空，询问是否下载数据，选择 `1` 即可。

### 方式2：命令行下载

**只下载日线数据（推荐，快速）:**

```bash
uv run run_cherryquant_complete.py --download-data
```

**下载日线和小时线数据:**

```bash
uv run run_cherryquant_complete.py --download-data --timeframes 1d 1h
```

**指定要下载的品种:**

```bash
uv run run_cherryquant_complete.py --download-data --symbols rb cu i SR
```

**查看所有选项:**

```bash
uv run run_cherryquant_complete.py --help
```

## 时间周期说明

| 周期 | 说明 | API限流 | 下载速度 | 数据用途 |
|------|------|---------|----------|---------|
| `1d` | 日线 | 无限制 | 快速 | ✅ 推荐，适合大部分策略 |
| `1h` | 小时线 | 每分钟2次 | 很慢 | 需要高级权限 |
| `30m` | 30分钟线 | 每分钟2次 | 很慢 | 需要2000+积分 |
| `10m` | 10分钟线 | 每分钟2次 | 很慢 | 需要2000+积分 |
| `5m` | 5分钟线 | 每分钟2次 | 很慢 | 需要2000+积分 |
| `1m` | 1分钟线 | 每分钟2次 | 极慢 | 需要2000+积分 |

## Tushare API 限流问题

### 限流说明

Tushare 对分钟线数据（`ft_mins` API）有严格限制：

- **普通用户**: 每分钟最多 2 次请求
- **2000+积分用户**: 每分钟最多 200 次请求

由于需要逐个合约下载，普通用户下载分钟线数据会**非常慢**：
- 1个品种有12个合约
- 每个合约下载需要多次请求（数据分页）
- **预计每个品种需要 10-20 分钟**

### 解决方案

**方案1：只下载日线数据（推荐）**

```bash
# 日线数据无限流限制，几分钟内完成
uv run run_cherryquant_complete.py --download-data
```

日线数据足够大部分交易策略使用。

**方案2：升级 Tushare 积分**

- 积分达到 2000+，限流提升到 200次/分钟
- 详见：https://tushare.pro/document/1?doc_id=108

**方案3：等待或分批下载**

脚本已实现智能重试和限流处理：
- 遇到限流自动等待60秒后重试
- 每次请求间隔35秒
- 最多重试3次

可以让程序慢慢下载，或者分批下载不同品种。

## 命令行参数完整列表

```bash
uv run run_cherryquant_complete.py [OPTIONS]

选项:
  --download-data           只下载历史数据然后退出
  --skip-data-check         跳过启动时的数据检查
  --trading-only            只启动交易系统（不启动Web服务）
  --timeframes 1d 1h ...    指定时间周期（配合 --download-data）
  --symbols rb cu i ...     指定品种（配合 --download-data）
  -h, --help                显示帮助信息
```

## 使用示例

### 示例1：快速下载主流品种日线数据

```bash
uv run run_cherryquant_complete.py --download-data
```

默认下载：
- 上期所: rb, hc, cu, al
- 大商所: i, j, jm, m
- 郑商所: SR, CF, TA
- 中金所: IF, IC

### 示例2：只下载特定品种

```bash
# 只下载螺纹钢和铁矿石
uv run run_cherryquant_complete.py --download-data --symbols rb i
```

### 示例3：下载多时间周期（慎用）

```bash
# 下载日线和小时线（会很慢！）
uv run run_cherryquant_complete.py --download-data --timeframes 1d 1h
```

### 示例4：跳过数据检查启动

```bash
# 数据库有数据时，跳过检查直接启动
uv run run_cherryquant_complete.py --skip-data-check
```

## 数据格式

下载的数据保存在 PostgreSQL 的 `market_data` 表中，格式符合 VNPy 规范：

| 字段 | 格式示例 | 说明 |
|------|---------|------|
| symbol | `rb2501` | 上期所/大商所：小写+4位 |
|  | `SR501` | **郑商所：大写+3位** |
|  | `IF2512` | 中金所：大写+4位 |
| exchange | `SHFE`, `DCE`, `CZCE`, `CFFEX` | VNPy标准交易所代码 |
| timeframe | `1d`, `1h`, `5m`, etc | 时间周期 |

详见：[合约代码标准化文档](./SYMBOL_STANDARDIZATION.md)

## 手动下载脚本

如果需要更灵活的控制，可以直接运行下载脚本：

```bash
# 交互式下载
uv run python scripts/init_historical_data.py

# 自动模式（快速测试）
uv run python scripts/init_historical_data.py --auto
```

## 常见问题

### Q: 下载很慢怎么办？

A: 如果选择了分钟线数据（1h及以下），由于API限流，下载会非常慢。建议：
1. 只下载日线数据（推荐）
2. 或者升级Tushare积分到2000+

### Q: 下载失败怎么办？

A: 脚本已实现自动重试。如果多次失败：
1. 检查 Tushare token 是否正确配置在 `.env` 文件中
2. 检查网络连接
3. 查看是否触发了API限流

### Q: 如何更新数据？

A: 重新运行下载命令即可，脚本会自动去重（`ON CONFLICT DO NOTHING`）

### Q: 数据保存在哪里？

A: PostgreSQL 数据库的 `market_data` 表，可以使用以下命令查看：

```bash
export PGPASSWORD=cherryquant123
psql -h localhost -U postgres -d cherryquant -c "
  SELECT symbol, exchange, timeframe, COUNT(*) as count
  FROM market_data
  GROUP BY symbol, exchange, timeframe
  LIMIT 10;
"
```

## 推荐工作流

1. **首次使用**：只下载日线数据
   ```bash
   uv run run_cherryquant_complete.py --download-data
   ```

2. **测试策略**：使用日线数据回测

3. **如需分钟数据**：
   - 选择性下载特定品种
   - 或者使用实时数据（VNPy接入）

4. **日常使用**：跳过数据检查快速启动
   ```bash
   uv run run_cherryquant_complete.py --skip-data-check
   ```
