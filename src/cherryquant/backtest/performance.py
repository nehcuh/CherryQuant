"""
性能分析器

计算回测性能指标：
1. 收益率指标（总收益、年化收益）
2. 风险指标（波动率、最大回撤）
3. 风险调整收益（Sharpe、Sortino、Calmar）
4. 交易统计（胜率、盈亏比）

教学要点：
1. 量化交易性能评估
2. 风险收益权衡
3. 统计分析
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
import statistics
import math

from cherryquant.constants import BacktestConstants


@dataclass
class PerformanceMetrics:
    """性能指标"""

    # 收益指标
    total_return: float  # 总收益率
    annual_return: float  # 年化收益率
    daily_return_mean: float  # 日均收益
    daily_return_std: float  # 日收益标准差

    # 风险指标
    max_drawdown: float  # 最大回撤
    max_drawdown_duration: int  # 最大回撤持续天数
    volatility: float  # 波动率（年化）

    # 风险调整收益
    sharpe_ratio: float  # 夏普比率
    sortino_ratio: float  # 索提诺比率
    calmar_ratio: float  # 卡尔玛比率

    # 交易统计
    total_trades: int  # 总交易次数
    winning_trades: int  # 盈利交易次数
    losing_trades: int  # 亏损交易次数
    win_rate: float  # 胜率
    avg_win: float  # 平均盈利
    avg_loss: float  # 平均亏损
    profit_factor: float  # 利润因子
    expectancy: float  # 期望值

    # 时间统计
    start_date: datetime
    end_date: datetime
    trading_days: int

    # 资金统计
    initial_capital: float
    final_capital: float
    peak_capital: float  # 最高资金
    min_capital: float  # 最低资金

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "total_return": f"{self.total_return:.2%}",
            "annual_return": f"{self.annual_return:.2%}",
            "max_drawdown": f"{self.max_drawdown:.2%}",
            "sharpe_ratio": f"{self.sharpe_ratio:.2f}",
            "sortino_ratio": f"{self.sortino_ratio:.2f}",
            "calmar_ratio": f"{self.calmar_ratio:.2f}",
            "win_rate": f"{self.win_rate:.2%}",
            "profit_factor": f"{self.profit_factor:.2f}",
            "total_trades": self.total_trades,
            "trading_days": self.trading_days,
        }


class PerformanceAnalyzer:
    """
    性能分析器

    教学要点：
    1. 时间序列分析
    2. 风险度量方法
    3. 统计指标计算
    """

    def __init__(
        self,
        initial_capital: float,
        risk_free_rate: float = BacktestConstants.RISK_FREE_RATE
    ):
        self.initial_capital = initial_capital
        self.risk_free_rate = risk_free_rate

        # 权益曲线
        self.equity_curve: list[dict] = []
        # [{timestamp: datetime, equity: float, drawdown: float}, ...]

        # 交易记录
        self.trades: list[dict] = []
        # [{entry_time, exit_time, pnl, pnl_pct, ...}, ...]

    def record_equity(self, timestamp: datetime, equity: float):
        """记录权益"""
        # 计算回撤
        if self.equity_curve:
            peak = max(point["equity"] for point in self.equity_curve)
            drawdown = (peak - equity) / peak if peak > 0 else 0.0
        else:
            drawdown = 0.0

        self.equity_curve.append({
            "timestamp": timestamp,
            "equity": equity,
            "drawdown": drawdown,
        })

    def record_trade(
        self,
        entry_time: datetime,
        exit_time: datetime,
        entry_price: float,
        exit_price: float,
        quantity: int,
        side: str,
        pnl: float,
    ):
        """记录交易"""
        pnl_pct = pnl / (entry_price * quantity) if entry_price > 0 else 0.0

        self.trades.append({
            "entry_time": entry_time,
            "exit_time": exit_time,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "quantity": quantity,
            "side": side,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "duration": (exit_time - entry_time).total_seconds() / 3600,  # 小时
        })

    def calculate_metrics(self) -> PerformanceMetrics:
        """计算性能指标"""
        if not self.equity_curve:
            raise ValueError("No equity data")

        # 基本信息
        start_date = self.equity_curve[0]["timestamp"]
        end_date = self.equity_curve[-1]["timestamp"]
        trading_days = len(self.equity_curve)
        final_capital = self.equity_curve[-1]["equity"]

        # 计算日收益率
        daily_returns = []
        for i in range(1, len(self.equity_curve)):
            prev_equity = self.equity_curve[i-1]["equity"]
            curr_equity = self.equity_curve[i]["equity"]
            daily_return = (curr_equity - prev_equity) / prev_equity if prev_equity > 0 else 0.0
            daily_returns.append(daily_return)

        # 收益指标
        total_return = (final_capital - self.initial_capital) / self.initial_capital

        years = trading_days / BacktestConstants.TRADING_DAYS_PER_YEAR
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0.0

        daily_return_mean = statistics.mean(daily_returns) if daily_returns else 0.0
        daily_return_std = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0.0

        # 风险指标
        max_drawdown, max_dd_duration = self._calculate_max_drawdown()
        volatility = daily_return_std * math.sqrt(BacktestConstants.TRADING_DAYS_PER_YEAR)

        # 风险调整收益
        sharpe_ratio = self._calculate_sharpe_ratio(daily_returns, daily_return_std)
        sortino_ratio = self._calculate_sortino_ratio(daily_returns)
        calmar_ratio = annual_return / max_drawdown if max_drawdown > 0 else 0.0

        # 交易统计
        trade_stats = self._calculate_trade_stats()

        # 资金统计
        peak_capital = max(point["equity"] for point in self.equity_curve)
        min_capital = min(point["equity"] for point in self.equity_curve)

        return PerformanceMetrics(
            total_return=total_return,
            annual_return=annual_return,
            daily_return_mean=daily_return_mean,
            daily_return_std=daily_return_std,
            max_drawdown=max_drawdown,
            max_drawdown_duration=max_dd_duration,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            total_trades=trade_stats["total_trades"],
            winning_trades=trade_stats["winning_trades"],
            losing_trades=trade_stats["losing_trades"],
            win_rate=trade_stats["win_rate"],
            avg_win=trade_stats["avg_win"],
            avg_loss=trade_stats["avg_loss"],
            profit_factor=trade_stats["profit_factor"],
            expectancy=trade_stats["expectancy"],
            start_date=start_date,
            end_date=end_date,
            trading_days=trading_days,
            initial_capital=self.initial_capital,
            final_capital=final_capital,
            peak_capital=peak_capital,
            min_capital=min_capital,
        )

    def _calculate_max_drawdown(self) -> tuple[float, int]:
        """计算最大回撤和持续时间"""
        if not self.equity_curve:
            return 0.0, 0

        peak = self.initial_capital
        max_dd = 0.0
        max_dd_duration = 0
        current_dd_duration = 0

        for point in self.equity_curve:
            equity = point["equity"]

            if equity > peak:
                peak = equity
                current_dd_duration = 0
            else:
                dd = (peak - equity) / peak
                if dd > max_dd:
                    max_dd = dd

                current_dd_duration += 1
                if current_dd_duration > max_dd_duration:
                    max_dd_duration = current_dd_duration

        return max_dd, max_dd_duration

    def _calculate_sharpe_ratio(
        self,
        daily_returns: list[float],
        std: float
    ) -> float:
        """计算夏普比率"""
        if not daily_returns or std == 0:
            return 0.0

        mean_return = statistics.mean(daily_returns)
        daily_rf = self.risk_free_rate / BacktestConstants.TRADING_DAYS_PER_YEAR

        excess_return = mean_return - daily_rf
        sharpe = (excess_return / std) * math.sqrt(BacktestConstants.TRADING_DAYS_PER_YEAR)

        return sharpe

    def _calculate_sortino_ratio(self, daily_returns: list[float]) -> float:
        """计算索提诺比率（只考虑下行风险）"""
        if not daily_returns:
            return 0.0

        mean_return = statistics.mean(daily_returns)
        daily_rf = self.risk_free_rate / BacktestConstants.TRADING_DAYS_PER_YEAR

        # 下行偏差（只考虑负收益）
        downside_returns = [r - daily_rf for r in daily_returns if r < daily_rf]

        if not downside_returns:
            return 0.0

        downside_std = math.sqrt(sum(r**2 for r in downside_returns) / len(downside_returns))

        if downside_std == 0:
            return 0.0

        sortino = (mean_return - daily_rf) / downside_std * math.sqrt(BacktestConstants.TRADING_DAYS_PER_YEAR)

        return sortino

    def _calculate_trade_stats(self) -> dict:
        """计算交易统计"""
        if not self.trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
            }

        winning_trades = [t for t in self.trades if t["pnl"] > 0]
        losing_trades = [t for t in self.trades if t["pnl"] < 0]

        total_trades = len(self.trades)
        num_wins = len(winning_trades)
        num_losses = len(losing_trades)

        win_rate = num_wins / total_trades if total_trades > 0 else 0.0

        avg_win = statistics.mean([t["pnl"] for t in winning_trades]) if winning_trades else 0.0
        avg_loss = abs(statistics.mean([t["pnl"] for t in losing_trades])) if losing_trades else 0.0

        total_profit = sum(t["pnl"] for t in winning_trades)
        total_loss = abs(sum(t["pnl"] for t in losing_trades))

        profit_factor = total_profit / total_loss if total_loss > 0 else 0.0

        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

        return {
            "total_trades": total_trades,
            "winning_trades": num_wins,
            "losing_trades": num_losses,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "expectancy": expectancy,
        }

    def get_equity_curve_df(self):
        """获取权益曲线DataFrame（需要pandas）"""
        try:
            import pandas as pd
            return pd.DataFrame(self.equity_curve)
        except ImportError:
            return self.equity_curve

    def get_trades_df(self):
        """获取交易记录DataFrame（需要pandas）"""
        try:
            import pandas as pd
            return pd.DataFrame(self.trades)
        except ImportError:
            return self.trades
