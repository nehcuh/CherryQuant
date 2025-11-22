# Lab 07: 回测系统实验

## 实验信息

- **难度**: ⭐⭐⭐⭐ 高级
- **预计时间**: 6 小时
- **相关模块**: Module 3 (AI 决策引擎), Module 4 (交易执行), Module 5 (依赖注入)
- **截止日期**: Week 9 结束

## 学习目标

完成本实验后，你将能够：

1. ✅ 理解回测系统的核心组件（数据回放、模拟执行、性能分析）
2. ✅ 实现历史数据回放引擎
3. ✅ 计算关键性能指标（Sharpe Ratio, Max Drawdown, Win Rate）
4. ✅ 分析回测结果并识别问题
5. ✅ 理解回测与实盘的差异（滑点、延迟、成本）
6. ✅ 生成专业的回测报告

## 实验前准备

### 前置实验

- [x] Lab 01-06: 所有前置实验

### 必备知识

- [ ] 期货交易基础
- [ ] 技术指标
- [ ] 基本统计学（均值、标准差、夏普比率）

### 参考资料

- 📖 `examples/backtesting/` (待创建)
- 📖 [Quantopian Lecture Series](https://www.quantopian.com/lectures)

---

## 实验背景

### 为什么需要回测？

> "没有经过回测的策略，就像没有经过测试的代码。" - Quantitative Trading Wisdom

**回测的目的：**
1. ✅ 验证策略的有效性
2. ✅ 评估风险收益特征
3. ✅ 发现策略弱点
4. ✅ 优化参数

**回测的局限性：**
- ⚠️ **过拟合风险** - 策略只在历史数据上表现好
- ⚠️ **前视偏差** - 使用了未来信息
- ⚠️ **幸存者偏差** - 只看存活的品种
- ⚠️ **市场环境变化** - 历史不代表未来

---

## 实验任务

### 任务 1: 构建回测引擎框架 (2 小时)

#### 1.1 设计回测引擎架构

创建 `src/cherryquant/backtest/backtest_engine.py`:

```python
"""
回测引擎

架构：
1. DataReplay - 数据回放
2. SimulatedBroker - 模拟经纪商
3. PerformanceAnalyzer - 性能分析
4. BacktestEngine - 主引擎（协调上述组件）

教学要点：
1. 事件驱动架构
2. 模拟交易环境
3. 性能指标计算
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"  # 市价单
    LIMIT = "limit"    # 限价单


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


@dataclass
class Order:
    """订单"""
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    price: Optional[float] = None  # 限价单需要
    timestamp: datetime = field(default_factory=datetime.now)
    order_id: str = ""


@dataclass
class Trade:
    """成交记录"""
    order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    commission: float
    timestamp: datetime


@dataclass
class Position:
    """持仓"""
    symbol: str
    quantity: int  # 正数=多头，负数=空头
    avg_price: float
    current_price: float

    @property
    def market_value(self) -> float:
        """市值"""
        return abs(self.quantity) * self.current_price

    @property
    def pnl(self) -> float:
        """浮动盈亏"""
        if self.quantity > 0:  # 多头
            return self.quantity * (self.current_price - self.avg_price)
        else:  # 空头
            return abs(self.quantity) * (self.avg_price - self.current_price)


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_capital: float = 1_000_000  # 初始资金
    commission_rate: float = 0.0003     # 手续费率
    slippage: float = 0.0001            # 滑点
    start_date: datetime = None
    end_date: datetime = None


class SimulatedBroker:
    """
    模拟经纪商

    功能：
    1. 订单撮合
    2. 持仓管理
    3. 资金管理
    """

    def __init__(self, config: BacktestConfig):
        self.config = config
        self.cash = config.initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.order_id_counter = 0

    def submit_order(self, order: Order, current_price: float) -> Optional[Trade]:
        """
        提交订单

        Args:
            order: 订单
            current_price: 当前市场价格

        Returns:
            成交记录（如果成交）
        """
        # 生成订单 ID
        self.order_id_counter += 1
        order.order_id = f"ORDER_{self.order_id_counter}"

        # 确定成交价格
        if order.order_type == OrderType.MARKET:
            # 市价单：考虑滑点
            if order.side == OrderSide.BUY:
                fill_price = current_price * (1 + self.config.slippage)
            else:
                fill_price = current_price * (1 - self.config.slippage)
        else:
            # 限价单：检查是否能成交
            if order.side == OrderSide.BUY and current_price <= order.price:
                fill_price = order.price
            elif order.side == OrderSide.SELL and current_price >= order.price:
                fill_price = order.price
            else:
                return None  # 限价单未成交

        # 计算手续费
        commission = fill_price * order.quantity * self.config.commission_rate

        # 检查资金是否充足
        if order.side == OrderSide.BUY:
            required_cash = fill_price * order.quantity + commission
            if required_cash > self.cash:
                raise ValueError(f"资金不足：需要 {required_cash}, 可用 {self.cash}")

        # 执行成交
        trade = Trade(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            commission=commission,
            timestamp=order.timestamp
        )

        # 更新持仓
        self._update_position(trade)

        # 更新资金
        if order.side == OrderSide.BUY:
            self.cash -= (fill_price * order.quantity + commission)
        else:
            self.cash += (fill_price * order.quantity - commission)

        # 记录成交
        self.trades.append(trade)

        return trade

    def _update_position(self, trade: Trade):
        """更新持仓"""
        symbol = trade.symbol

        if symbol not in self.positions:
            # 新建持仓
            quantity = trade.quantity if trade.side == OrderSide.BUY else -trade.quantity
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                avg_price=trade.price,
                current_price=trade.price
            )
        else:
            # 更新持仓
            pos = self.positions[symbol]
            if trade.side == OrderSide.BUY:
                new_quantity = pos.quantity + trade.quantity
                if pos.quantity >= 0:  # 多头加仓
                    pos.avg_price = (
                        (pos.avg_price * pos.quantity + trade.price * trade.quantity) /
                        new_quantity
                    )
                pos.quantity = new_quantity
            else:  # SELL
                new_quantity = pos.quantity - trade.quantity
                if pos.quantity <= 0:  # 空头加仓
                    pos.avg_price = (
                        (pos.avg_price * abs(pos.quantity) + trade.price * trade.quantity) /
                        abs(new_quantity)
                    )
                pos.quantity = new_quantity

            # 如果持仓归零，删除
            if pos.quantity == 0:
                del self.positions[symbol]

    def update_prices(self, prices: Dict[str, float]):
        """更新持仓的当前价格"""
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.current_price = prices[symbol]

    @property
    def total_value(self) -> float:
        """总资产"""
        return self.cash + sum(pos.market_value for pos in self.positions.values())

    @property
    def total_pnl(self) -> float:
        """总浮动盈亏"""
        return sum(pos.pnl for pos in self.positions.values())


class DataReplay:
    """
    数据回放器

    功能：
    1. 逐条回放历史数据
    2. 模拟实时数据流
    """

    def __init__(self, data: List[Dict]):
        """
        Args:
            data: 历史数据（按时间排序）
                  [{timestamp, symbol, open, high, low, close, volume}, ...]
        """
        self.data = data
        self.current_index = 0

    def has_next(self) -> bool:
        """是否还有数据"""
        return self.current_index < len(self.data)

    def next(self) -> Dict:
        """获取下一条数据"""
        if not self.has_next():
            raise StopIteration("No more data")

        bar = self.data[self.current_index]
        self.current_index += 1
        return bar

    def peek(self) -> Dict:
        """查看下一条数据（不移动指针）"""
        if not self.has_next():
            return None
        return self.data[self.current_index]


class PerformanceAnalyzer:
    """
    性能分析器

    计算：
    1. 总收益率
    2. 年化收益率
    3. 夏普比率
    4. 最大回撤
    5. 胜率
    """

    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.equity_curve: List[Dict] = []  # [{timestamp, equity}, ...]

    def record_equity(self, timestamp: datetime, equity: float):
        """记录权益"""
        self.equity_curve.append({
            "timestamp": timestamp,
            "equity": equity
        })

    def calculate_metrics(self) -> Dict:
        """计算性能指标"""
        if not self.equity_curve:
            return {}

        final_equity = self.equity_curve[-1]["equity"]
        total_return = (final_equity - self.initial_capital) / self.initial_capital

        # 计算日收益率序列
        daily_returns = []
        for i in range(1, len(self.equity_curve)):
            prev_equity = self.equity_curve[i-1]["equity"]
            curr_equity = self.equity_curve[i]["equity"]
            daily_return = (curr_equity - prev_equity) / prev_equity
            daily_returns.append(daily_return)

        # 年化收益率（假设 252 个交易日）
        days = len(self.equity_curve)
        years = days / 252
        annual_return = ((1 + total_return) ** (1 / years) - 1) if years > 0 else 0

        # 夏普比率（假设无风险利率 = 0）
        if daily_returns:
            import statistics
            mean_return = statistics.mean(daily_returns)
            std_return = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0
            sharpe_ratio = (mean_return / std_return * (252 ** 0.5)) if std_return > 0 else 0
        else:
            sharpe_ratio = 0

        # 最大回撤
        max_drawdown = self._calculate_max_drawdown()

        return {
            "total_return": total_return,
            "annual_return": annual_return,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "final_equity": final_equity,
            "total_trades": len(self.equity_curve)
        }

    def _calculate_max_drawdown(self) -> float:
        """计算最大回撤"""
        peak = self.initial_capital
        max_dd = 0

        for point in self.equity_curve:
            equity = point["equity"]
            if equity > peak:
                peak = equity

            drawdown = (peak - equity) / peak
            if drawdown > max_dd:
                max_dd = drawdown

        return max_dd


class BacktestEngine:
    """
    回测引擎主类

    协调所有组件，执行回测
    """

    def __init__(self, config: BacktestConfig):
        self.config = config
        self.broker = SimulatedBroker(config)
        self.analyzer = PerformanceAnalyzer(config.initial_capital)

    def run(self, data: List[Dict], strategy_func):
        """
        运行回测

        Args:
            data: 历史数据
            strategy_func: 策略函数 (bar, broker) -> List[Order]
        """
        replay = DataReplay(data)

        while replay.has_next():
            bar = replay.next()

            # 更新持仓价格
            self.broker.update_prices({bar["symbol"]: bar["close"]})

            # 执行策略
            orders = strategy_func(bar, self.broker)

            # 提交订单
            if orders:
                for order in orders:
                    try:
                        trade = self.broker.submit_order(order, bar["close"])
                        if trade:
                            print(f"成交: {trade}")
                    except ValueError as e:
                        print(f"订单失败: {e}")

            # 记录权益
            self.analyzer.record_equity(bar["timestamp"], self.broker.total_value)

        # 返回回测结果
        metrics = self.analyzer.calculate_metrics()
        metrics["trades"] = self.broker.trades

        return metrics
```

---

### 任务 2: 实现简单策略并回测 (2 小时)

#### 2.1 创建双均线策略

创建 `examples/backtesting/ma_crossover_strategy.py`:

```python
"""
双均线交叉策略

逻辑：
- 短期 MA 上穿长期 MA → 做多
- 短期 MA 下穿长期 MA → 平仓
"""
from src.cherryquant.backtest.backtest_engine import (
    BacktestEngine,
    BacktestConfig,
    Order,
    OrderType,
    OrderSide
)
from src.cherryquant.utils.indicators import calculate_ma
from datetime import datetime


def ma_crossover_strategy(bar, broker):
    """
    双均线策略函数

    Args:
        bar: 当前 K 线
        broker: 模拟经纪商

    Returns:
        订单列表
    """
    # 这里简化处理，实际需要维护价格历史
    # 为了演示，我们使用简单的规则

    symbol = bar["symbol"]
    current_price = bar["close"]

    # 检查是否有持仓
    has_position = symbol in broker.positions

    # 简单规则：价格上涨买入，下跌卖出（演示用）
    # 实际应该计算 MA
    if not has_position and current_price > bar["open"]:
        # 买入信号
        return [Order(
            symbol=symbol,
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET
        )]
    elif has_position and current_price < bar["open"]:
        # 卖出信号
        position = broker.positions[symbol]
        return [Order(
            symbol=symbol,
            side=OrderSide.SELL,
            quantity=position.quantity,
            order_type=OrderType.MARKET
        )]

    return []


def main():
    """运行回测"""
    # 模拟历史数据
    data = []
    base_price = 3500
    for i in range(100):
        # 生成随机价格走势
        price = base_price + (i % 20) * 10 - 100
        data.append({
            "timestamp": datetime(2024, 1, 1) + timedelta(days=i),
            "symbol": "rb2501",
            "open": price,
            "high": price + 10,
            "low": price - 10,
            "close": price + (5 if i % 2 == 0 else -5),
            "volume": 100000
        })

    # 配置回测
    config = BacktestConfig(
        initial_capital=1_000_000,
        commission_rate=0.0003,
        slippage=0.0001
    )

    # 创建引擎
    engine = BacktestEngine(config)

    # 运行回测
    results = engine.run(data, ma_crossover_strategy)

    # 打印结果
    print("=" * 60)
    print("回测结果")
    print("=" * 60)
    print(f"总收益率: {results['total_return']:.2%}")
    print(f"年化收益率: {results['annual_return']:.2%}")
    print(f"夏普比率: {results['sharpe_ratio']:.2f}")
    print(f"最大回撤: {results['max_drawdown']:.2%}")
    print(f"最终权益: {results['final_equity']:,.0f}")
    print(f"交易次数: {len(results['trades'])}")


if __name__ == "__main__":
    from datetime import timedelta
    main()
```

---

### 任务 3: 分析回测结果 (1 小时)

#### 3.1 生成权益曲线图

```python
import matplotlib.pyplot as plt


def plot_equity_curve(analyzer):
    """绘制权益曲线"""
    timestamps = [point["timestamp"] for point in analyzer.equity_curve]
    equities = [point["equity"] for point in analyzer.equity_curve]

    plt.figure(figsize=(12, 6))
    plt.plot(timestamps, equities, label="Equity")
    plt.axhline(y=analyzer.initial_capital, color='r', linestyle='--', label="Initial Capital")
    plt.xlabel("Date")
    plt.ylabel("Equity")
    plt.title("Equity Curve")
    plt.legend()
    plt.grid(True)
    plt.savefig("equity_curve.png")
    plt.show()
```

#### 3.2 分析交易记录

```python
def analyze_trades(trades):
    """分析交易记录"""
    if not trades:
        print("没有交易记录")
        return

    # 盈亏统计
    winning_trades = 0
    losing_trades = 0
    total_profit = 0
    total_loss = 0

    for i in range(0, len(trades), 2):
        if i + 1 >= len(trades):
            break

        # 假设成对交易（买入+卖出）
        buy_trade = trades[i]
        sell_trade = trades[i + 1]

        pnl = (sell_trade.price - buy_trade.price) * buy_trade.quantity
        pnl -= (buy_trade.commission + sell_trade.commission)

        if pnl > 0:
            winning_trades += 1
            total_profit += pnl
        else:
            losing_trades += 1
            total_loss += abs(pnl)

    total_trades = winning_trades + losing_trades
    win_rate = winning_trades / total_trades if total_trades > 0 else 0
    avg_win = total_profit / winning_trades if winning_trades > 0 else 0
    avg_loss = total_loss / losing_trades if losing_trades > 0 else 0
    profit_factor = total_profit / total_loss if total_loss > 0 else 0

    print("\n交易分析:")
    print(f"  总交易次数: {total_trades}")
    print(f"  盈利次数: {winning_trades}")
    print(f"  亏损次数: {losing_trades}")
    print(f"  胜率: {win_rate:.2%}")
    print(f"  平均盈利: {avg_win:,.0f}")
    print(f"  平均亏损: {avg_loss:,.0f}")
    print(f"  盈亏比: {avg_win/avg_loss:.2f}" if avg_loss > 0 else "  盈亏比: N/A")
    print(f"  利润因子: {profit_factor:.2f}")
```

---

### 任务 4: 识别回测陷阱 (1 小时)

#### 4.1 前视偏差检测

```python
def check_lookahead_bias(strategy_code: str):
    """
    检查策略代码是否存在前视偏差

    前视偏差示例：
    - 使用未来数据（如 tomorrow's close）
    - 使用整个数据集计算参数
    """
    warnings = []

    # 简单检查（实际应该用 AST 分析）
    if "future" in strategy_code.lower():
        warnings.append("可能存在前视偏差：使用了 'future' 关键字")

    if ".shift(-" in strategy_code:
        warnings.append("可能存在前视偏差：使用了负向位移")

    return warnings
```

#### 4.2 过拟合检测

```python
def check_overfitting(results_in_sample, results_out_sample):
    """
    检查过拟合

    方法：对比样本内和样本外表现
    """
    in_sample_return = results_in_sample["total_return"]
    out_sample_return = results_out_sample["total_return"]

    degradation = (in_sample_return - out_sample_return) / in_sample_return

    print(f"\n过拟合检查:")
    print(f"  样本内收益: {in_sample_return:.2%}")
    print(f"  样本外收益: {out_sample_return:.2%}")
    print(f"  性能衰减: {degradation:.2%}")

    if degradation > 0.5:
        print("  ⚠️  警告：样本外表现显著下降，可能存在过拟合！")
    elif degradation > 0.2:
        print("  ⚠️  注意：样本外表现有所下降")
    else:
        print("  ✅ 样本外表现良好")
```

---

## 实验总结

### 完成情况自查

- [ ] 实现了完整的回测引擎
- [ ] 回测了简单策略
- [ ] 计算了关键性能指标
- [ ] 识别了回测陷阱

### 关键收获

1. **回测不等于实盘** - 滑点、延迟、成本都会影响结果
2. **过拟合风险** - 样本外验证很重要
3. **性能指标** - Sharpe、MaxDD、Win Rate 等
4. **前视偏差** - 不能使用未来信息

---

**下一步**: Lab 08 - 完整系统集成与毕业项目 🎓
