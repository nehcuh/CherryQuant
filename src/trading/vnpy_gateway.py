"""
VNPy CTP网关集成
连接CherryQuant多代理系统与VNPy交易框架
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

from vnpy.event import Event, EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.object import (
    TickData, BarData, OrderData, TradeData, PositionData,
    AccountData, ContractData, OrderRequest, CancelRequest, SubscribeRequest
)
from vnpy.trader.constant import Direction, Status, OrderType, Offset, Exchange
from vnpy.trader.gateway import BaseGateway

try:
    from vnpy_ctp import CtpGateway
    CTP_AVAILABLE = True
except ImportError:
    CtpGateway = None
    CTP_AVAILABLE = False

from ..cherryquant.cherry_quant_strategy import CherryQuantStrategy

logger = logging.getLogger(__name__)

class OrderStatus(Enum):
    """订单状态"""
    SUBMITTED = "submitted"
    NOTTRADED = "not_traded"
    PARTTRADED = "part_traded"
    ALLTRADED = "all_traded"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

@dataclass
class OrderRequest:
    """订单请求"""
    strategy_id: str
    symbol: str
    direction: Direction
    order_type: OrderType
    volume: int
    price: float
    offset: Offset
    reference: str = ""

@dataclass
class PositionInfo:
    """持仓信息"""
    symbol: str
    direction: Direction
    volume: int
    frozen: int
    price: float
    pnl: float
    yd_volume: int

class VNPyGateway:
    """VNPy交易网关"""

    def __init__(
        self,
        gateway_name: str = "CTP",
        setting: Dict[str, Any] = None
    ):
        """初始化VNPy网关

        Args:
            gateway_name: 网关名称
            setting: 网关设置
        """
        self.gateway_name = gateway_name
        self.setting = setting or {}

        # 初始化事件引擎和主引擎
        self.event_engine = EventEngine()
        self.main_engine = MainEngine(self.event_engine)

        # 交易状态
        self.connected = False
        self.authenticated = False
        self.trading = False

        # 数据缓存
        self.contracts: Dict[str, ContractData] = {}
        self.positions: Dict[str, PositionData] = {}
        self.accounts: Dict[str, AccountData] = {}
        self.orders: Dict[str, OrderData] = {}
        self.trades: List[TradeData] = []
        self.ticks: Dict[str, TickData] = {}

        # 回调函数
        self.tick_callbacks: List[Callable] = []
        self.trade_callbacks: List[Callable] = []
        self.order_callbacks: List[Callable] = []
        self.position_callbacks: List[Callable] = []

        # 策略实例
        self.strategies: Dict[str, CherryQuantStrategy] = {}

        logger.info(f"VNPy网关初始化完成: {gateway_name}")

    def initialize(self) -> bool:
        """初始化网关"""
        try:
            # 检查 CTP 是否可用
            if self.gateway_name == "CTP":
                if not CTP_AVAILABLE:
                    logger.error("vnpy_ctp 未安装或不可用")
                    return False

                # 添加CTP网关（传入网关类，不是字符串）
                self.main_engine.add_gateway(CtpGateway)
                logger.info("CTP网关已添加到主引擎")

            # 注册事件处理器
            self._register_event_handlers()

            logger.info("VNPy网关初始化成功")
            return True

        except Exception as e:
            logger.error(f"VNPy网关初始化失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def connect(self) -> bool:
        """连接网关"""
        try:
            # 连接网关
            self.main_engine.connect(self.setting, self.gateway_name)

            logger.info(f"正在连接{self.gateway_name}网关...")
            return True

        except Exception as e:
            logger.error(f"连接网关失败: {e}")
            return False

    async def wait_for_connection(self, timeout: int = 30) -> bool:
        """等待网关连接成功

        Args:
            timeout: 超时时间（秒）

        Returns:
            是否连接成功
        """
        import time
        start_time = time.time()

        logger.info("等待CTP连接...")
        while time.time() - start_time < timeout:
            if self.connected:
                logger.info("✅ CTP连接已建立")
                return True
            await asyncio.sleep(0.5)

        logger.error(f"❌ CTP连接超时（{timeout}秒）")
        return False

    def disconnect(self) -> None:
        """断开网关连接"""
        try:
            self.main_engine.close()
            self.connected = False
            logger.info("网关连接已断开")
        except Exception as e:
            logger.error(f"断开网关连接失败: {e}")

    def _register_event_handlers(self) -> None:
        """注册事件处理器"""
        from vnpy.event import (
            EVENT_TICK, EVENT_TRADE, EVENT_ORDER, EVENT_POSITION,
            EVENT_ACCOUNT, EVENT_CONTRACT, EVENT_LOG
        )

        # 注册事件
        self.event_engine.register(EVENT_TICK, self._on_tick)
        self.event_engine.register(EVENT_TRADE, self._on_trade)
        self.event_engine.register(EVENT_ORDER, self._on_order)
        self.event_engine.register(EVENT_POSITION, self._on_position)
        self.event_engine.register(EVENT_ACCOUNT, self._on_account)
        self.event_engine.register(EVENT_CONTRACT, self._on_contract)
        self.event_engine.register(EVENT_LOG, self._on_log)

    def _on_log(self, event: Event) -> None:
        """日志事件处理"""
        log_data = event.data
        msg = log_data.msg

        # 检测连接成功消息
        if '成功登录' in msg or '登录成功' in msg:
            self.connected = True
            logger.info(f"✅ CTP连接成功: {msg}")
        elif '连接成功' in msg:
            logger.info(f"CTP网络连接: {msg}")
        elif '失败' in msg or '错误' in msg:
            logger.warning(f"CTP消息: {msg}")

    def _on_tick(self, event: Event) -> None:
        """Tick事件处理"""
        tick: TickData = event.data
        self.ticks[tick.vt_symbol] = tick

        # 调用回调函数
        for callback in self.tick_callbacks:
            try:
                callback(tick)
            except Exception as e:
                logger.error(f"Tick回调函数执行失败: {e}")

    def _on_trade(self, event: Event) -> None:
        """成交事件处理"""
        trade: TradeData = event.data
        self.trades.append(trade)

        # 调用回调函数
        for callback in self.trade_callbacks:
            try:
                callback(trade)
            except Exception as e:
                logger.error(f"成交回调函数执行失败: {e}")

    def _on_order(self, event: Event) -> None:
        """订单事件处理"""
        order: OrderData = event.data
        self.orders[order.vt_orderid] = order

        # 调用回调函数
        for callback in self.order_callbacks:
            try:
                callback(order)
            except Exception as e:
                logger.error(f"订单回调函数执行失败: {e}")

    def _on_position(self, event: Event) -> None:
        """持仓事件处理"""
        position: PositionData = event.data
        self.positions[position.vt_positionid] = position

        # 调用回调函数
        for callback in self.position_callbacks:
            try:
                callback(position)
            except Exception as e:
                logger.error(f"持仓回调函数执行失败: {e}")

    def _on_account(self, event: Event) -> None:
        """账户事件处理"""
        account: AccountData = event.data
        self.accounts[account.vt_accountid] = account

    def _on_contract(self, event: Event) -> None:
        """合约事件处理"""
        contract: ContractData = event.data
        self.contracts[contract.vt_symbol] = contract

    def send_order(self, req: OrderRequest) -> Optional[str]:
        """发送订单"""
        try:
            # 检查连接状态
            if not self.connected:
                logger.error("网关未连接，无法发送订单")
                return None

            # 检查合约是否存在
            if req.symbol not in self.contracts:
                logger.error(f"合约不存在: {req.symbol}")
                return None

            contract = self.contracts[req.symbol]

            # 创建VNPy订单请求
            vnpy_req = OrderRequest(
                symbol=contract.symbol,
                exchange=contract.exchange,
                direction=req.direction,
                type=req.order_type,
                volume=req.volume,
                price=req.price,
                offset=req.offset,
                reference=req.reference
            )

            # 发送订单
            vt_orderid = self.main_engine.send_order(vnpy_req, self.gateway_name)

            if vt_orderid:
                logger.info(f"订单发送成功: {req.symbol} {req.direction.value} {req.volume}手 @ {req.price}")
                return vt_orderid
            else:
                logger.error("订单发送失败")
                return None

        except Exception as e:
            logger.error(f"发送订单异常: {e}")
            return None

    def cancel_order(self, vt_orderid: str) -> bool:
        """撤销订单"""
        try:
            if vt_orderid not in self.orders:
                logger.error(f"订单不存在: {vt_orderid}")
                return False

            order = self.orders[vt_orderid]

            # 创建撤单请求
            cancel_req = CancelRequest(
                orderid=order.orderid,
                symbol=order.symbol,
                exchange=order.exchange
            )

            # 发送撤单
            self.main_engine.cancel_order(cancel_req, self.gateway_name)
            logger.info(f"撤单请求发送: {vt_orderid}")
            return True

        except Exception as e:
            logger.error(f"撤单异常: {e}")
            return False

    def get_contract(self, vt_symbol: str) -> Optional[ContractData]:
        """获取合约信息"""
        return self.contracts.get(vt_symbol)

    def get_position(self, vt_positionid: str) -> Optional[PositionData]:
        """获取持仓信息"""
        return self.positions.get(vt_positionid)

    def get_account(self, vt_accountid: str) -> Optional[AccountData]:
        """获取账户信息"""
        return self.accounts.get(vt_accountid)

    def get_order(self, vt_orderid: str) -> Optional[OrderData]:
        """获取订单信息"""
        return self.orders.get(vt_orderid)

    def get_tick(self, vt_symbol: str) -> Optional[TickData]:
        """获取Tick数据"""
        return self.ticks.get(vt_symbol)

    def get_all_positions(self) -> List[PositionData]:
        """获取所有持仓"""
        return list(self.positions.values())

    def get_all_accounts(self) -> List[AccountData]:
        """获取所有账户"""
        return list(self.accounts.values())

    def get_all_active_orders(self) -> List[OrderData]:
        """获取所有活动订单"""
        return [order for order in self.orders.values() if order.status in [Status.NOTTRADED, Status.PARTTRADED]]

    def subscribe_market_data(self, vt_symbols: List[str]) -> None:
        """订阅市场数据"""
        try:
            for vt_symbol in vt_symbols:
                # 解析 vt_symbol (格式: rb2501.SHFE)
                if '.' in vt_symbol:
                    symbol, exchange_str = vt_symbol.split('.', 1)
                else:
                    symbol = vt_symbol
                    exchange_str = 'SHFE'  # 默认上期所

                # 转换交易所字符串到 Exchange 枚举
                try:
                    exchange = Exchange[exchange_str]
                except KeyError:
                    logger.warning(f"未知交易所: {exchange_str}，使用默认值 SHFE")
                    exchange = Exchange.SHFE

                # 创建订阅请求
                req = SubscribeRequest(
                    symbol=symbol,
                    exchange=exchange
                )

                # 订阅
                self.main_engine.subscribe(req, self.gateway_name)
                logger.info(f"订阅行情: {vt_symbol}")

        except Exception as e:
            logger.error(f"订阅市场数据失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def unsubscribe_market_data(self, vt_symbols: List[str]) -> None:
        """取消订阅市场数据"""
        try:
            self.main_engine.unsubscribe(vt_symbols, self.gateway_name)
            logger.info(f"取消订阅市场数据: {vt_symbols}")
        except Exception as e:
            logger.error(f"取消订阅市场数据失败: {e}")

    def add_strategy(self, strategy_id: str, strategy: CherryQuantStrategy) -> None:
        """添加策略"""
        self.strategies[strategy_id] = strategy
        logger.info(f"策略已添加: {strategy_id}")

    def remove_strategy(self, strategy_id: str) -> None:
        """移除策略"""
        if strategy_id in self.strategies:
            del self.strategies[strategy_id]
            logger.info(f"策略已移除: {strategy_id}")

    def register_tick_callback(self, callback: Callable) -> None:
        """注册Tick数据回调"""
        self.tick_callbacks.append(callback)

    def register_trade_callback(self, callback: Callable) -> None:
        """注册成交回调"""
        self.trade_callbacks.append(callback)

    def register_order_callback(self, callback: Callable) -> None:
        """注册订单回调"""
        self.order_callbacks.append(callback)

    def register_position_callback(self, callback: Callable) -> None:
        """注册持仓回调"""
        self.position_callbacks.append(callback)

    def get_gateway_status(self) -> Dict[str, Any]:
        """获取网关状态"""
        return {
            "gateway_name": self.gateway_name,
            "connected": self.connected,
            "authenticated": self.authenticated,
            "trading": self.trading,
            "contracts_count": len(self.contracts),
            "positions_count": len(self.positions),
            "accounts_count": len(self.accounts),
            "active_orders_count": len(self.get_all_active_orders()),
            "strategies_count": len(self.strategies),
            "last_update": datetime.now().isoformat()
        }

    def get_trading_statistics(self) -> Dict[str, Any]:
        """获取交易统计"""
        if not self.trades:
            return {
                "total_trades": 0,
                "total_volume": 0,
                "total_turnover": 0,
                "total_commission": 0
            }

        total_volume = sum(trade.volume for trade in self.trades)
        total_turnover = sum(trade.volume * trade.price for trade in self.trades)
        total_commission = sum(getattr(trade, 'commission', 0) for trade in self.trades)

        return {
            "total_trades": len(self.trades),
            "total_volume": total_volume,
            "total_turnover": total_turnover,
            "total_commission": total_commission,
            "avg_trade_size": total_volume / len(self.trades) if self.trades else 0,
            "last_trade_time": self.trades[-1].trade_time.isoformat() if self.trades else None
        }

# 网关管理器
class VNPyGatewayManager:
    """VNPy网关管理器"""

    def __init__(self):
        """初始化网关管理器"""
        self.gateways: Dict[str, VNPyGateway] = {}
        self.primary_gateway: Optional[VNPyGateway] = None

    def add_gateway(
        self,
        name: str,
        gateway_type: str = "CTP",
        setting: Dict[str, Any] = None
    ) -> bool:
        """添加网关"""
        try:
            gateway = VNPyGateway(gateway_type, setting)

            if gateway.initialize():
                self.gateways[name] = gateway

                # 如果是第一个网关，设为主要网关
                if self.primary_gateway is None:
                    self.primary_gateway = gateway

                logger.info(f"网关添加成功: {name}")
                return True
            else:
                logger.error(f"网关初始化失败: {name}")
                return False

        except Exception as e:
            logger.error(f"添加网关失败: {name}, 错误: {e}")
            return False

    def remove_gateway(self, name: str) -> bool:
        """移除网关"""
        try:
            if name in self.gateways:
                gateway = self.gateways[name]
                gateway.disconnect()
                del self.gateways[name]

                # 如果移除的是主要网关，重新指定主要网关
                if self.primary_gateway == gateway:
                    self.primary_gateway = next(iter(self.gateways.values()), None)

                logger.info(f"网关移除成功: {name}")
                return True
            else:
                logger.warning(f"网关不存在: {name}")
                return False

        except Exception as e:
            logger.error(f"移除网关失败: {name}, 错误: {e}")
            return False

    def get_gateway(self, name: str) -> Optional[VNPyGateway]:
        """获取网关"""
        return self.gateways.get(name)

    def connect_all(self) -> bool:
        """连接所有网关"""
        success = True
        for name, gateway in self.gateways.items():
            if not gateway.connect():
                success = False
                logger.error(f"网关连接失败: {name}")
        return success

    def disconnect_all(self) -> None:
        """断开所有网关"""
        for name, gateway in self.gateways.items():
            gateway.disconnect()

    def get_all_status(self) -> Dict[str, Any]:
        """获取所有网关状态"""
        status = {
            "total_gateways": len(self.gateways),
            "gateway_status": {}
        }

        for name, gateway in self.gateways.items():
            status["gateway_status"][name] = gateway.get_gateway_status()

        return status

# 全局网关管理器实例
gateway_manager = VNPyGatewayManager()