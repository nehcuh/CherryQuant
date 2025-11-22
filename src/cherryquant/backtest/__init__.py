"""
CherryQuant 回测系统

完整的回测引擎，支持：
1. 历史数据回放
2. 模拟订单执行
3. 性能指标计算
4. 回测报告生成

教学要点：
1. 事件驱动架构
2. 模拟交易环境
3. 性能评估方法
"""

from .engine import BacktestEngine, BacktestConfig
from .broker import SimulatedBroker, Order, Trade, Position, OrderType, OrderSide
from .data_replay import DataReplay
from .performance import PerformanceAnalyzer, PerformanceMetrics
from .report import BacktestReport, ReportGenerator

__all__ = [
    "BacktestEngine",
    "BacktestConfig",
    "SimulatedBroker",
    "Order",
    "Trade",
    "Position",
    "OrderType",
    "OrderSide",
    "DataReplay",
    "PerformanceAnalyzer",
    "PerformanceMetrics",
    "BacktestReport",
    "ReportGenerator",
]
