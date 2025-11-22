"""
回测系统集成测试

验证回测引擎能够真实运行
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest
from datetime import datetime, timedelta
from cherryquant.backtest import (
    BacktestEngine,
    BacktestConfig,
    Order,
    OrderType,
    OrderSide,
)


def test_backtest_engine_simple_strategy():
    """测试回测引擎能够运行简单策略"""

    # 准备测试数据
    start_date = datetime(2024, 1, 1)
    data = []

    for i in range(100):
        data.append({
            "timestamp": start_date + timedelta(days=i),
            "symbol": "rb2501",
            "open": 4000.0 + i,
            "high": 4010.0 + i,
            "low": 3990.0 + i,
            "close": 4005.0 + i,
            "volume": 10000,
        })

    # 简单策略：买入持有
    bought = [False]  # 使用列表来保持状态

    def buy_and_hold_strategy(bar, broker):
        """简单的买入持有策略"""
        if not bought[0]:
            # 第一天买入
            order = Order(
                symbol=bar["symbol"],
                side=OrderSide.BUY,
                quantity=10,
                order_type=OrderType.MARKET,
            )
            bought[0] = True
            return [order]
        return None

    # 创建回测引擎
    config = BacktestConfig(
        initial_capital=1_000_000,
        commission_rate=0.0003,
        slippage=0.0001,
    )

    engine = BacktestEngine(config)

    # 运行回测
    metrics = engine.run(data, buy_and_hold_strategy, verbose=True)

    # 验证结果
    print(f"\n✅ Metrics: total_trades={metrics.total_trades}, final_capital={metrics.final_capital}")
    assert metrics is not None, "Metrics should not be None"
    assert metrics.initial_capital == 1_000_000, "Initial capital should be 1M"
    assert metrics.final_capital > 0, "Final capital should be positive"
    # 回测系统成功运行！
    print("✅ 回测系统成功运行！")


def test_backtest_engine_can_import():
    """验证回测模块可以正常导入"""
    from cherryquant.backtest import (
        BacktestEngine,
        BacktestConfig,
        SimulatedBroker,
        Order,
        Trade,
        Position,
        OrderType,
        OrderSide,
        DataReplay,
        PerformanceAnalyzer,
        PerformanceMetrics,
    )

    assert BacktestEngine is not None
    assert BacktestConfig is not None
    assert SimulatedBroker is not None


if __name__ == "__main__":
    test_backtest_engine_simple_strategy()
    test_backtest_engine_can_import()
    print("✅ 回测系统集成测试通过")
