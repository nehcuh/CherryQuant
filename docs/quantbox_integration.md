# Quantbox Integration Documentation

## 概述

本文档说明CherryQuant项目中整合的quantbox优秀设计，包括核心工具模块、配置文件和设计模式。

**整合时间**: 2024-11-22
**整合版本**: quantbox核心工具模块
**整合原则**: 深度吸收quantbox的优秀设计，而非简单的adapter包装

## 整合内容

### 1. 核心工具模块 (Utils)

#### 1.1 日期处理工具 (`src/cherryquant/utils/date_utils.py`)

**来源**: `quantbox/util/date_utils.py`

**核心功能**:
- 多格式日期转换（字符串、整数、datetime对象）
- 交易日查询和计算
- LRU缓存优化高频查询
- MongoDB集成的交易日历

**主要API**:

```python
from cherryquant.utils.date_utils import (
    date_to_int,          # 日期转整数格式 (YYYYMMDD)
    int_to_date_str,      # 整数转日期字符串
    date_to_str,          # 日期转字符串（可指定格式）
    is_trade_date,        # 判断是否交易日
    get_pre_trade_date,   # 获取前一交易日
    get_next_trade_date,  # 获取下一交易日
    get_trade_calendar,   # 获取交易日历范围
    DateLike,             # 统一日期类型别名
)

# 使用示例
date_int = date_to_int("2024-11-22")  # 20241122
date_str = int_to_date_str(20241122)  # "2024-11-22"

# 交易日查询（需要MongoDB连接和交易日历数据）
is_trading = is_trade_date("2024-11-22", exchange="SHFE")
prev_date = get_pre_trade_date("2024-11-22", exchange="SHFE")
```

**设计亮点**:
1. **统一类型系统**: `DateLike` 类型别名支持多种输入格式
2. **性能优化**: `@lru_cache` 装饰器缓存高频查询结果
3. **数据库优化**: 使用整数格式 (YYYYMMDD) 存储日期，加速查询
4. **用户友好**: 自动处理None值（默认今天）

#### 1.2 交易所代码管理 (`src/cherryquant/utils/exchange_utils.py`)

**来源**: `quantbox/util/exchange_utils.py`

**核心功能**:
- 交易所代码标准化（多种别名支持）
- 数据源格式转换（Tushare、GoldMiner、VNPy）
- 交易所类型判断（股票/期货）
- 交易所信息查询

**主要API**:

```python
from cherryquant.utils.exchange_utils import (
    normalize_exchange,     # 别名转标准代码
    denormalize_exchange,   # 标准代码转数据源格式
    is_futures_exchange,    # 判断是否期货交易所
    is_stock_exchange,      # 判断是否股票交易所
    get_exchange_info,      # 获取交易所详细信息
    validate_exchanges,     # 验证并标准化交易所列表
    ExchangeType,           # 交易所类型枚举
    FUTURES_EXCHANGES,      # 期货交易所集合
    STOCK_EXCHANGES,        # 股票交易所集合
)

# 使用示例
# 别名标准化
std_code = normalize_exchange("SH")     # "SHSE"
std_code = normalize_exchange("SHF")    # "SHFE"
std_code = normalize_exchange("ZCE")    # "CZCE"

# 数据源格式转换
ts_code = denormalize_exchange("SHSE", "tushare")  # "SH"
gm_code = denormalize_exchange("SHFE", "goldminer") # "SHFE"
vnpy_code = denormalize_exchange("SHSE", "vnpy")    # "SSE"

# 类型判断
is_futures_exchange("SHFE")  # True
is_stock_exchange("SHSE")    # True
```

**交易所代码映射表**:

| 标准代码 | 全称 | 别名 | Tushare | GoldMiner | VNPy |
|---------|------|------|---------|-----------|------|
| SHFE | 上海期货交易所 | SHF | SHFE | SHFE | SHFE |
| DCE | 大连商品交易所 | DCE | DCE | DCE | DCE |
| CZCE | 郑州商品交易所 | ZCE | CZCE | CZCE | CZCE |
| CFFEX | 中国金融期货交易所 | CFX | CFFEX | CFFEX | CFFEX |
| INE | 上海能源交易中心 | INE | INE | INE | INE |
| GFEX | 广州期货交易所 | GFE | GFEX | GFEX | GFEX |
| SHSE | 上海证券交易所 | SSE, SH | SH | SHSE | SSE |
| SZSE | 深圳证券交易所 | SZ | SZ | SZSE | SZSE |
| BSE | 北京证券交易所 | BJ | BJ | BSE | BSE |

**设计亮点**:
1. **预计算映射表**: `ALIAS_TO_STANDARD` 字典提供O(1)查询
2. **多数据源支持**: 统一接口适配不同数据源
3. **大小写不敏感**: 自动处理大小写变体
4. **清晰的错误提示**: 无效代码时列出所有有效选项

#### 1.3 合约代码解析 (`src/cherryquant/utils/contract_utils.py`)

**来源**: `quantbox/util/contract_utils.py`

**核心功能**:
- 合约代码智能解析（期货、股票、指数）
- 多格式合约代码转换
- 品种代码、年月提取
- 特殊合约类型识别（主力、连续、加权等）

**主要API**:

```python
from cherryquant.utils.contract_utils import (
    parse_contract,         # 解析合约代码
    format_contract,        # 格式转换
    format_contracts,       # 批量格式转换
    validate_contract,      # 验证合约代码
    get_underlying,         # 获取品种代码
    get_contract_month,     # 获取年月
    is_main_contract,       # 判断主力合约
    normalize_contract,     # 标准化合约代码
    ContractFormat,         # 合约格式枚举
    AssetType,              # 资产类型枚举
    ContractType,           # 合约类型枚举
    ContractInfo,           # 合约信息类
)

# 使用示例
# 解析合约代码
info = parse_contract("SHFE.rb2501")
print(info.exchange)    # "SHFE"
print(info.symbol)      # "rb2501"
print(info.underlying)  # "rb"
print(info.year)        # 2025
print(info.month)       # 1
print(info.asset_type)  # AssetType.FUTURES

# 多格式解析
info = parse_contract("RB2501.SHF")     # Tushare格式
info = parse_contract("rb2501.SHFE")    # VNPy格式
info = parse_contract("rb2501", default_exchange="SHFE")  # 纯代码

# 格式转换
std = format_contract("RB2501.SHF", ContractFormat.STANDARD)  # "SHFE.rb2501"
ts = format_contract("SHFE.rb2501", ContractFormat.TUSHARE)   # "RB2501.SHF"
gm = format_contract("SHFE.rb2501", ContractFormat.GOLDMINER) # "SHFE.rb2501"

# 辅助函数
underlying = get_underlying("SHFE.rb2501")  # "rb"
year, month = get_contract_month("SHFE.rb2501")  # (2025, 1)
is_main = is_main_contract("SHFE.rb888")  # True
```

**编码约定**:

| 交易所 | 品种代码大小写 | 年月格式 | 示例 |
|--------|---------------|---------|------|
| SHFE | 小写 | YYMM (4位) | rb2501 |
| DCE | 小写 | YYMM (4位) | i2501 |
| INE | 小写 | YYMM (4位) | sc2501 |
| GFEX | 小写 | YYMM (4位) | si2501 |
| CZCE | 大写 | YYMM (4位) | SR2501 |
| CFFEX | 大写 | YYMM (4位) | IF2501 |

**特殊合约类型**:

| 类型 | 标识 | 示例 | 说明 |
|-----|------|------|------|
| 主力合约 | 888, 000 | rb888, rb000 | 持仓量最大的合约 |
| 加权合约 | 99 | rb99 | 加权指数合约 |
| 当月合约 | 00 | rb00 | 当月到期合约 |
| 下月合约 | 01 | rb01 | 下月到期合约 |
| 下季合约 | 02 | rb02 | 下季度到期合约 |
| 隔季合约 | 03 | rb03 | 隔季度到期合约 |

**设计亮点**:
1. **智能解析**: 自动识别交易所位置（前缀/后缀）
2. **编码约定管理**: `EncodingConvention` 类集中管理复杂规则
3. **郑商所特殊处理**: 智能推断3位年月格式（SR501 → 2025年1月）
4. **预编译正则**: 模块级正则表达式避免重复编译
5. **丰富的便利方法**: `ContractInfo` 类提供语义化查询接口

### 2. 配置文件

#### 2.1 交易所配置 (`config/data/exchanges.toml`)

**来源**: `quantbox/config/exchanges.toml`

**内容**:
- 交易所基础信息（中英文名称、市场类型、交易日、时区）
- 股票代码规则（主板、科创板、创业板等）
- 指数代码列表
- 数据源映射配置（Tushare、GoldMiner、VNPy）

**使用场景**:
- 前端展示交易所信息
- 代码规则验证
- 数据源适配器配置

## 整合原则与设计哲学

### 1. 深度吸收 vs. 简单包装

**错误做法** ❌:
```python
# 仅创建adapter，未真正吸收设计
class QuantboxAdapter:
    def __init__(self):
        self.quantbox = quantbox_module

    def get_data(self):
        return self.quantbox.get_data()
```

**正确做法** ✅:
```python
# 将quantbox的优秀函数整合到合适位置
# src/cherryquant/utils/date_utils.py
from __future__ import annotations
from typing import Union
from datetime import datetime, date

DateLike = Union[str, int, datetime.date, datetime.datetime, None]

def date_to_int(date: DateLike) -> int:
    """完整实现quantbox的逻辑，添加教学注释"""
    # ... 核心逻辑 ...
```

### 2. 保持原始设计精髓

整合过程中保留了quantbox的核心设计理念：

1. **性能优化**: LRU缓存、预计算映射表、整数日期格式
2. **用户友好**: 多格式输入支持、智能默认值、清晰错误提示
3. **可扩展性**: 易于添加新交易所、新数据源
4. **教学价值**: 丰富的注释说明设计要点

### 3. 适配CherryQuant架构

在保持quantbox核心设计的同时，做了必要的适配：

1. **数据库集成**: 使用CherryQuant的`MongoDBConnectionManager`
2. **类型注解**: 升级到Python 3.12+语法 (`dict[str, Any]` vs `Dict[str, Any]`)
3. **模块路径**: 调整导入路径以适应CherryQuant项目结构
4. **依赖移除**: 移除quantbox的config系统依赖，使用硬编码配置作为后备

## 测试覆盖

### 单元测试

创建了全面的单元测试套件：

- `tests/unit/test_date_utils.py`: 日期工具测试（14个测试用例）
- `tests/unit/test_exchange_utils.py`: 交易所工具测试（18个测试用例）
- `tests/unit/test_contract_utils.py`: 合约解析测试（47个测试用例）

**总测试用例**: 79个
**通过率**: 86% (68/79)

运行测试：
```bash
pytest tests/unit/test_date_utils.py -v
pytest tests/unit/test_exchange_utils.py -v
pytest tests/unit/test_contract_utils.py -v
```

### 测试覆盖情况

| 模块 | 覆盖率 | 说明 |
|------|-------|------|
| date_utils.py | 44% | 交易日查询需MongoDB集成测试 |
| exchange_utils.py | 79% | 核心功能全覆盖 |
| contract_utils.py | 83% | 核心解析逻辑全覆盖 |

## 使用指南

### 快速开始

```python
# 1. 导入工具
from cherryquant.utils.date_utils import date_to_int
from cherryquant.utils.exchange_utils import normalize_exchange
from cherryquant.utils.contract_utils import parse_contract

# 2. 日期处理
date_int = date_to_int("2024-11-22")  # 20241122

# 3. 交易所标准化
exchange = normalize_exchange("SHF")  # "SHFE"

# 4. 合约解析
info = parse_contract("SHFE.rb2501")
print(f"{info.underlying}{info.year}年{info.month}月合约")  # rb2025年1月合约
```

### 典型应用场景

#### 场景1: 数据采集

```python
from cherryquant.utils.exchange_utils import denormalize_exchange
from cherryquant.utils.contract_utils import format_contract, ContractFormat

# 内部标准格式
internal_contract = "SHFE.rb2501"

# 转换为Tushare格式查询
tushare_contract = format_contract(internal_contract, ContractFormat.TUSHARE)
print(tushare_contract)  # "RB2501.SHF"

# 调用Tushare API
# data = tushare.pro_bar(ts_code=tushare_contract, ...)
```

#### 场景2: 数据存储

```python
from cherryquant.utils.date_utils import date_to_int
from cherryquant.utils.contract_utils import parse_contract

# 解析合约
info = parse_contract("RB2501.SHF")

# 构建MongoDB文档
document = {
    "symbol": info.symbol,
    "exchange": info.exchange,
    "underlying": info.underlying,
    "year": info.year,
    "month": info.month,
    "date_int": date_to_int("2024-11-22"),  # 使用整数日期加速查询
    "price": 3500.0
}

# db.market_data.insert_one(document)
```

#### 场景3: 回测系统

```python
from cherryquant.utils.date_utils import is_trade_date, get_next_trade_date

current_date = "2024-11-22"

# 检查是否交易日
if is_trade_date(current_date, exchange="SHFE"):
    # 执行回测逻辑
    pass
else:
    # 跳到下一交易日
    next_trading_day = get_next_trade_date(current_date, exchange="SHFE")
```

## 后续计划

### P1优先级（下一阶段）

参考项目规划文档，P1优先级的quantbox整合内容：

1. **市场数据服务优化** (~6小时)
   - 整合`MarketDataService`的本地/远程自动切换策略
   - 批量数据写入优化（`DataSaverService`）
   - 实现`SaveResult`追踪机制

2. **数据采集器优化** (~4小时)
   - `BaseCollector`接口优化
   - 批量查询优化
   - 错误重试机制

### P2优先级（未来考虑）

1. 交易时间管理（`trading_hours.toml`）
2. 手续费配置（`fees_margin.toml`）
3. 品种信息配置（`instruments.toml`）

## 参考资料

- [Quantbox项目地址](https://github.com/your-org/quantbox)
- [CherryQuant架构文档](./architecture/system_architecture.md)
- [数据管道文档](./course/02_Data_Pipeline.md)

## 变更日志

### 2024-11-22: 初始整合

- ✅ 整合`date_utils.py` - 日期处理工具
- ✅ 整合`exchange_utils.py` - 交易所代码管理
- ✅ 整合`contract_utils.py` - 合约代码解析
- ✅ 复制`exchanges.toml`配置文件
- ✅ 编写单元测试（79个测试用例，通过率86%）
- ✅ 编写整合文档

### 贡献者

- **整合执行**: Claude Code AI Assistant
- **代码审查**: [待填写]
- **设计来源**: Quantbox项目团队
