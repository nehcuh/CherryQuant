# 合约代码标准化说明

## 概述

CherryQuant 使用 VNPy 作为交易接口，因此需要确保所有合约代码符合 VNPy 的编码规范。由于不同数据源（如 Tushare）使用的合约代码格式与 VNPy 不完全一致，我们实现了 `SymbolStandardizer` 工具来进行统一转换。

## 主要差异

### 1. 郑州商品交易所 (CZCE)

这是**最关键的差异**：

- **Tushare 格式**: `SR2501` (大写字母 + 4位数字，完整年月)
- **VNPy/CTP 格式**: `SR501` (大写字母 + 3位数字，去掉年份千位)

**原因**: 郑商所在 2010 年后改用 4 位数字表示合约，但交易系统（CTP）仍使用传统的 3 位数字格式。

**示例转换**:
```
SR2501 (Tushare) → SR501 (VNPy)
CF2503 (Tushare) → CF503 (VNPy)
TA2512 (Tushare) → TA512 (VNPy)
```

### 2. 上海期货交易所 (SHFE) 和大连商品交易所 (DCE)

- **Tushare 格式**: `RB2501.SHF`, `I2501.DCE` (大写)
- **VNPy 格式**: `rb2501.SHFE`, `i2501.DCE` (小写，完整交易所名)

**示例转换**:
```
RB2501.SHF (Tushare) → rb2501.SHFE (VNPy)
I2511.DCE (Tushare)  → i2511.DCE (VNPy)
CU2512.SHF (Tushare) → cu2512.SHFE (VNPy)
```

### 3. 中国金融期货交易所 (CFFEX)

- **Tushare 格式**: `IF2501.CFX`
- **VNPy 格式**: `IF2501.CFFEX` (保持大写，完整交易所名)

**示例转换**:
```
IF2512.CFX (Tushare) → IF2512.CFFEX (VNPy)
IC2601.CFX (Tushare) → IC2601.CFFEX (VNPy)
```

## 交易所代码映射

| 交易所 | Tushare | VNPy | 说明 |
|--------|---------|------|------|
| 上海期货交易所 | SHF | SHFE | Shanghai Futures Exchange |
| 大连商品交易所 | DCE | DCE | Dalian Commodity Exchange |
| 郑州商品交易所 | ZCE | CZCE | Zhengzhou Commodity Exchange |
| 中国金融期货交易所 | CFX | CFFEX | China Financial Futures Exchange |
| 上海国际能源交易中心 | INE | INE | Shanghai International Energy Exchange |

## 使用方法

### 基本转换

```python
from src.cherryquant.utils.symbol_standardizer import SymbolStandardizer

# Tushare -> VNPy
vnpy_symbol, vnpy_exchange = SymbolStandardizer.tushare_to_vnpy("SR2501.ZCE")
print(f"{vnpy_symbol}.{vnpy_exchange}")  # 输出: SR501.CZCE

# VNPy -> Tushare
ts_code = SymbolStandardizer.vnpy_to_tushare("SR501", "CZCE")
print(ts_code)  # 输出: SR2501.ZCE
```

### 生成 vt_symbol

```python
# 创建 VNPy 的 vt_symbol 格式
vt_symbol = SymbolStandardizer.get_vt_symbol("rb2501", "SHFE")
print(vt_symbol)  # 输出: rb2501.SHFE

# 解析 vt_symbol
symbol, exchange = SymbolStandardizer.parse_vt_symbol("rb2501.SHFE")
print(f"Symbol: {symbol}, Exchange: {exchange}")
```

### 便捷函数

```python
from src.cherryquant.utils.symbol_standardizer import (
    standardize_tushare_contract,
    create_vt_symbol
)

# 快速标准化
symbol, exchange = standardize_tushare_contract("RB2501.SHF")
print(f"{symbol}.{exchange}")  # rb2501.SHFE

# 快速创建 vt_symbol
vt_symbol = create_vt_symbol("rb2501", "SHFE")
print(vt_symbol)  # rb2501.SHFE
```

## 数据库存储

所有保存到 `market_data` 表的合约代码都使用 **VNPy 格式**:

```sql
-- 正确的存储格式
INSERT INTO market_data (symbol, exchange, ...)
VALUES ('rb2501', 'SHFE', ...);  -- 上期所

INSERT INTO market_data (symbol, exchange, ...)
VALUES ('SR501', 'CZCE', ...);   -- 郑商所 (注意是3位数字)

INSERT INTO market_data (symbol, exchange, ...)
VALUES ('i2511', 'DCE', ...);    -- 大商所
```

## 历史数据下载

`scripts/init_historical_data.py` 已经集成了自动转换功能：

1. 从 Tushare 下载数据时使用 Tushare 格式
2. 转换数据时自动使用 `SymbolStandardizer` 转换为 VNPy 格式
3. 保存到数据库时使用 VNPy 格式

**无需手动转换**，系统会自动处理。

## 与 VNPy 交易接口对接

从数据库读取数据后，可以直接用于 VNPy 交易：

```python
from vnpy.trader.constant import Exchange

# 从数据库读取
symbol = "rb2501"  # 已经是VNPy格式
exchange = Exchange.SHFE

# 构造 vt_symbol 用于订阅或交易
vt_symbol = f"{symbol}.{exchange.value}"  # rb2501.SHFE

# 或使用标准化工具
vt_symbol = create_vt_symbol(symbol, exchange.value)
```

## 注意事项

1. **郑商所合约是关键**: 务必确保郑商所合约使用 3 位数字格式 (如 SR501)
2. **数据库一致性**: 所有保存到数据库的数据必须使用 VNPy 格式
3. **API 调用**: 调用 Tushare API 时使用 Tushare 格式，调用 VNPy API 时使用 VNPy 格式
4. **双向转换**: 工具支持双向转换，但要注意郑商所年份推断的准确性

## 测试验证

运行测试以验证转换是否正确：

```bash
# 查看测试示例
grep -A 10 "test_cases =" test_symbol_standardizer.py

# 测试实际数据下载
uv run python test_data_download_vnpy.py
```

## 常见问题

### Q: 为什么郑商所要用 3 位数字？
A: CTP 交易系统沿用了郑商所的历史格式（3 位数字），虽然郑商所在 2010 年后改用了 4 位数字，但为了兼容性，CTP 和 VNPy 仍使用 3 位数字。

### Q: 如果年份推断错误怎么办？
A: `vnpy_to_tushare` 方法在转换郑商所合约时会根据月份推断年份。如果跨度较大（如 2029 年的合约），需要确保推断逻辑正确。

### Q: 可以直接存储 Tushare 格式吗？
A: **不推荐**。为了与 VNPy 交易接口无缝对接，强烈建议数据库中统一使用 VNPy 格式。

## 参考

- [VNPy 官方文档](https://www.vnpy.com/)
- [CTP API 文档](http://www.sfit.com.cn/DocumentDown/api_3/index.htm)
- Tushare Pro API: https://tushare.pro/document/2
