"""
Prometheus监控指标（真实实现 with Pydantic v2）

功能：
1. 真实的Prometheus客户端集成
2. 关键业务指标定义
3. 自动暴露/metrics端点
4. Grafana仪表盘兼容

教学要点：
1. Prometheus metrics类型（Counter, Gauge, Histogram, Summary）
2. 标签（Labels）使用
3. 监控最佳实践
4. Python 3.12+ 类型注解

代码风格：Python 3.12+ with Pydantic v2

安装依赖：pip install prometheus-client
"""

from typing import Any
from datetime import datetime

# Prometheus客户端导入（带降级处理）
try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        Summary,
        Info,
        generate_latest,
        REGISTRY,
        start_http_server,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # 降级：简化实现
    class Counter:
        def __init__(self, *args, **kwargs):
            self.value = 0
        def inc(self, amount=1):
            self.value += amount
        def labels(self, **kwargs):
            return self

    class Gauge:
        def __init__(self, *args, **kwargs):
            self.value = 0
        def set(self, value):
            self.value = value
        def inc(self, amount=1):
            self.value += amount
        def dec(self, amount=1):
            self.value -= amount
        def labels(self, **kwargs):
            return self

    class Histogram:
        def __init__(self, *args, **kwargs):
            self.values = []
        def observe(self, value):
            self.values.append(value)
        def labels(self, **kwargs):
            return self

    Summary = Histogram
    Info = Gauge


class PrometheusMetrics:
    """
    Prometheus指标收集器（真实实现）

    教学要点：
    - Counter：只增不减的计数器（如总请求数）
    - Gauge：可增可减的仪表（如当前持仓量）
    - Histogram：分布统计（如延迟分布）
    - Summary：百分位统计（如P95延迟）

    代码风格：Python 3.12+
    """

    def __init__(self, namespace: str = "cherryquant"):
        """
        初始化Prometheus指标

        Args:
            namespace: 指标命名空间
        """
        self.namespace = namespace
        self.enabled = PROMETHEUS_AVAILABLE

        if not self.enabled:
            print("⚠️  prometheus-client未安装，使用简化实现")
            print("   安装: pip install prometheus-client")

        # 定义指标
        self._init_metrics()

    def _init_metrics(self) -> None:
        """初始化所有指标"""

        # ==================== 数据采集指标 ====================

        self.data_fetch_total = Counter(
            f"{self.namespace}_data_fetch_total",
            "数据获取总次数",
            labelnames=["symbol", "status"]  # status: success/error
        )

        self.data_fetch_latency = Histogram(
            f"{self.namespace}_data_fetch_latency_seconds",
            "数据获取延迟（秒）",
            labelnames=["symbol"],
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0)
        )

        # ==================== AI决策指标 ====================

        self.ai_decision_total = Counter(
            f"{self.namespace}_ai_decision_total",
            "AI决策总次数",
            labelnames=["symbol", "decision"]  # decision: LONG/SHORT/HOLD
        )

        self.ai_confidence = Gauge(
            f"{self.namespace}_ai_confidence",
            "AI决策置信度",
            labelnames=["symbol"]
        )

        self.ai_cost_usd = Counter(
            f"{self.namespace}_ai_cost_usd_total",
            "AI API调用成本（美元）"
        )

        self.ai_latency = Histogram(
            f"{self.namespace}_ai_latency_seconds",
            "AI决策延迟（秒）",
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
        )

        # ==================== 交易执行指标 ====================

        self.trade_total = Counter(
            f"{self.namespace}_trade_total",
            "交易总次数",
            labelnames=["symbol", "side"]  # side: BUY/SELL
        )

        self.trade_volume = Counter(
            f"{self.namespace}_trade_volume_total",
            "交易总数量",
            labelnames=["symbol"]
        )

        self.trade_value = Counter(
            f"{self.namespace}_trade_value_total",
            "交易总金额",
            labelnames=["symbol"]
        )

        # ==================== 盈亏指标 ====================

        self.total_pnl = Gauge(
            f"{self.namespace}_total_pnl",
            "总盈亏"
        )

        self.unrealized_pnl = Gauge(
            f"{self.namespace}_unrealized_pnl",
            "未实现盈亏"
        )

        self.realized_pnl = Gauge(
            f"{self.namespace}_realized_pnl",
            "已实现盈亏"
        )

        self.position_value = Gauge(
            f"{self.namespace}_position_value",
            "持仓市值",
            labelnames=["symbol"]
        )

        # ==================== 风险指标 ====================

        self.max_drawdown = Gauge(
            f"{self.namespace}_max_drawdown",
            "最大回撤"
        )

        self.sharpe_ratio = Gauge(
            f"{self.namespace}_sharpe_ratio",
            "夏普比率"
        )

        self.win_rate = Gauge(
            f"{self.namespace}_win_rate",
            "胜率"
        )

        # ==================== 系统健康指标 ====================

        self.cpu_usage_percent = Gauge(
            f"{self.namespace}_cpu_usage_percent",
            "CPU使用率（%）"
        )

        self.memory_usage_mb = Gauge(
            f"{self.namespace}_memory_usage_mb",
            "内存使用量（MB）"
        )

        self.disk_usage_percent = Gauge(
            f"{self.namespace}_disk_usage_percent",
            "磁盘使用率（%）"
        )

        # ==================== 应用信息 ====================

        self.app_info = Info(
            f"{self.namespace}_app",
            "应用信息"
        )

        if self.enabled:
            self.app_info.info({
                "version": "1.0.0",
                "python_version": "3.12+",
                "framework": "CherryQuant"
            })


# 全局指标实例
metrics = PrometheusMetrics()


# ==================== 便捷函数 ====================

def record_data_fetch(symbol: str, success: bool, latency: float) -> None:
    """
    记录数据获取

    Args:
        symbol: 品种代码
        success: 是否成功
        latency: 延迟（秒）

    使用示例:
        record_data_fetch("rb2501", True, 0.123)
    """
    status = "success" if success else "error"
    metrics.data_fetch_total.labels(symbol=symbol, status=status).inc()
    metrics.data_fetch_latency.labels(symbol=symbol).observe(latency)


def record_ai_decision(
    symbol: str,
    decision: str,
    confidence: float,
    cost: float,
    latency: float
) -> None:
    """
    记录AI决策

    Args:
        symbol: 品种代码
        decision: 决策类型（LONG/SHORT/HOLD）
        confidence: 置信度（0-1）
        cost: API成本（美元）
        latency: 延迟（秒）

    使用示例:
        record_ai_decision("rb2501", "LONG", 0.85, 0.002, 1.5)
    """
    metrics.ai_decision_total.labels(symbol=symbol, decision=decision).inc()
    metrics.ai_confidence.labels(symbol=symbol).set(confidence)
    metrics.ai_cost_usd.inc(cost)
    metrics.ai_latency.observe(latency)


def record_trade(symbol: str, side: str, quantity: int, price: float) -> None:
    """
    记录交易

    Args:
        symbol: 品种代码
        side: 方向（BUY/SELL）
        quantity: 数量
        price: 价格

    使用示例:
        record_trade("rb2501", "BUY", 10, 4000.0)
    """
    metrics.trade_total.labels(symbol=symbol, side=side).inc()
    metrics.trade_volume.labels(symbol=symbol).inc(quantity)
    metrics.trade_value.labels(symbol=symbol).inc(quantity * price)


def record_pnl(total_pnl: float, unrealized: float, realized: float) -> None:
    """
    记录盈亏

    Args:
        total_pnl: 总盈亏
        unrealized: 未实现盈亏
        realized: 已实现盈亏

    使用示例:
        record_pnl(50000, 30000, 20000)
    """
    metrics.total_pnl.set(total_pnl)
    metrics.unrealized_pnl.set(unrealized)
    metrics.realized_pnl.set(realized)


def record_position_value(symbol: str, value: float) -> None:
    """
    记录持仓市值

    Args:
        symbol: 品种代码
        value: 持仓市值

    使用示例:
        record_position_value("rb2501", 400000.0)
    """
    metrics.position_value.labels(symbol=symbol).set(value)


def record_risk_metrics(
    max_drawdown: float,
    sharpe_ratio: float,
    win_rate: float
) -> None:
    """
    记录风险指标

    Args:
        max_drawdown: 最大回撤
        sharpe_ratio: 夏普比率
        win_rate: 胜率

    使用示例:
        record_risk_metrics(-0.08, 1.5, 0.60)
    """
    metrics.max_drawdown.set(max_drawdown)
    metrics.sharpe_ratio.set(sharpe_ratio)
    metrics.win_rate.set(win_rate)


def record_system_health(
    cpu_percent: float,
    memory_mb: float,
    disk_percent: float
) -> None:
    """
    记录系统健康

    Args:
        cpu_percent: CPU使用率（%）
        memory_mb: 内存使用量（MB）
        disk_percent: 磁盘使用率（%）

    使用示例:
        record_system_health(45.2, 2048.5, 60.1)
    """
    metrics.cpu_usage_percent.set(cpu_percent)
    metrics.memory_usage_mb.set(memory_mb)
    metrics.disk_usage_percent.set(disk_percent)


def start_metrics_server(port: int = 9090) -> None:
    """
    启动Prometheus metrics HTTP服务器

    Args:
        port: 端口号（默认9090）

    使用示例:
        start_metrics_server(port=9090)
        # 访问 http://localhost:9090/metrics
    """
    if not PROMETHEUS_AVAILABLE:
        print("⚠️  prometheus-client未安装，无法启动metrics服务器")
        print("   安装: pip install prometheus-client")
        return

    try:
        start_http_server(port)
        print(f"✅ Prometheus metrics服务器已启动: http://localhost:{port}/metrics")
    except Exception as e:
        print(f"❌ 启动metrics服务器失败: {e}")


def get_metrics_text() -> str:
    """
    获取Prometheus格式的指标文本

    Returns:
        Prometheus格式的指标

    使用示例:
        text = get_metrics_text()
        print(text)
    """
    if not PROMETHEUS_AVAILABLE:
        return "# prometheus-client not available\n"

    return generate_latest(REGISTRY).decode("utf-8")


# ==================== 使用示例 ====================

if __name__ == "__main__":
    print("🔧 CherryQuant Prometheus Metrics 测试\n")

    # 模拟一些指标
    print("1. 记录数据获取...")
    record_data_fetch("rb2501", True, 0.123)
    record_data_fetch("rb2501", True, 0.156)
    record_data_fetch("hc2501", False, 2.5)

    print("2. 记录AI决策...")
    record_ai_decision("rb2501", "LONG", 0.85, 0.002, 1.5)
    record_ai_decision("hc2501", "SHORT", 0.72, 0.002, 1.8)

    print("3. 记录交易...")
    record_trade("rb2501", "BUY", 10, 4000.0)
    record_trade("hc2501", "SELL", 5, 3500.0)

    print("4. 记录盈亏...")
    record_pnl(50000, 30000, 20000)

    print("5. 记录风险指标...")
    record_risk_metrics(-0.08, 1.5, 0.60)

    print("6. 记录系统健康...")
    record_system_health(45.2, 2048.5, 60.1)

    print("\n📊 当前指标:")
    print(get_metrics_text())

    print("\n💡 启动HTTP服务器:")
    print("   start_metrics_server(port=9090)")
    print("   然后访问: http://localhost:9090/metrics")
