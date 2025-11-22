# CherryQuant 迁移指南

**版本**: v0.2.0
**日期**: 2024-11-22

本指南帮助用户从旧版本 API 迁移到 Quantbox 整合后的新版本。

---

## 目录

1. [概述](#概述)
2. [重要变更](#重要变更)
3. [新增模块](#新增模块)
4. [API 变更](#api-变更)
5. [迁移步骤](#迁移步骤)
6. [常见问题](#常见问题)

---

## 概述

CherryQuant v0.2.0 整合了 Quantbox 项目的核心设计模式和工具，带来了：

✅ **性能提升**: 批量数据写入提速 100 倍
✅ **新增工具**: 日期、交易所、合约代码解析工具
✅ **更好的追踪**: SaveResult 详细记录操作结果
✅ **智能策略**: 数据源本地优先、远程备用策略

**向后兼容性**: 所有新功能都是可选的，旧代码无需修改即可继续运行。

---

## 重要变更

### 1. ContractInfo 类重命名 ⚠️

**问题**: `ContractInfo` 在两个地方定义，用途不同导致冲突

**解决方案**: 合约解析工具中的类已重命名为 `ParsedContractInfo`

#### 变更详情

| 位置 | 旧名称 | 新名称 | 用途 |
|------|--------|--------|------|
| `cherryquant.utils.contract_utils` | `ContractInfo` | `ParsedContractInfo` | 合约代码解析 |
| `cherryquant.data.collectors.base_collector` | `ContractInfo` | `ContractInfo`（不变） | 合约完整规格 |

#### 迁移示例

**旧代码**:
```python
from cherryquant.utils.contract_utils import ContractInfo, parse_contract

info = parse_contract("SHFE.rb2501")  # 返回 ContractInfo
```

**新代码**（推荐）:
```python
from cherryquant.utils.contract_utils import ParsedContractInfo, parse_contract

info = parse_contract("SHFE.rb2501")  # 返回 ParsedContractInfo
```

**兼容性别名**（临时方案）:
```python
from cherryquant.utils.contract_utils import ContractInfo, parse_contract

# ContractInfo 现在是 ParsedContractInfo 的别名（已弃用）
info = parse_contract("SHFE.rb2501")  # 仍可工作，但应尽快迁移
```

⚠️ **建议**: 尽快更新代码使用 `ParsedContractInfo`，`ContractInfo` 别名将在未来版本移除。

### 2. Exchange 枚举扩展 ✅

**变更**: `base_collector.Exchange` 枚举新增了缺失的交易所

#### 新增交易所

```python
from cherryquant.data.collectors.base_collector import Exchange

# 新增期货交易所
Exchange.GFEX   # 广州期货交易所

# 新增股票交易所
Exchange.SHSE   # 上海证券交易所
Exchange.SZSE   # 深圳证券交易所
Exchange.BSE    # 北京证券交易所
```

**影响**: 无破坏性变更，仅新增枚举值，旧代码无需修改。

---

## 新增模块

### P0 - 基础工具层 (cherryquant.utils)

#### 1. 日期工具 (date_utils.py)

```python
from cherryquant.utils.date_utils import (
    get_trading_dates,
    is_trading_day,
    get_next_trading_day,
    get_previous_trading_day,
)

# 获取交易日列表
dates = get_trading_dates("20241101", "20241130", exchange="SHFE")

# 判断是否交易日
if is_trading_day("20241122", exchange="SHFE"):
    print("今天是交易日")

# 获取下一个交易日
next_day = get_next_trading_day("20241122", exchange="SHFE")
```

**优势**:
- 支持多交易所日历
- LRU 缓存提升性能
- 自动节假日处理

#### 2. 交易所工具 (exchange_utils.py)

```python
from cherryquant.utils.exchange_utils import (
    normalize_exchange,
    denormalize_exchange,
    is_futures_exchange,
    is_stock_exchange,
)

# 标准化交易所代码
exchange = normalize_exchange("SHF")  # "SHFE"
exchange = normalize_exchange("ZCE")  # "CZCE"

# 反标准化（转换为特定数据源格式）
ts_exchange = denormalize_exchange("SHFE", "tushare")  # "SHF"

# 判断交易所类型
is_futures_exchange("SHFE")  # True
is_stock_exchange("SHSE")    # True
```

**优势**:
- 统一不同数据源的交易所代码
- 快速类型判断

#### 3. 合约代码工具 (contract_utils.py)

```python
from cherryquant.utils.contract_utils import (
    parse_contract,
    format_contract,
    ParsedContractInfo,
)

# 解析合约代码
info = parse_contract("SHFE.rb2501")
print(info.exchange)    # "SHFE"
print(info.underlying)  # "rb"
print(info.year)        # 2025
print(info.month)       # 1

# 转换合约格式
# 标准格式 → Tushare 格式
tushare_code = format_contract("SHFE.rb2501", "tushare")  # "RB2501.SHF"

# Tushare 格式 → 标准格式
std_code = format_contract("RB2501.SHF", "standard")  # "SHFE.rb2501"

# 掘金格式 → VNPy 格式
vnpy_code = format_contract("SHFE.rb2501", "vnpy")  # "RB2501.SHFE"
```

**优势**:
- 自动识别多种数据源格式
- 智能处理郑商所 3/4 位年月格式
- 支持主力合约、连续合约等特殊类型

### P1 - 存储优化层 (cherryquant.data.storage)

#### 1. SaveResult 追踪器 (save_result.py)

```python
from cherryquant.data.storage.save_result import SaveResult

# 创建追踪器
result = SaveResult()

# 记录操作
result.inserted_count = 100
result.modified_count = 50

# 记录错误
result.add_error("VALIDATION_ERROR", "日期格式无效", {"date": "invalid"})

# 完成操作
result.complete()

# 查看结果
print(result)  # SaveResult(✓ total=150, inserted=100, modified=50, errors=1, duration=0.52s)
print(f"成功率: {result.success_rate:.1%}")  # 成功率: 99.3%

# 导出为字典
result_dict = result.to_dict()
```

**优势**:
- 详细的操作统计
- 错误分类和追踪
- 性能度量（持续时间）

#### 2. BulkWriter 批量写入 (bulk_writer.py)

```python
from cherryquant.data.storage.bulk_writer import BulkWriter
from cherryquant.data.storage.save_result import SaveResult

# 批量 upsert 数据
data = [
    {"symbol": "rb2501", "date": 20241122, "close": 3500.0},
    {"symbol": "rb2501", "date": 20241123, "close": 3510.0},
]

result = SaveResult()
await BulkWriter.bulk_upsert(
    collection=db.market_data,
    data=data,
    key_fields=["symbol", "date"],  # 唯一键
    result=result
)

# 创建索引
await BulkWriter.ensure_indexes(
    collection=db.market_data,
    index_specs=[
        {
            "keys": [("symbol", 1), ("date", 1)],
            "unique": True
        }
    ]
)
```

**优势**:
- **100 倍性能提升**（vs 循环 insert）
- Upsert 模式自动去重
- 后台索引创建不阻塞

#### 3. 数据源策略 (data_source_strategy.py)

```python
from cherryquant.data.collectors.data_source_strategy import (
    DataSourceStrategy,
    LocalDataSource,
    RemoteDataSource,
)

# 创建策略（本地优先）
strategy = DataSourceStrategy(
    local_source=LocalDataSource(),
    remote_source=RemoteDataSource(),
    prefer_local=True
)

# 自动选择数据源获取数据
data = await strategy.get_data(symbol="rb2501")

# 强制使用远程数据源
data = await strategy.get_data(use_local=False, symbol="rb2501")
```

**优势**:
- 本地优先，自动降级
- 透明切换，调用方无感知
- 配置灵活

---

## API 变更

### 无破坏性变更 ✅

本次更新**没有破坏性变更**，所有新功能都是增量添加：

1. ✅ 旧代码无需修改即可继续运行
2. ✅ 新模块是可选的，可渐进式采用
3. ✅ 提供了兼容性别名（ContractInfo）

### 推荐变更

虽然不是必需的，但建议逐步采用新 API：

| 场景 | 旧方案 | 新方案（推荐） |
|------|--------|----------------|
| 合约代码转换 | 手动字符串处理 | `contract_utils.format_contract()` |
| 交易日判断 | 手动查询数据库 | `date_utils.is_trading_day()` |
| 批量数据写入 | 循环 `insert()` | `BulkWriter.bulk_upsert()` |
| 数据源切换 | 硬编码条件判断 | `DataSourceStrategy` |
| 操作结果追踪 | 手动计数 | `SaveResult` |

---

## 迁移步骤

### 步骤 1: 更新依赖

确保已安装最新版本:

```bash
pip install cherryquant --upgrade
```

### 步骤 2: 渐进式迁移

**不要一次性重写所有代码**，建议分模块逐步迁移：

#### 优先级 1: 性能关键路径

如果有批量数据写入的场景，优先迁移到 `BulkWriter`:

```python
# 旧代码（慢）
for item in data:
    await collection.insert_one(item)

# 新代码（快 100 倍）
from cherryquant.data.storage.bulk_writer import BulkWriter

await BulkWriter.bulk_upsert(
    collection=collection,
    data=data,
    key_fields=["symbol", "date"]
)
```

#### 优先级 2: 合约代码处理

如果代码中有大量合约代码格式转换，迁移到 `contract_utils`:

```python
# 旧代码（手动处理）
if code.endswith(".SHF"):
    exchange = "SHFE"
    symbol = code.replace(".SHF", "")
# ... 更多 if-else ...

# 新代码（自动识别）
from cherryquant.utils.contract_utils import parse_contract

info = parse_contract(code)
exchange = info.exchange  # 自动识别
symbol = info.symbol
```

#### 优先级 3: 日期处理

如果有交易日判断逻辑，迁移到 `date_utils`:

```python
# 旧代码（查询数据库）
trading_days = await db.calendar.find({"exchange": "SHFE"})
is_trading = date in trading_days

# 新代码（内置缓存）
from cherryquant.utils.date_utils import is_trading_day

is_trading = is_trading_day(date, exchange="SHFE")  # 更快
```

### 步骤 3: 更新 ContractInfo 引用

搜索所有 `from cherryquant.utils.contract_utils import ContractInfo` 并更新:

```bash
# 搜索旧引用
grep -r "from cherryquant.utils.contract_utils import ContractInfo" .

# 批量替换（使用 sed 或手动）
# ContractInfo → ParsedContractInfo
```

### 步骤 4: 测试

迁移后运行完整测试套件确保功能正常:

```bash
pytest tests/
```

---

## 常见问题

### Q1: 我必须立即迁移吗？

**A**: 不需要。所有旧 API 仍然有效，可以在方便时渐进式迁移。

### Q2: ContractInfo 别名会一直存在吗？

**A**: 不会。别名仅作为过渡期方案，计划在 v0.3.0 移除。建议尽早迁移到 `ParsedContractInfo`。

### Q3: 新工具会增加依赖吗？

**A**: 不会。所有新工具都使用 Python 标准库或已有依赖（如 motor、pymongo）。

### Q4: 如何知道 BulkWriter 是否真的更快？

**A**: 可以使用 `SaveResult` 的 `duration` 属性对比:

```python
import time

# 旧方案
start = time.time()
for item in data:
    await collection.insert_one(item)
old_duration = time.time() - start

# 新方案
result = SaveResult()
await BulkWriter.bulk_upsert(collection, data, ["symbol", "date"], result)
result.complete()
new_duration = result.duration.total_seconds()

print(f"性能提升: {old_duration / new_duration:.1f}x")
```

### Q5: 数据源策略如何配置？

**A**: 通过 `prefer_local` 参数控制:

```python
# 本地优先（默认）
strategy = DataSourceStrategy(local, remote, prefer_local=True)

# 远程优先
strategy = DataSourceStrategy(local, remote, prefer_local=False)
```

### Q6: 如果我只用期货，需要新增的股票交易所枚举吗？

**A**: 不需要。新增的 `Exchange.SHSE`、`Exchange.SZSE`、`Exchange.BSE` 不会影响现有期货代码。

### Q7: 文档在哪里？

**A**: 详细文档位于:

- **P0 工具**: `docs/quantbox_integration_p0.md`
- **P1 存储优化**: `docs/quantbox_integration_p1.md`
- **架构反思**: `docs/ARCHITECTURE_REFLECTION_QUANTBOX.md`
- **课程文档**: `docs/course/02_Data_Pipeline.md`（即将更新）

---

## 获取帮助

如果在迁移过程中遇到问题：

1. 📖 查看文档: `docs/` 目录
2. 💬 提交 Issue: [GitHub Issues](https://github.com/your-repo/cherryquant/issues)
3. 📧 联系作者

---

**最后更新**: 2024-11-22
**适用版本**: CherryQuant v0.2.0+
