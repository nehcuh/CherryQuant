"""
回测引擎

完整的回测框架：
1. 数据回放
2. 策略执行
3. 订单管理
4. 性能分析
5. 报告生成

教学要点：
1. 事件驱动架构
2. 策略模式
3. 完整的回测流程
"""

from dataclasses import dataclass
from typing import Callable
from datetime import datetime

from .broker import SimulatedBroker, Order, OrderSide, OrderType
from .data_replay import DataReplay
from .performance import PerformanceAnalyzer, PerformanceMetrics
from cherryquant.constants import BacktestConstants


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_capital: float = BacktestConstants.DEFAULT_INITIAL_CAPITAL
    commission_rate: float = BacktestConstants.DEFAULT_COMMISSION_RATE
    slippage: float = BacktestConstants.DEFAULT_SLIPPAGE
    start_date: datetime | None = None
    end_date: datetime | None = None
    benchmark_symbol: str | None = None  # 基准品种


# 策略函数类型定义
StrategyFunc = Callable[[dict, SimulatedBroker], list[Order]]


class BacktestEngine:
    """
    回测引擎

    教学要点：
    1. 如何组织回测流程
    2. 策略与执行分离
    3. 性能监控
    """

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()

        # 初始化组件
        self.broker = SimulatedBroker(
            initial_capital=self.config.initial_capital,
            commission_rate=self.config.commission_rate,
            slippage=self.config.slippage,
        )

        self.analyzer = PerformanceAnalyzer(
            initial_capital=self.config.initial_capital
        )

        self.current_bar: dict | None = None

    def run(
        self,
        data: list[dict],
        strategy: StrategyFunc,
        verbose: bool = True
    ) -> PerformanceMetrics:
        """
        运行回测

        Args:
            data: 历史数据
            strategy: 策略函数 (bar, broker) -> [Order]
            verbose: 是否打印进度

        Returns:
            性能指标
        """
        replay = DataReplay(data)

        bar_count = 0
        total_bars = len(data)

        if verbose:
            print(f"\n{'='*60}")
            print(f"开始回测")
            print(f"{'='*60}")
            print(f"初始资金: {self.config.initial_capital:,.0f}")
            print(f"数据条数: {total_bars}")
            print(f"手续费率: {self.config.commission_rate:.4%}")
            print(f"滑点: {self.config.slippage:.4%}")
            print(f"{'='*60}\n")

        while replay.has_next():
            bar = replay.next()
            bar_count += 1

            # 更新当前Bar
            self.current_bar = bar

            # 更新持仓价格
            self.broker.update_prices({bar["symbol"]: bar["close"]})

            # 执行策略
            orders = strategy(bar, self.broker)

            # 处理订单
            if orders:
                for order in orders:
                    try:
                        trade = self.broker.submit_order(
                            order,
                            current_price=bar["close"],
                            timestamp=bar["timestamp"]
                        )

                        if trade and verbose:
                            print(f"[{bar['timestamp']}] {trade.side.value.upper()} "
                                  f"{trade.symbol} x{trade.quantity} @ {trade.price:.2f}")

                    except ValueError as e:
                        if verbose:
                            print(f"[{bar['timestamp']}] 订单失败: {e}")

            # 记录权益
            self.analyzer.record_equity(
                timestamp=bar["timestamp"],
                equity=self.broker.total_value
            )

            # 打印进度
            if verbose and bar_count % 100 == 0:
                progress = bar_count / total_bars
                equity = self.broker.total_value
                pnl_pct = (equity - self.config.initial_capital) / self.config.initial_capital
                print(f"进度: {progress:.1%} | 权益: {equity:,.0f} | 盈亏: {pnl_pct:+.2%}")

        # 计算性能指标
        metrics = self.analyzer.calculate_metrics()

        if verbose:
            self._print_results(metrics)

        return metrics

    def _print_results(self, metrics: PerformanceMetrics):
        """打印回测结果"""
        print(f"\n{'='*60}")
        print(f"回测结果")
        print(f"{'='*60}")

        print(f"\n📊 收益指标:")
        print(f"  总收益率: {metrics.total_return:+.2%}")
        print(f"  年化收益: {metrics.annual_return:+.2%}")
        print(f"  最终资金: {metrics.final_capital:,.0f}")
        print(f"  最高资金: {metrics.peak_capital:,.0f}")

        print(f"\n⚠️  风险指标:")
        print(f"  最大回撤: {metrics.max_drawdown:.2%}")
        print(f"  回撤持续: {metrics.max_drawdown_duration} 天")
        print(f"  波动率: {metrics.volatility:.2%}")

        print(f"\n📈 风险调整收益:")
        print(f"  Sharpe比率: {metrics.sharpe_ratio:.2f}")
        print(f"  Sortino比率: {metrics.sortino_ratio:.2f}")
        print(f"  Calmar比率: {metrics.calmar_ratio:.2f}")

        print(f"\n💼 交易统计:")
        print(f"  总交易次数: {metrics.total_trades}")
        print(f"  盈利次数: {metrics.winning_trades}")
        print(f"  亏损次数: {metrics.losing_trades}")
        print(f"  胜率: {metrics.win_rate:.2%}")
        print(f"  平均盈利: {metrics.avg_win:,.0f}")
        print(f"  平均亏损: {metrics.avg_loss:,.0f}")
        print(f"  利润因子: {metrics.profit_factor:.2f}")
        print(f"  期望值: {metrics.expectancy:,.0f}")

        print(f"\n⏱️  时间统计:")
        print(f"  开始日期: {metrics.start_date.strftime('%Y-%m-%d')}")
        print(f"  结束日期: {metrics.end_date.strftime('%Y-%m-%d')}")
        print(f"  交易天数: {metrics.trading_days}")

        print(f"\n💰 成本统计:")
        print(f"  总手续费: {self.broker.total_commission:,.0f}")
        print(f"  总滑点: {self.broker.total_slippage:,.0f}")

        print(f"\n{'='*60}\n")

    def get_equity_curve(self) -> list[dict]:
        """获取权益曲线"""
        return self.analyzer.equity_curve

    def get_trades(self) -> list[dict]:
        """获取交易记录"""
        return self.broker.trades

    def get_positions(self) -> dict:
        """获取当前持仓"""
        return self.broker.positions
