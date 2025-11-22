#!/usr/bin/env python3
"""
完整回测系统示例

难度：⭐⭐⭐⭐ 高级

功能：完整的策略回测演示
- 历史数据回放
- 模拟订单执行
- 性能指标计算
- 回测报告生成

学习要点：
1. 事件驱动回测架构
2. 模拟交易环境
3. 性能评估方法
4. 风险指标计算

运行方式：
    uv run python examples/complete_system/backtest_demo.py
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cherryquant.backtest.engine import BacktestEngine, BacktestConfig
from cherryquant.backtest.broker import SimulatedBroker, Order, OrderType, OrderSide
from cherryquant.backtest.performance import PerformanceAnalyzer
from cherryquant.backtest.report import BacktestReport, ReportGenerator
from cherryquant.constants import BacktestConstants


# ==================== 简单均线策略 ====================

class SimpleMAStrategy:
    """简单的双均线交易策略"""

    def __init__(self, short_period: int = 5, long_period: int = 20):
        self.short_period = short_period
        self.long_period = long_period
        self.position = 0  # 当前持仓：1(多头), -1(空头), 0(空仓)

    def on_bar(self, bar: dict, broker: SimulatedBroker) -> None:
        """K线数据回调"""

        # 简化：假设我们有MA5和MA20数据
        # 实际应该从历史bar计算
        ma5 = bar.get("ma5", bar["close"])
        ma20 = bar.get("ma20", bar["close"])

        # 金叉：买入信号
        if ma5 > ma20 and self.position <= 0:
            if self.position < 0:
                # 平空
                order = Order(
                    symbol=bar["symbol"],
                    side=OrderSide.BUY,
                    quantity=1,
                    order_type=OrderType.MARKET,
                )
                broker.submit_order(order, bar["close"], bar["datetime"])
            # 开多
            order = Order(
                symbol=bar["symbol"],
                side=OrderSide.BUY,
                quantity=1,
                order_type=OrderType.MARKET,
            )
            broker.submit_order(order, bar["close"], bar["datetime"])
            self.position = 1

        # 死叉：卖出信号
        elif ma5 < ma20 and self.position >= 0:
            if self.position > 0:
                # 平多
                order = Order(
                    symbol=bar["symbol"],
                    side=OrderSide.SELL,
                    quantity=1,
                    order_type=OrderType.MARKET,
                )
                broker.submit_order(order, bar["close"], bar["datetime"])
            # 开空
            order = Order(
                symbol=bar["symbol"],
                side=OrderSide.SELL,
                quantity=1,
                order_type=OrderType.MARKET,
            )
            broker.submit_order(order, bar["close"], bar["datetime"])
            self.position = -1


# ==================== 模拟数据生成器 ====================

def generate_mock_data(symbol: str, days: int = 60):
    """生成模拟历史K线数据"""
    import random

    data = []
    base_price = 3500.0
    current_date = datetime.now() - timedelta(days=days)

    for i in range(days):
        # 添加趋势和随机波动
        trend = 0.2 if i > days // 2 else -0.1
        price = base_price + trend * i + random.uniform(-30, 30)

        # 计算MA
        ma5 = price + random.uniform(-10, 10)
        ma20 = price + random.uniform(-20, 20)

        bar = {
            "symbol": symbol,
            "datetime": current_date + timedelta(days=i),
            "open": price + random.uniform(-5, 5),
            "high": price + random.uniform(0, 15),
            "low": price - random.uniform(0, 15),
            "close": price,
            "volume": random.randint(50000, 150000),
            "ma5": ma5,
            "ma20": ma20,
        }
        data.append(bar)

    return data


# ==================== 主要示例 ====================

async def example_1_basic_backtest():
    """示例1：基础回测"""
    print("\n" + "=" * 60)
    print("示例 1: 基础双均线策略回测")
    print("=" * 60 + "\n")

    # 1. 配置回测参数
    config = BacktestConfig(
        start_date=datetime.now() - timedelta(days=60),
        end_date=datetime.now(),
        initial_capital=BacktestConstants.DEFAULT_INITIAL_CAPITAL,
        commission_rate=BacktestConstants.DEFAULT_COMMISSION_RATE,
        slippage=BacktestConstants.DEFAULT_SLIPPAGE,
    )

    print(f"📊 回测配置:")
    print(f"  初始资金: ¥{config.initial_capital:,.0f}")
    print(f"  回测周期: {config.start_date.date()} 至 {config.end_date.date()}")
    print(f"  手续费率: {config.commission_rate:.2%}")
    print(f"  滑点: {config.slippage:.2%}\n")

    # 2. 生成模拟数据
    symbol = "rb2501"
    historical_data = generate_mock_data(symbol, days=60)

    print(f"✅ 生成历史数据: {len(historical_data)} 根K线\n")

    # 3. 创建回测引擎
    broker = SimulatedBroker(
        initial_capital=config.initial_capital,
        commission_rate=config.commission_rate,
        slippage=config.slippage,
    )

    strategy = SimpleMAStrategy(short_period=5, long_period=20)

    print("🤖 开始回测...\n")

    # 4. 运行回测
    for i, bar in enumerate(historical_data):
        # 更新市场价格
        broker.update_prices({bar["symbol"]: bar["close"]})

        # 策略决策
        strategy.on_bar(bar, broker)

        # 显示进度
        if (i + 1) % 20 == 0:
            print(f"  进度: {i + 1}/{len(historical_data)} ({(i + 1) / len(historical_data) * 100:.0f}%)")

    print("\n✅ 回测完成\n")

    # 5. 计算性能指标
    print("📈 性能分析:")

    trades = broker.trades
    final_value = broker.get_total_value()
    print(f"  总交易次数: {len(trades)}")
    print(f"  最终资金: ¥{final_value:,.2f}")
    print(f"  总收益: ¥{final_value - config.initial_capital:+,.2f}")
    print(f"  收益率: {(final_value / config.initial_capital - 1) * 100:+.2f}%")

    # 显示部分交易
    if trades:
        print(f"\n  前3笔交易:")
        for i, trade in enumerate(trades[:3]):
            print(f"    [{i + 1}] {trade.timestamp.date()} {trade.side.value} {trade.symbol} @ ¥{trade.price:.2f}")

    print("\n✅ 示例1完成")


async def example_2_performance_metrics():
    """示例2：详细性能指标"""
    print("\n" + "=" * 60)
    print("示例 2: 详细性能指标计算")
    print("=" * 60 + "\n")

    # 运行回测
    config = BacktestConfig(
        start_date=datetime.now() - timedelta(days=90),
        end_date=datetime.now(),
        initial_capital=1_000_000,
    )

    broker = SimulatedBroker(initial_capital=config.initial_capital)
    strategy = SimpleMAStrategy()
    analyzer = PerformanceAnalyzer(initial_capital=config.initial_capital)

    symbol = "rb2501"
    historical_data = generate_mock_data(symbol, days=90)

    print(f"📊 回测 {len(historical_data)} 天数据...\n")

    for bar in historical_data:
        broker.update_prices({bar["symbol"]: bar["close"]})
        strategy.on_bar(bar, broker)

        # 记录权益曲线
        analyzer.record_equity(
            timestamp=bar["datetime"],
            equity=broker.get_total_value()
        )

    metrics = analyzer.calculate_metrics()

    print("📊 详细性能指标:\n")
    print(f"  总收益率: {metrics.total_return * 100:+.2f}%")
    print(f"  年化收益率: {metrics.annual_return * 100:+.2f}%")
    print(f"  最大回撤: {metrics.max_drawdown * 100:.2f}%")
    print(f"  夏普比率: {metrics.sharpe_ratio:.2f}")
    print(f"  胜率: {metrics.win_rate * 100:.1f}%")
    print(f"  利润因子: {metrics.profit_factor:.2f}")
    print(f"  总交易次数: {metrics.total_trades}")
    print(f"  盈利交易: {metrics.winning_trades}")
    print(f"  亏损交易: {metrics.losing_trades}")

    print("\n✅ 示例2完成")


async def example_3_generate_report():
    """示例3：生成回测报告"""
    print("\n" + "=" * 60)
    print("示例 3: 生成完整回测报告")
    print("=" * 60 + "\n")

    # 运行回测
    config = BacktestConfig(initial_capital=1_000_000)
    broker = SimulatedBroker(initial_capital=config.initial_capital)
    strategy = SimpleMAStrategy()
    analyzer = PerformanceAnalyzer(initial_capital=config.initial_capital)

    symbol = "rb2501"
    historical_data = generate_mock_data(symbol, days=60)

    for bar in historical_data:
        broker.update_prices({bar["symbol"]: bar["close"]})
        strategy.on_bar(bar, broker)

        # 记录权益曲线
        analyzer.record_equity(
            timestamp=bar["datetime"],
            equity=broker.get_total_value()
        )
    metrics = analyzer.calculate_metrics()

    # 生成报告
    report = BacktestReport(
        metrics=metrics,
        strategy_name="双均线策略 (MA5/MA20)",
        description="基于5日和20日均线金叉死叉的简单策略"
    )
    generator = ReportGenerator(report=report)

    print("📝 生成Markdown报告...\n")

    markdown_report = generator.generate_markdown()

    # 显示报告的前几行
    lines = markdown_report.split("\n")
    print("报告预览（前30行）:")
    print("=" * 60)
    for line in lines[:30]:
        print(line)
    print("...")
    print("=" * 60)

    # 保存报告
    output_path = Path("backtest_report.md")
    generator.save_to_file(output_path, format="markdown")

    print(f"\n✅ 完整报告已保存: {output_path.absolute()}")
    print("\n💡 提示: 使用Markdown阅读器查看完整报告")

    print("\n✅ 示例3完成")


async def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("🍒 CherryQuant 完整回测系统演示")
    print("=" * 70)

    print("\n💡 本示例演示完整的策略回测流程:")
    print("   数据回放 → 策略执行 → 订单模拟 → 性能分析 → 报告生成\n")

    try:
        await example_1_basic_backtest()
        await example_2_performance_metrics()
        await example_3_generate_report()

        print("\n" + "=" * 70)
        print("✅ 所有示例运行完成！")
        print("=" * 70)

        print("\n💡 回测系统使用提示:")
        print("  1. 使用真实历史数据进行回测（连接Tushare/MongoDB）")
        print("  2. 调整策略参数进行优化")
        print("  3. 注意过拟合风险（样本外测试）")
        print("  4. 考虑交易成本（手续费+滑点）")
        print("  5. 回测表现不等于实盘表现")
        print()

        print("📚 延伸阅读:")
        print("  - docs/course/06_Testing_Strategies.md")
        print("  - src/cherryquant/backtest/ 源码")
        print()

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n\n❌ 错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
