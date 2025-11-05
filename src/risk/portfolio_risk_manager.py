"""
组合级风险管理系统
实现跨策略的风险监控、控制和管理
"""

import asyncio
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RiskEventType(Enum):
    """风险事件类型"""
    CAPITAL_USAGE_EXCEEDED = "capital_usage_exceeded"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    MAX_DRAWDOWN = "max_drawdown"
    CORRELATION_RISK = "correlation_risk"
    SECTOR_CONCENTRATION = "sector_concentration"
    LIQUIDITY_RISK = "liquidity_risk"
    VOLATILITY_SPIKE = "volatility_spike"
    POSITION_LIMIT = "position_limit"

@dataclass
class RiskMetrics:
    """风险指标"""
    total_exposure: float
    capital_usage: float
    daily_pnl: float
    max_drawdown: float
    var_95: float  # 95% VaR
    var_99: float  # 99% VaR
    sharpe_ratio: float
    sortino_ratio: float
    beta: float
    correlation_matrix: Dict[str, float]
    sector_concentration: Dict[str, float]
    liquidity_score: float
    leverage_ratio: float

@dataclass
class RiskEvent:
    """风险事件"""
    event_id: str
    event_type: RiskEventType
    severity: RiskLevel
    timestamp: datetime
    strategy_id: Optional[str]
    description: str
    current_value: float
    threshold_value: float
    action_taken: str
    additional_data: Dict[str, Any]

class PortfolioRiskManager:
    """组合风险管理器"""

    def __init__(
        self,
        max_capital_usage: float = 0.8,
        max_daily_loss: float = 0.05,
        max_drawdown: float = 0.15,
        max_correlation: float = 0.7,
        max_sector_concentration: float = 0.4,
        var_confidence: float = 0.95,
        lookback_days: int = 252
    ):
        """初始化组合风险管理器

        Args:
            max_capital_usage: 最大资金使用率
            max_daily_loss: 最大每日亏损比例
            max_drawdown: 最大回撤比例
            max_correlation: 最大相关性
            max_sector_concentration: 最大板块集中度
            var_confidence: VaR置信度
            lookback_days: 历史数据回看天数
        """
        self.max_capital_usage = max_capital_usage
        self.max_daily_loss = max_daily_loss
        self.max_drawdown = max_drawdown
        self.max_correlation = max_correlation
        self.max_sector_concentration = max_sector_concentration
        self.var_confidence = var_confidence
        self.lookback_days = lookback_days

        # 风险事件记录
        self.risk_events: List[RiskEvent] = []

        # 历史数据
        self.portfolio_history: List[Dict[str, Any]] = []
        self.strategy_returns: Dict[str, List[float]] = {}
        self.benchmark_returns: List[float] = []

        # 风险监控任务
        self.monitor_task: Optional[asyncio.Task] = None
        self.is_monitoring = False

        # 回调函数
        self.risk_callbacks: List[callable] = []

        logger.info("组合风险管理器初始化完成")

    async def start_monitoring(self) -> None:
        """启动风险监控"""
        if self.is_monitoring:
            return

        self.is_monitoring = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("风险监控已启动")

    async def stop_monitoring(self) -> None:
        """停止风险监控"""
        self.is_monitoring = False

        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("风险监控已停止")

    async def evaluate_portfolio_risk(
        self,
        portfolio_data: Dict[str, Any],
        strategies_data: Dict[str, Dict[str, Any]]
    ) -> RiskMetrics:
        """评估组合风险

        Args:
            portfolio_data: 组合数据
            strategies_data: 策略数据

        Returns:
            风险指标
        """
        try:
            # 基础指标计算
            total_exposure = self._calculate_total_exposure(portfolio_data, strategies_data)
            capital_usage = portfolio_data.get('capital_usage', 0)
            daily_pnl = portfolio_data.get('daily_pnl', 0)
            max_drawdown = portfolio_data.get('max_drawdown', 0)

            # 计算VaR
            returns = self._calculate_portfolio_returns(portfolio_data, strategies_data)
            var_95, var_99 = self._calculate_var(returns)

            # 计算夏普比率和索提诺比率
            sharpe_ratio = self._calculate_sharpe_ratio(returns)
            sortino_ratio = self._calculate_sortino_ratio(returns)

            # 计算Beta
            beta = self._calculate_beta(returns)

            # 相关性矩阵
            correlation_matrix = self._calculate_correlation_matrix(strategies_data)

            # 板块集中度
            sector_concentration = self._calculate_sector_concentration(strategies_data)

            # 流动性评分
            liquidity_score = self._calculate_liquidity_score(strategies_data)

            # 杠杆比率
            leverage_ratio = total_exposure / portfolio_data.get('total_initial_capital', 1)

            risk_metrics = RiskMetrics(
                total_exposure=total_exposure,
                capital_usage=capital_usage,
                daily_pnl=daily_pnl,
                max_drawdown=max_drawdown,
                var_95=var_95,
                var_99=var_99,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                beta=beta,
                correlation_matrix=correlation_matrix,
                sector_concentration=sector_concentration,
                liquidity_score=liquidity_score,
                leverage_ratio=leverage_ratio
            )

            # 检查风险限制
            await self._check_risk_limits(risk_metrics, portfolio_data, strategies_data)

            return risk_metrics

        except Exception as e:
            logger.error(f"评估组合风险失败: {e}")
            raise

    def _calculate_total_exposure(
        self,
        portfolio_data: Dict[str, Any],
        strategies_data: Dict[str, Dict[str, Any]]
    ) -> float:
        """计算总敞口"""
        total_exposure = 0.0

        for strategy_id, strategy_data in strategies_data.items():
            positions = strategy_data.get('positions', [])
            for position in positions:
                exposure = position.get('quantity', 0) * position.get('current_price', 0)
                total_exposure += abs(exposure)

        return total_exposure

    def _calculate_portfolio_returns(
        self,
        portfolio_data: Dict[str, Any],
        strategies_data: Dict[str, Dict[str, Any]]
    ) -> List[float]:
        """计算组合收益率"""
        # 这里应该从历史数据中计算
        # 简化实现，返回模拟数据
        returns = portfolio_data.get('historical_returns', [])
        if not returns:
            # 生成模拟收益率数据
            np.random.seed(42)
            returns = np.random.normal(0.001, 0.02, 100).tolist()

        return returns

    def _calculate_var(self, returns: List[float]) -> Tuple[float, float]:
        """计算VaR"""
        if not returns:
            return 0.0, 0.0

        returns_array = np.array(returns)
        var_95 = np.percentile(returns_array, (1 - 0.95) * 100)
        var_99 = np.percentile(returns_array, (1 - 0.99) * 100)

        return abs(var_95), abs(var_99)

    def _calculate_sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.03) -> float:
        """计算夏普比率"""
        if not returns or len(returns) < 2:
            return 0.0

        returns_array = np.array(returns)
        excess_returns = returns_array - risk_free_rate / 252  # 日化无风险利率

        if np.std(excess_returns) == 0:
            return 0.0

        sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
        return sharpe

    def _calculate_sortino_ratio(self, returns: List[float], risk_free_rate: float = 0.03) -> float:
        """计算索提诺比率"""
        if not returns or len(returns) < 2:
            return 0.0

        returns_array = np.array(returns)
        excess_returns = returns_array - risk_free_rate / 252

        # 只计算负收益的标准差
        negative_returns = excess_returns[excess_returns < 0]
        if len(negative_returns) == 0 or np.std(negative_returns) == 0:
            return 0.0

        downside_deviation = np.std(negative_returns)
        sortino = np.mean(excess_returns) / downside_deviation * np.sqrt(252)
        return sortino

    def _calculate_beta(self, returns: List[float]) -> float:
        """计算Beta系数"""
        if not returns or not self.benchmark_returns:
            return 1.0

        if len(returns) != len(self.benchmark_returns):
            return 1.0

        portfolio_returns = np.array(returns)
        benchmark_returns = np.array(self.benchmark_returns)

        if np.var(benchmark_returns) == 0:
            return 1.0

        covariance = np.cov(portfolio_returns, benchmark_returns)[0][1]
        beta = covariance / np.var(benchmark_returns)

        return beta

    def _calculate_correlation_matrix(
        self,
        strategies_data: Dict[str, Dict[str, Any]]
    ) -> Dict[str, float]:
        """计算策略相关性矩阵"""
        correlation_matrix = {}
        strategy_ids = list(strategies_data.keys())

        for i, strategy1 in enumerate(strategy_ids):
            for j, strategy2 in enumerate(strategy_ids):
                if i < j:
                    # 获取策略收益率数据
                    returns1 = self.strategy_returns.get(strategy1, [])
                    returns2 = self.strategy_returns.get(strategy2, [])

                    if len(returns1) > 10 and len(returns2) > 10:
                        correlation = np.corrcoef(returns1[-min(len(returns1), len(returns2)):],
                                                returns2[-min(len(returns1), len(returns2)):])[0][1]
                        correlation_matrix[f"{strategy1}_{strategy2}"] = correlation

        return correlation_matrix

    def _calculate_sector_concentration(
        self,
        strategies_data: Dict[str, Dict[str, Any]]
    ) -> Dict[str, float]:
        """计算板块集中度"""
        sector_exposure = {}
        total_exposure = 0.0

        for strategy_id, strategy_data in strategies_data.items():
            positions = strategy_data.get('positions', [])
            for position in positions:
                symbol = position.get('symbol', '')
                sector = self._get_symbol_sector(symbol)
                exposure = abs(position.get('quantity', 0) * position.get('current_price', 0))

                sector_exposure[sector] = sector_exposure.get(sector, 0) + exposure
                total_exposure += exposure

        # 计算集中度
        sector_concentration = {}
        if total_exposure > 0:
            for sector, exposure in sector_exposure.items():
                sector_concentration[sector] = exposure / total_exposure

        return sector_concentration

    def _get_symbol_sector(self, symbol: str) -> str:
        """获取品种所属板块"""
        sector_mapping = {
            "rb": "黑色金属", "i": "黑色金属", "j": "黑色金属", "jm": "黑色金属",
            "cu": "有色金属", "al": "有色金属", "zn": "有色金属", "ni": "有色金属",
            "au": "贵金属", "ag": "贵金属",
            "a": "农产品", "m": "农产品", "c": "农产品", "y": "农产品",
        }

        commodity = symbol[:2].lower()
        return sector_mapping.get(commodity, "其他")

    def _calculate_liquidity_score(
        self,
        strategies_data: Dict[str, Dict[str, Any]]
    ) -> float:
        """计算流动性评分"""
        total_score = 0.0
        total_weight = 0.0

        for strategy_id, strategy_data in strategies_data.items():
            positions = strategy_data.get('positions', [])
            for position in positions:
                symbol = position.get('symbol', '')
                volume = position.get('volume', 0)
                price = position.get('current_price', 0)

                # 简化的流动性评分
                if volume > 10000:  # 高流动性
                    score = 1.0
                elif volume > 1000:  # 中等流动性
                    score = 0.7
                else:  # 低流动性
                    score = 0.3

                weight = abs(position.get('quantity', 0) * price)
                total_score += score * weight
                total_weight += weight

        return total_score / total_weight if total_weight > 0 else 0.5

    async def _check_risk_limits(
        self,
        risk_metrics: RiskMetrics,
        portfolio_data: Dict[str, Any],
        strategies_data: Dict[str, Dict[str, Any]]
    ) -> None:
        """检查风险限制"""
        # 资金使用率检查
        if risk_metrics.capital_usage > self.max_capital_usage:
            await self._create_risk_event(
                RiskEventType.CAPITAL_USAGE_EXCEEDED,
                RiskLevel.HIGH,
                f"资金使用率 {risk_metrics.capital_usage:.2%} 超过限制 {self.max_capital_usage:.2%}",
                risk_metrics.capital_usage,
                self.max_capital_usage,
                "暂停高杠杆策略"
            )

        # 每日亏损检查
        if abs(risk_metrics.daily_pnl) > self.max_daily_loss:
            await self._create_risk_event(
                RiskEventType.DAILY_LOSS_LIMIT,
                RiskLevel.CRITICAL,
                f"每日亏损 {abs(risk_metrics.daily_pnl):.2%} 超过限制 {self.max_daily_loss:.2%}",
                abs(risk_metrics.daily_pnl),
                self.max_daily_loss,
                "暂停所有交易"
            )

        # 最大回撤检查
        if risk_metrics.max_drawdown > self.max_drawdown:
            await self._create_risk_event(
                RiskEventType.MAX_DRAWDOWN,
                RiskLevel.HIGH,
                f"最大回撤 {risk_metrics.max_drawdown:.2%} 超过限制 {self.max_drawdown:.2%}",
                risk_metrics.max_drawdown,
                self.max_drawdown,
                "降低仓位规模"
            )

        # 相关性风险检查
        high_correlations = [
            pair for pair, corr in risk_metrics.correlation_matrix.items()
            if abs(corr) > self.max_correlation
        ]
        if high_correlations:
            await self._create_risk_event(
                RiskEventType.CORRELATION_RISK,
                RiskLevel.MEDIUM,
                f"高相关性策略: {', '.join(high_correlations)}",
                max(abs(corr) for corr in risk_metrics.correlation_matrix.values()),
                self.max_correlation,
                "调整策略配置"
            )

        # 板块集中度检查
        max_sector_conc = max(risk_metrics.sector_concentration.values()) if risk_metrics.sector_concentration else 0
        if max_sector_conc > self.max_sector_concentration:
            max_sector = max(risk_metrics.sector_concentration.items(), key=lambda x: x[1])[0]
            await self._create_risk_event(
                RiskEventType.SECTOR_CONCENTRATION,
                RiskLevel.MEDIUM,
                f"板块 {max_sector} 集中度 {max_sector_conc:.2%} 过高",
                max_sector_conc,
                self.max_sector_concentration,
                "分散化投资"
            )

        # 流动性风险检查
        if risk_metrics.liquidity_score < 0.3:
            await self._create_risk_event(
                RiskEventType.LIQUIDITY_RISK,
                RiskLevel.MEDIUM,
                f"组合流动性评分过低: {risk_metrics.liquidity_score:.2f}",
                risk_metrics.liquidity_score,
                0.3,
                "增加高流动性品种"
            )

    async def _create_risk_event(
        self,
        event_type: RiskEventType,
        severity: RiskLevel,
        description: str,
        current_value: float,
        threshold_value: float,
        action_taken: str,
        strategy_id: Optional[str] = None
    ) -> None:
        """创建风险事件"""
        import uuid

        event = RiskEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            severity=severity,
            timestamp=datetime.now(),
            strategy_id=strategy_id,
            description=description,
            current_value=current_value,
            threshold_value=threshold_value,
            action_taken=action_taken,
            additional_data={}
        )

        self.risk_events.append(event)

        # 调用回调函数
        for callback in self.risk_callbacks:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"风险回调执行失败: {e}")

        # 记录日志
        log_level = {
            RiskLevel.LOW: logging.INFO,
            RiskLevel.MEDIUM: logging.WARNING,
            RiskLevel.HIGH: logging.ERROR,
            RiskLevel.CRITICAL: logging.CRITICAL
        }.get(severity, logging.INFO)

        logger.log(log_level, f"风险事件: {description} - 采取行动: {action_taken}")

    async def _monitoring_loop(self) -> None:
        """风险监控循环"""
        while self.is_monitoring:
            try:
                # 这里应该获取最新的组合和策略数据
                # 简化实现
                await asyncio.sleep(60)  # 每分钟检查一次

            except Exception as e:
                logger.error(f"风险监控循环出错: {e}")
                await asyncio.sleep(10)

    def get_risk_summary(self) -> Dict[str, Any]:
        """获取风险汇总"""
        if not self.risk_events:
            return {
                "total_events": 0,
                "by_severity": {},
                "by_type": {},
                "recent_events": []
            }

        # 按严重程度统计
        by_severity = {}
        for event in self.risk_events:
            severity = event.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1

        # 按事件类型统计
        by_type = {}
        for event in self.risk_events:
            event_type = event.event_type.value
            by_type[event_type] = by_type.get(event_type, 0) + 1

        # 最近事件
        recent_events = sorted(
            self.risk_events,
            key=lambda x: x.timestamp,
            reverse=True
        )[:10]

        return {
            "total_events": len(self.risk_events),
            "by_severity": by_severity,
            "by_type": by_type,
            "recent_events": [
                {
                    "event_id": event.event_id,
                    "type": event.event_type.value,
                    "severity": event.severity.value,
                    "timestamp": event.timestamp.isoformat(),
                    "description": event.description,
                    "action_taken": event.action_taken
                }
                for event in recent_events
            ]
        }

    def register_risk_callback(self, callback: callable) -> None:
        """注册风险事件回调"""
        self.risk_callbacks.append(callback)

    def update_market_data(self, market_data: Dict[str, Any]) -> None:
        """更新市场数据"""
        # 更新基准收益率
        if 'benchmark_return' in market_data:
            self.benchmark_returns.append(market_data['benchmark_return'])
            if len(self.benchmark_returns) > 500:  # 保持最近500个数据点
                self.benchmark_returns = self.benchmark_returns[-500:]

    def update_strategy_returns(self, strategy_id: str, returns: List[float]) -> None:
        """更新策略收益率"""
        self.strategy_returns[strategy_id] = returns
        if len(returns) > 500:  # 保持最近500个数据点
            self.strategy_returns[strategy_id] = returns[-500:]