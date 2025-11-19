import sys
import types
import enum
import asyncio
import pytest

# --- stub minimal vn.py modules before importing order_manager ---

# vnpy.trader.constant
m_vnp = types.ModuleType("vnpy")
m_vnp_trader = types.ModuleType("vnpy.trader")
# mark as package
m_vnp_trader.__path__ = []
m_vnp_trader_constant = types.ModuleType("vnpy.trader.constant")

class Direction(enum.Enum):
    LONG = "long"
    SHORT = "short"

class OrderType(enum.Enum):
    LIMIT = "limit"
    MARKET = "market"
    STOP = "stop"

class Offset(enum.Enum):
    OPEN = "open"

class Status(enum.Enum):
    ALLTRADED = "all_traded"
    PARTTRADED = "part_traded"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class Exchange(enum.Enum):
    SHFE = "SHFE"
    DCE = "DCE"
    CZCE = "CZCE"
    CFFEX = "CFFEX"
    INE = "INE"

m_vnp_trader_constant.Direction = Direction
m_vnp_trader_constant.OrderType = OrderType
m_vnp_trader_constant.Offset = Offset
m_vnp_trader_constant.Status = Status
m_vnp_trader_constant.Exchange = Exchange

# vnpy.event
m_vnp_event = types.ModuleType("vnpy.event")
class Event:  # placeholder
    def __init__(self, type: str, data=None):
        self.type = type
        self.data = data
class EventEngine:  # placeholder
    def register(self, *args, **kwargs):
        pass
m_vnp_event.Event = Event
m_vnp_event.EventEngine = EventEngine

# vnpy.trader.engine
m_vnp_trader_engine = types.ModuleType("vnpy.trader.engine")
class MainEngine:  # placeholder
    def __init__(self, event_engine=None):
        pass
    def add_gateway(self, *args, **kwargs):
        pass
    def add_rtd_service(self, *args, **kwargs):
        pass
    def connect(self, *args, **kwargs):
        pass
    def close(self):
        pass
m_vnp_trader_engine.MainEngine = MainEngine

# vnpy.trader.object
m_vnp_trader_object = types.ModuleType("vnpy.trader.object")
class TickData: pass
class BarData: pass
class OrderData:
    def __init__(self):
        self.vt_orderid = ""
        self.status = None
class TradeData: pass
class PositionData: pass
class AccountData: pass
class ContractData: pass
class OrderRequest: pass
class CancelRequest: pass
class SubscribeRequest: pass

m_vnp_trader_object.TickData = TickData
m_vnp_trader_object.BarData = BarData
m_vnp_trader_object.OrderData = OrderData
m_vnp_trader_object.TradeData = TradeData
m_vnp_trader_object.PositionData = PositionData
m_vnp_trader_object.AccountData = AccountData
m_vnp_trader_object.ContractData = ContractData
m_vnp_trader_object.OrderRequest = OrderRequest
m_vnp_trader_object.CancelRequest = CancelRequest
m_vnp_trader_object.SubscribeRequest = SubscribeRequest

# vnpy.trader.gateway
m_vnp_trader_gateway = types.ModuleType("vnpy.trader.gateway")
class BaseGateway: pass
m_vnp_trader_gateway.BaseGateway = BaseGateway

# vnpy.trader.utility
m_vnp_trader_utility = types.ModuleType("vnpy.trader.utility")
class BarGenerator: pass
class ArrayManager: pass
m_vnp_trader_utility.BarGenerator = BarGenerator
m_vnp_trader_utility.ArrayManager = ArrayManager

# vnpy.app.cta_strategy
m_vnp_app = types.ModuleType("vnpy.app")
m_vnp_app_cta = types.ModuleType("vnpy.app.cta_strategy")
class CtaTemplate: pass
class StopOrder: pass
class TickData: pass
class BarData: pass
class OrderData: pass
class TradeData: pass
m_vnp_app_cta.CtaTemplate = CtaTemplate
m_vnp_app_cta.StopOrder = StopOrder
m_vnp_app_cta.TickData = TickData
m_vnp_app_cta.BarData = BarData
m_vnp_app_cta.OrderData = OrderData
m_vnp_app_cta.TradeData = TradeData

# install into sys.modules
sys.modules["vnpy"] = m_vnp
sys.modules["vnpy.event"] = m_vnp_event
sys.modules["vnpy.trader"] = m_vnp_trader
sys.modules["vnpy.trader.constant"] = m_vnp_trader_constant
sys.modules["vnpy.trader.engine"] = m_vnp_trader_engine
sys.modules["vnpy.trader.object"] = m_vnp_trader_object
sys.modules["vnpy.trader.gateway"] = m_vnp_trader_gateway
sys.modules["vnpy.trader.utility"] = m_vnp_trader_utility
sys.modules["vnpy.app"] = m_vnp_app
sys.modules["vnpy.app.cta_strategy"] = m_vnp_app_cta

# --- now safe to import order_manager ---
from src.trading.order_manager import KLineOrderManager, OrderTIF, OrderStatus
from vnpy.trader.constant import Direction, OrderType


class FakeGateway:
    def __init__(self):
        self.sent = []

    # API expected by KLineOrderManager
    def register_order_callback(self, cb):
        self._order_cb = cb

    def register_trade_callback(self, cb):
        self._trade_cb = cb

    def register_tick_callback(self, cb):
        self._tick_cb = cb

    def send_order(self, order_request):
        self.sent.append(order_request)
        return "vt-order-1"

    def cancel_order(self, vt_orderid):
        return True

    def get_tick(self, symbol):
        return None


@pytest.mark.asyncio
async def test_place_order_expire_after_seconds_sets_expire_time():
    gw = FakeGateway()
    mgr = KLineOrderManager(gw)

    oid = await mgr.place_order(
        strategy_id="s1",
        symbol="rb.SHFE",
        direction=Direction.LONG,
        order_type=OrderType.LIMIT,
        volume=1,
        price=0.0,
        time_in_force=OrderTIF.GTT_NEXT_BAR,
        expire_after_seconds=2,
    )
    assert oid is not None
    order = mgr.get_order(oid)
    assert order is not None and order.expire_time is not None

    # Wait and force expiration check
    await asyncio.sleep(2.2)
    await mgr._check_order_expiration()
    assert order.status == OrderStatus.EXPIRED


@pytest.mark.asyncio
async def test_default_gtt_next_bar_sets_next_5m_boundary():
    gw = FakeGateway()
    mgr = KLineOrderManager(gw)

    # Capture now and expected boundary using helper
    from datetime import datetime

    now = datetime.now()
    expected = mgr._next_5m_boundary(now)

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
    assert order is not None and order.expire_time is not None

    # The expire_time should be close to expected boundary
    diff = abs((order.expire_time - expected).total_seconds())
    assert diff < 3.0
