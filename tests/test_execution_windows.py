import asyncio
from datetime import datetime
from typing import Any

import pytest

from src.cherryquant.ai.agents.agent_manager import AgentManager, PortfolioRiskConfig
from src.trading.order_manager import KLineOrderManager


class DummyExecution:
    """简单的执行对象，用于测试 AgentManager.live_executions 的滚动窗口。"""

    def __init__(self, idx: int, strategy_id: str = "s1") -> None:
        self.strategy_id = strategy_id
        self.symbol = "rb"
        self.execution_id = f"e{idx}"
        self.order_id = f"o{idx}"

        class _Dir:
            value = "long"

        self.direction = _Dir()
        self.volume = 1
        self.price = 3500.0 + idx
        self.timestamp = datetime.now()
        self.commission = 0.0


class DummyGateway:
    """最小网关桩，用于测试 KLineOrderManager.executions 的窗口行为。"""

    def __init__(self) -> None:
        self._order_cb = None
        self._trade_cb = None
        self._tick_cb = None

    def register_order_callback(self, cb: Any) -> None:
        self._order_cb = cb

    def register_trade_callback(self, cb: Any) -> None:
        self._trade_cb = cb

    def register_tick_callback(self, cb: Any) -> None:
        self._tick_cb = cb

    def send_order(self, order_request: Any) -> str:
        # 简化：始终返回同一个 vt_orderid
        return "vt-order-1"

    def cancel_order(self, vt_orderid: str) -> bool:
        return True

    def get_tick(self, symbol: str) -> None:
        return None


class DummyTradeData:
    """最小成交对象，用于驱动 _on_trade_update。"""

    def __init__(self, vt_orderid: str) -> None:
        from src.trading.order_manager import Direction

        self.vt_orderid = vt_orderid
        self.direction = Direction.LONG
        self.volume = 1
        self.price = 3500.0
        self.trade_time = datetime.now()
        self.commission = 0.0


@pytest.mark.asyncio
async def test_live_executions_window_capped():
    """AgentManager.live_executions 应按每个策略保留固定数量的最新记录。"""

    risk_cfg = PortfolioRiskConfig(
        max_total_capital_usage=1.0,
        max_correlation_threshold=1.0,
        max_sector_concentration=1.0,
        portfolio_stop_loss=1.0,
        daily_loss_limit=1.0,
        max_leverage_total=10.0,
    )

    am = AgentManager(
        db_manager=None,
        market_data_manager=None,
        risk_config=risk_cfg,
        ai_client=None,
        order_manager=None,
    )

    # 超过窗口大小写入执行记录
    limit = am._max_live_executions_per_strategy
    total = limit + 100

    for i in range(total):
        await am._on_execution_update(DummyExecution(i))

    records = am.live_executions.get("s1")
    assert records is not None
    assert len(records) == limit
    # 确认保留的是最新的 N 条
    assert records[0]["execution_id"] == f"e{total - limit}"
    assert records[-1]["execution_id"] == f"e{total - 1}"


@pytest.mark.asyncio
async def test_order_manager_executions_window_capped():
    """KLineOrderManager.executions 应仅保留最近 N 条执行记录。"""

    gw = DummyGateway()
    mgr = KLineOrderManager(gw)

    # 先下一个订单，让 SmartOrder 产生 vt_orderid
    from src.trading.order_manager import Direction, OrderType, OrderTIF

    oid = await mgr.place_order(
        strategy_id="s1",
        symbol="rb.SHFE",
        direction=Direction.LONG,
        order_type=OrderType.LIMIT,
        volume=1,
        price=3500.0,
        time_in_force=OrderTIF.GTT_NEXT_BAR,
    )
    assert oid is not None
    order = mgr.get_order(oid)
    assert order is not None
    vt_orderid = getattr(order, "vt_orderid", None)
    assert vt_orderid == "vt-order-1"

    # 超过窗口大小触发成交更新
    limit = mgr._max_executions
    total = limit + 200

    for _ in range(total):
        await mgr._on_trade_update(DummyTradeData(vt_orderid))

    assert len(mgr.executions) == limit
