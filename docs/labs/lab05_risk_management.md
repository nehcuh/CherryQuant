# Lab 05: 风险管理系统实验

## 实验信息

- **难度**: ⭐⭐⭐ 中级
- **预计时间**: 4 小时
- **相关模块**: Module 4 (交易执行), config/settings/base.py (RiskConfig)
- **截止日期**: Week 7 结束

## 学习目标

完成本实验后，你将能够：

1. ✅ 理解量化交易系统的多层风险控制架构
2. ✅ 配置和调优风险参数（持仓限制、止损、相关性控制等）
3. ✅ 实现实时风控检查逻辑
4. ✅ 测试风控系统在极端情况下的表现
5. ✅ 分析风控失效的常见原因
6. ✅ 设计风险监控告警规则

## 实验前准备

### 前置实验

- [x] Lab 01: 环境搭建与首次运行
- [x] Lab 02: 追踪数据流
- [x] Lab 03: 提示词工程实验
- [x] Lab 04: 模拟账户 vs 实盘执行与 PnL 对账实验

### 必备知识

- [ ] 理解期货交易的基本概念（保证金、杠杆、强平）
- [ ] 了解风险管理的基本原则（仓位管理、止损止盈）
- [ ] 理解相关性和资产组合风险

### 参考资料

- 📖 `config/settings/base.py` - RiskConfig 类定义
- 📖 `src/risk/portfolio_risk_manager.py` - 风险管理器实现
- 📖 `docs/course/04_Trading_Execution.md`

---

## 实验背景

### 为什么风险管理至关重要？

在量化交易中，**风险管理是生存的第一法则**：

> "在交易中，你的首要任务不是赚钱，而是不亏钱。" - Paul Tudor Jones

**真实案例：**

- 📉 **长期资本管理公司（LTCM）**: 1998 年因杠杆过高、风控失效而破产，亏损 46 亿美元
- 📉 **骑士资本（Knight Capital）**: 2012 年因算法 Bug 45 分钟内亏损 4.4 亿美元
- 📉 **Archegos 爆仓事件**: 2021 年因杠杆过高、风险集中导致 200 亿美元损失

### CherryQuant 的多层风控架构

```
┌───────────────────────────────────────────────────────────┐
│                  Level 1: 策略层风控                       │
│  - 单次交易资金限制                                        │
│  - 止损止盈设置                                           │
└─────────────────────────┬─────────────────────────────────┘
                          ↓
┌─────────────────────────┴─────────────────────────────────┐
│                  Level 2: 组合层风控                       │
│  - 总持仓限制 (max_total_capital_usage)                    │
│  - 单品种持仓限制 (max_single_position_pct)                │
│  - 相关性控制 (max_correlation_threshold)                  │
└─────────────────────────┬─────────────────────────────────┘
                          ↓
┌─────────────────────────┴─────────────────────────────────┐
│                  Level 3: 账户层风控                       │
│  - 可用资金检查                                           │
│  - 保证金充足性验证                                        │
│  - 强平风险检测                                           │
└─────────────────────────┬─────────────────────────────────┘
                          ↓
┌─────────────────────────┴─────────────────────────────────┐
│                  Level 4: 交易所层风控                     │
│  - 涨跌停限制                                             │
│  - 熔断机制                                               │
│  - 异常波动暂停                                           │
└───────────────────────────────────────────────────────────┘
```

本实验重点关注 **Level 1-3**（系统可控部分）。

---

## 实验任务

### 任务 1: 理解风险配置参数 (30 分钟)

#### 1.1 查看风险配置

打开 `config/settings/base.py`，找到 `RiskConfig` 类：

```python
class RiskConfig(BaseSettings):
    """风险管理配置"""

    # 总持仓限制
    max_total_capital_usage: float = Field(
        default=0.8,
        description="最大总资金使用率（0-1）"
    )

    # 单品种限制
    max_single_position_pct: float = Field(
        default=0.3,
        description="单个品种最大持仓占比（0-1）"
    )

    # 相关性控制
    max_correlation_threshold: float = Field(
        default=0.7,
        description="品种间最大相关系数（0-1）"
    )

    # 止损设置
    max_daily_loss_pct: float = Field(
        default=0.05,
        description="单日最大亏损比例（0-1）"
    )

    stop_loss_pct: float = Field(
        default=0.02,
        description="单笔交易止损比例（0-1）"
    )

    take_profit_pct: float = Field(
        default=0.04,
        description="单笔交易止盈比例（0-1）"
    )

    # 杠杆控制
    max_leverage: float = Field(
        default=3.0,
        description="最大杠杆倍数"
    )

    # 强平预警
    force_close_threshold: float = Field(
        default=0.2,
        description="强平预警阈值（保证金占用率）"
    )
```

#### 1.2 理解每个参数的含义

创建 `lab05_risk_analysis.py`:

```python
"""
Lab 05: 风险参数分析
"""
from config.settings.settings import get_settings


def analyze_risk_config():
    """分析风险配置参数"""
    settings = get_settings()
    risk = settings.risk

    print("=" * 60)
    print("CherryQuant 风险管理配置分析")
    print("=" * 60)

    # 总资金限制
    print(f"\n1. 总资金使用限制: {risk.max_total_capital_usage * 100:.0f}%")
    print(f"   含义: 最多使用 {risk.max_total_capital_usage * 100:.0f}% 的资金进行交易")
    print(f"   保留: {(1 - risk.max_total_capital_usage) * 100:.0f}% 作为安全垫")

    # 单品种限制
    print(f"\n2. 单品种持仓限制: {risk.max_single_position_pct * 100:.0f}%")
    print(f"   含义: 单个品种最多占用 {risk.max_single_position_pct * 100:.0f}% 的资金")
    print(f"   目的: 避免风险集中在单一品种")

    # 相关性控制
    print(f"\n3. 相关性阈值: {risk.max_correlation_threshold}")
    print(f"   含义: 持仓品种间相关系数不应超过 {risk.max_correlation_threshold}")
    print(f"   目的: 避免同向波动导致组合风险放大")

    # 止损止盈
    print(f"\n4. 止损/止盈设置:")
    print(f"   单笔止损: {risk.stop_loss_pct * 100:.0f}%")
    print(f"   单笔止盈: {risk.take_profit_pct * 100:.0f}%")
    print(f"   盈亏比: {risk.take_profit_pct / risk.stop_loss_pct:.1f}:1")

    # 单日亏损限制
    print(f"\n5. 单日最大亏损: {risk.max_daily_loss_pct * 100:.0f}%")
    print(f"   含义: 单日累计亏损达到 {risk.max_daily_loss_pct * 100:.0f}% 时停止交易")
    print(f"   目的: 防止连续亏损失控")

    # 杠杆控制
    print(f"\n6. 最大杠杆: {risk.max_leverage}x")
    print(f"   含义: 最多可以使用 {risk.max_leverage} 倍杠杆")
    print(f"   风险: 杠杆越高，爆仓风险越大")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    analyze_risk_config()
```

运行：
```bash
uv run python lab05_risk_analysis.py
```

**✅ 检查点**: 理解每个风险参数的含义和作用

---

### 任务 2: 实现仓位检查逻辑 (1 小时)

#### 2.1 创建仓位检查器

创建 `src/cherryquant/risk/position_checker.py`:

```python
"""
仓位检查器 - Level 2 组合层风控
"""
from typing import Dict, List, Optional
from pydantic import BaseModel
from config.settings.settings import get_settings


class Position(BaseModel):
    """持仓信息"""
    symbol: str
    quantity: int
    avg_price: float
    current_price: float
    margin_used: float  # 占用保证金


class PositionCheckResult(BaseModel):
    """仓位检查结果"""
    passed: bool
    reason: str = ""
    current_usage: float = 0.0  # 当前资金使用率
    limit: float = 0.0  # 限制值


class PositionChecker:
    """
    仓位检查器

    教学要点：
    1. 风险规则的代码实现
    2. 多条件验证
    3. 清晰的错误提示
    """

    def __init__(self):
        self.settings = get_settings()
        self.risk = self.settings.risk

    def check_total_position_limit(
        self,
        existing_positions: List[Position],
        new_margin: float,
        total_capital: float
    ) -> PositionCheckResult:
        """
        检查总持仓限制

        Args:
            existing_positions: 现有持仓列表
            new_margin: 新订单需要的保证金
            total_capital: 总资金

        Returns:
            检查结果
        """
        # 计算现有持仓占用的保证金
        current_margin = sum(pos.margin_used for pos in existing_positions)

        # 加上新订单的保证金
        total_margin = current_margin + new_margin

        # 计算资金使用率
        usage_rate = total_margin / total_capital

        # 检查是否超限
        if usage_rate > self.risk.max_total_capital_usage:
            return PositionCheckResult(
                passed=False,
                reason=f"总资金使用率 {usage_rate:.1%} 超过限制 {self.risk.max_total_capital_usage:.1%}",
                current_usage=usage_rate,
                limit=self.risk.max_total_capital_usage
            )

        return PositionCheckResult(
            passed=True,
            current_usage=usage_rate,
            limit=self.risk.max_total_capital_usage
        )

    def check_single_position_limit(
        self,
        symbol: str,
        existing_positions: List[Position],
        new_margin: float,
        total_capital: float
    ) -> PositionCheckResult:
        """
        检查单品种持仓限制

        Args:
            symbol: 品种代码
            existing_positions: 现有持仓列表
            new_margin: 新订单需要的保证金
            total_capital: 总资金

        Returns:
            检查结果
        """
        # 找到该品种的现有持仓
        current_symbol_margin = sum(
            pos.margin_used
            for pos in existing_positions
            if pos.symbol == symbol
        )

        # 加上新订单的保证金
        total_symbol_margin = current_symbol_margin + new_margin

        # 计算该品种的资金占比
        symbol_usage = total_symbol_margin / total_capital

        # 检查是否超限
        if symbol_usage > self.risk.max_single_position_pct:
            return PositionCheckResult(
                passed=False,
                reason=f"{symbol} 持仓占比 {symbol_usage:.1%} 超过限制 {self.risk.max_single_position_pct:.1%}",
                current_usage=symbol_usage,
                limit=self.risk.max_single_position_pct
            )

        return PositionCheckResult(
            passed=True,
            current_usage=symbol_usage,
            limit=self.risk.max_single_position_pct
        )

    def check_leverage(
        self,
        total_position_value: float,
        total_capital: float
    ) -> PositionCheckResult:
        """
        检查杠杆限制

        Args:
            total_position_value: 总持仓价值
            total_capital: 总资金

        Returns:
            检查结果
        """
        current_leverage = total_position_value / total_capital

        if current_leverage > self.risk.max_leverage:
            return PositionCheckResult(
                passed=False,
                reason=f"杠杆倍数 {current_leverage:.1f}x 超过限制 {self.risk.max_leverage:.1f}x",
                current_usage=current_leverage,
                limit=self.risk.max_leverage
            )

        return PositionCheckResult(
            passed=True,
            current_usage=current_leverage,
            limit=self.risk.max_leverage
        )
```

#### 2.2 测试仓位检查器

创建 `tests/unit/test_position_checker.py`:

```python
"""
测试仓位检查器
"""
import pytest
from src.cherryquant.risk.position_checker import (
    PositionChecker,
    Position
)


def test_check_total_position_limit_pass():
    """测试总持仓检查 - 通过"""
    checker = PositionChecker()

    # 现有持仓：占用 50% 资金
    existing = [
        Position(
            symbol="rb2501",
            quantity=10,
            avg_price=3500,
            current_price=3520,
            margin_used=50000
        )
    ]

    # 新订单：需要 20% 资金
    # 总计 70%，低于默认限制 80%
    result = checker.check_total_position_limit(
        existing_positions=existing,
        new_margin=20000,
        total_capital=100000
    )

    assert result.passed == True
    assert result.current_usage == 0.7


def test_check_total_position_limit_fail():
    """测试总持仓检查 - 失败"""
    checker = PositionChecker()

    # 现有持仓：占用 70% 资金
    existing = [
        Position(
            symbol="rb2501",
            quantity=10,
            avg_price=3500,
            current_price=3520,
            margin_used=70000
        )
    ]

    # 新订单：需要 20% 资金
    # 总计 90%，超过默认限制 80%
    result = checker.check_total_position_limit(
        existing_positions=existing,
        new_margin=20000,
        total_capital=100000
    )

    assert result.passed == False
    assert "超过限制" in result.reason


def test_check_single_position_limit():
    """测试单品种持仓限制"""
    checker = PositionChecker()

    existing = []

    # 尝试开一个占用 40% 资金的仓位
    # 超过默认限制 30%
    result = checker.check_single_position_limit(
        symbol="rb2501",
        existing_positions=existing,
        new_margin=40000,
        total_capital=100000
    )

    assert result.passed == False
    assert result.current_usage == 0.4


# 添加更多测试...
```

运行测试：
```bash
uv run pytest tests/unit/test_position_checker.py -v
```

**✅ 检查点**: 所有测试通过

---

### 任务 3: 实现止损止盈逻辑 (45 分钟)

#### 3.1 创建止损止盈检查器

在 `src/cherryquant/risk/position_checker.py` 中添加：

```python
class StopLossChecker:
    """
    止损止盈检查器 - Level 1 策略层风控

    教学要点：
    1. 实时 PnL 计算
    2. 止损止盈触发逻辑
    3. 避免频繁止损（whipsaw）
    """

    def __init__(self):
        self.settings = get_settings()
        self.risk = self.settings.risk

    def check_stop_loss(
        self,
        entry_price: float,
        current_price: float,
        direction: str  # "long" or "short"
    ) -> tuple[bool, str]:
        """
        检查是否触发止损

        Args:
            entry_price: 开仓价格
            current_price: 当前价格
            direction: 方向（long/short）

        Returns:
            (是否触发, 原因)
        """
        # 计算盈亏比例
        if direction == "long":
            pnl_pct = (current_price - entry_price) / entry_price
        else:  # short
            pnl_pct = (entry_price - current_price) / entry_price

        # 检查止损
        if pnl_pct <= -self.risk.stop_loss_pct:
            return True, f"触发止损：亏损 {abs(pnl_pct):.2%}，超过止损线 {self.risk.stop_loss_pct:.2%}"

        # 检查止盈
        if pnl_pct >= self.risk.take_profit_pct:
            return True, f"触发止盈：盈利 {pnl_pct:.2%}，达到止盈线 {self.risk.take_profit_pct:.2%}"

        return False, "未触发止损止盈"

    def check_daily_loss_limit(
        self,
        today_pnl: float,
        total_capital: float
    ) -> tuple[bool, str]:
        """
        检查单日亏损限制

        Args:
            today_pnl: 今日盈亏（负数表示亏损）
            total_capital: 总资金

        Returns:
            (是否触发, 原因)
        """
        loss_pct = abs(today_pnl) / total_capital

        if today_pnl < 0 and loss_pct >= self.risk.max_daily_loss_pct:
            return True, f"单日亏损 {loss_pct:.2%} 达到限制 {self.risk.max_daily_loss_pct:.2%}，停止交易"

        return False, "未触发单日亏损限制"
```

#### 3.2 测试止损止盈

创建测试：

```python
def test_stop_loss_triggered():
    """测试止损触发"""
    checker = StopLossChecker()

    # 做多，亏损 3%（超过默认 2% 止损）
    triggered, reason = checker.check_stop_loss(
        entry_price=3500,
        current_price=3395,  # 下跌 3%
        direction="long"
    )

    assert triggered == True
    assert "止损" in reason


def test_take_profit_triggered():
    """测试止盈触发"""
    checker = StopLossChecker()

    # 做多，盈利 5%（超过默认 4% 止盈）
    triggered, reason = checker.check_stop_loss(
        entry_price=3500,
        current_price=3675,  # 上涨 5%
        direction="long"
    )

    assert triggered == True
    assert "止盈" in reason


def test_daily_loss_limit():
    """测试单日亏损限制"""
    checker = StopLossChecker()

    # 单日亏损 6%（超过默认 5% 限制）
    triggered, reason = checker.check_daily_loss_limit(
        today_pnl=-6000,
        total_capital=100000
    )

    assert triggered == True
    assert "单日亏损" in reason
```

---

### 任务 4: 模拟极端情况测试 (1 小时)

#### 4.1 创建压力测试场景

创建 `lab05_stress_test.py`:

```python
"""
Lab 05: 风险系统压力测试
"""
from src.cherryquant.risk.position_checker import (
    PositionChecker,
    StopLossChecker,
    Position
)


def stress_test_flash_crash():
    """
    场景 1: 闪崩（Flash Crash）

    模拟：持仓品种突然跌停（-10%）
    预期：触发止损，限制亏损
    """
    print("\n" + "=" * 60)
    print("压力测试 1: 闪崩场景")
    print("=" * 60)

    checker = StopLossChecker()

    # 持仓：rb2501 做多，开仓价 3500
    entry_price = 3500

    # 模拟价格下跌
    for drop_pct in [0.01, 0.02, 0.05, 0.10]:
        current_price = entry_price * (1 - drop_pct)
        triggered, reason = checker.check_stop_loss(
            entry_price=entry_price,
            current_price=current_price,
            direction="long"
        )

        print(f"\n价格下跌 {drop_pct:.1%}: {entry_price} → {current_price:.0f}")
        print(f"  触发: {triggered}")
        print(f"  原因: {reason}")

    print("\n✅ 结论：止损机制在 -2% 时触发，避免了更大亏损")


def stress_test_margin_call():
    """
    场景 2: 强平风险（Margin Call）

    模拟：多个持仓同时亏损，保证金不足
    """
    print("\n" + "=" * 60)
    print("压力测试 2: 强平风险场景")
    print("=" * 60)

    total_capital = 100000

    # 初始持仓：3 个品种，各占 30%
    positions = [
        Position(symbol="rb2501", quantity=10, avg_price=3500, current_price=3500, margin_used=30000),
        Position(symbol="hc2501", quantity=10, avg_price=3200, current_price=3200, margin_used=30000),
        Position(symbol="i2501", quantity=10, avg_price=800, current_price=800, margin_used=30000),
    ]

    print(f"\n初始状态:")
    print(f"  总资金: {total_capital}")
    print(f"  保证金占用: {sum(p.margin_used for p in positions)} ({sum(p.margin_used for p in positions) / total_capital:.1%})")

    # 模拟同时下跌 10%
    print(f"\n模拟：所有品种同时下跌 10%")

    # 计算亏损
    total_loss = 0
    for pos in positions:
        loss = pos.quantity * pos.avg_price * 0.10
        total_loss += loss
        print(f"  {pos.symbol}: 亏损 {loss:.0f}")

    print(f"\n总亏损: {total_loss:.0f}")
    print(f"剩余资金: {total_capital - total_loss:.0f}")
    print(f"保证金占用: {sum(p.margin_used for p in positions)}")

    # 检查是否触发强平
    remaining_capital = total_capital - total_loss
    margin_usage = sum(p.margin_used for p in positions) / remaining_capital

    if margin_usage > 0.8:
        print(f"\n⚠️  警告：保证金占用率 {margin_usage:.1%}，接近强平线！")
    else:
        print(f"\n✅ 安全：保证金占用率 {margin_usage:.1%}，风险可控")


def stress_test_correlation_risk():
    """
    场景 3: 相关性风险

    模拟：持有高相关性品种（rb, hc 都是钢铁类）
    预期：同涨同跌，风险放大
    """
    print("\n" + "=" * 60)
    print("压力测试 3: 相关性风险场景")
    print("=" * 60)

    print("\n情况 A: 分散持仓（低相关性）")
    print("  持仓: rb2501 (螺纹钢) + c2501 (玉米)")
    print("  相关系数: 0.2")
    print("  钢铁下跌 10%，玉米上涨 2%")
    print("  组合亏损: 约 4%")

    print("\n情况 B: 集中持仓（高相关性）")
    print("  持仓: rb2501 (螺纹钢) + hc2501 (热卷)")
    print("  相关系数: 0.9")
    print("  钢铁下跌 10%，两个品种都跌")
    print("  组合亏损: 约 10%")

    print("\n✅ 结论：低相关性持仓可以分散风险")


if __name__ == "__main__":
    stress_test_flash_crash()
    stress_test_margin_call()
    stress_test_correlation_risk()
```

运行压力测试：
```bash
uv run python lab05_stress_test.py
```

**✅ 检查点**: 理解极端情况下风控系统的表现

---

### 任务 5: 配置和调优风险参数 (45 分钟)

#### 5.1 创建风险参数优化器

编辑 `.env` 文件，尝试不同的风险参数：

```bash
# 保守配置（低风险）
RISK_MAX_TOTAL_CAPITAL_USAGE=0.5  # 只用 50% 资金
RISK_MAX_SINGLE_POSITION_PCT=0.2  # 单品种最多 20%
RISK_STOP_LOSS_PCT=0.01           # 1% 止损
RISK_TAKE_PROFIT_PCT=0.03         # 3% 止盈
RISK_MAX_LEVERAGE=2.0             # 最大 2 倍杠杆

# 激进配置（高风险）
# RISK_MAX_TOTAL_CAPITAL_USAGE=0.9
# RISK_MAX_SINGLE_POSITION_PCT=0.5
# RISK_STOP_LOSS_PCT=0.05
# RISK_TAKE_PROFIT_PCT=0.10
# RISK_MAX_LEVERAGE=5.0
```

#### 5.2 对比不同配置的效果

创建 `lab05_config_comparison.py`:

```python
"""
对比不同风险配置的效果
"""
from dataclasses import dataclass


@dataclass
class RiskProfile:
    """风险配置档案"""
    name: str
    capital_usage: float
    single_position: float
    stop_loss: float
    take_profit: float
    leverage: float


# 定义三种风险档案
profiles = [
    RiskProfile(
        name="保守型",
        capital_usage=0.5,
        single_position=0.2,
        stop_loss=0.01,
        take_profit=0.03,
        leverage=2.0
    ),
    RiskProfile(
        name="平衡型",
        capital_usage=0.7,
        single_position=0.3,
        stop_loss=0.02,
        take_profit=0.04,
        leverage=3.0
    ),
    RiskProfile(
        name="激进型",
        capital_usage=0.9,
        single_position=0.5,
        stop_loss=0.05,
        take_profit=0.10,
        leverage=5.0
    ),
]


def compare_profiles():
    """对比风险档案"""
    print("=" * 80)
    print("风险配置对比")
    print("=" * 80)

    print(f"\n{'配置':<10} {'资金使用':<12} {'单品种':<12} {'止损':<10} {'止盈':<10} {'杠杆':<8}")
    print("-" * 80)

    for profile in profiles:
        print(
            f"{profile.name:<10} "
            f"{profile.capital_usage:<12.1%} "
            f"{profile.single_position:<12.1%} "
            f"{profile.stop_loss:<10.1%} "
            f"{profile.take_profit:<10.1%} "
            f"{profile.leverage:<8.1f}x"
        )

    print("\n" + "=" * 80)
    print("分析：")
    print("-" * 80)

    for profile in profiles:
        print(f"\n{profile.name}:")

        # 最大可能亏损
        max_loss = profile.capital_usage * profile.stop_loss
        print(f"  单次最大亏损: {max_loss:.2%}")

        # 盈亏比
        risk_reward = profile.take_profit / profile.stop_loss
        print(f"  盈亏比: {risk_reward:.1f}:1")

        # 杠杆风险
        leveraged_loss = max_loss * profile.leverage
        print(f"  杠杆放大后最大亏损: {leveraged_loss:.2%}")

        # 风险评级
        risk_score = (
            profile.capital_usage * 0.3 +
            profile.single_position * 0.2 +
            profile.stop_loss * 0.3 +
            profile.leverage * 0.2 / 5.0
        )
        print(f"  风险评分: {risk_score:.2f} (越高越激进)")


if __name__ == "__main__":
    compare_profiles()
```

运行：
```bash
uv run python lab05_config_comparison.py
```

**✅ 检查点**: 理解不同风险配置的权衡

---

## 实验总结

### 完成情况自查

- [ ] 理解 CherryQuant 的多层风控架构
- [ ] 实现了仓位检查器并通过测试
- [ ] 实现了止损止盈检查器
- [ ] 完成了压力测试（闪崩、强平、相关性）
- [ ] 对比了不同风险配置的效果

### 关键收获

1. **风险管理是量化交易的生命线** - Bug 可能导致真金白银的损失
2. **多层防护** - 策略层、组合层、账户层、交易所层
3. **参数调优** - 不同风险偏好需要不同的配置
4. **压力测试** - 在极端情况下验证风控系统
5. **测试先行** - 风控代码必须有充分的测试覆盖

### 思考题

1. **如果同时持有 rb（螺纹钢）、hc（热卷）、i（铁矿石）三个品种，相关性如何控制？**

2. **为什么不建议设置过紧的止损（如 0.5%）？**

   提示：考虑"whipsaw"（来回打脸）现象

3. **单日亏损限制触发后，应该完全停止交易吗？还是可以平仓？**

4. **如何防止因网络延迟导致的止损失效？**

5. **风险参数应该固定不变，还是根据市场波动性动态调整？**

---

## 延伸挑战

### 挑战 1: 实现动态止损

实现 Trailing Stop（移动止损）：
- 当盈利达到一定比例时，止损线随之上移
- 锁定部分利润，同时保留盈利空间

### 挑战 2: 实现 VaR 计算

计算投资组合的 Value at Risk（风险价值）：
- 给定置信度下，组合的最大可能亏损
- 使用历史模拟法或蒙特卡洛模拟

### 挑战 3: 实现熔断机制

当检测到异常波动时，自动暂停交易：
- 价格波动超过 N 倍 ATR（Average True Range）
- 成交量异常
- 持仓盈亏异常波动

---

**下一步**: Lab 06 - 测试驱动开发实践 🧪

**提示**: 风险管理代码必须有高测试覆盖率（90%+），因为它是保护资金的最后防线！
