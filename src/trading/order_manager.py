"""
订单管理系统
基于K线数据的智能订单管理系统，支持限价单、止损止盈等高级功能
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import uuid

from .vnpy_gateway import VNPyGateway, OrderRequest
from vnpy.trader.constant import Direction, OrderType, Offset, Status

logger = logging.getLogger(__name__)

class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"           # 等待执行
    SUBMITTED = "submitted"       # 已提交
    PARTIAL = "partial_filled"    # 部分成交
    FILLED = "filled"             # 完全成交
    CANCELLED = "cancelled"       # 已撤销
    REJECTED = "rejected"         # 被拒绝
    EXPIRED = "expired"           # 已过期

class OrderTIF(Enum):
    """订单有效期类型"""
    DAY = "DAY"                   # 当日有效
    GTC = "GTC"                   # 撤销前有效
    IOC = "IOC"                   # 立即成交或撤销
    FOK = "FOK"                   # 全部成交或撤销
    GTT_NEXT_BAR = "GTT_NEXT_BAR"  # 到下一根 5m K 线收盘自动撤销

@dataclass
class SmartOrder:
    """智能订单"""
    order_id: str
    strategy_id: str
    symbol: str
    direction: Direction
    order_type: OrderType
    volume: int
    price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop: Optional[float] = None
    time_in_force: OrderTIF = OrderTIF.DAY
    create_time: datetime = field(default_factory=datetime.now)
    expire_time: Optional[datetime] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_volume: int = 0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    reason: str = ""
    reference: str = ""
    child_orders: List[str] = field(default_factory=list)  # 子订单ID（止损止盈等）
    parent_order: Optional[str] = None  # 父订单ID

@dataclass
class OrderExecution:
    """订单执行记录"""
    execution_id: str
    order_id: str
    strategy_id: str
    symbol: str
    direction: Direction
    volume: int
    price: float
    timestamp: datetime
    commission: float

class KLineOrderManager:
    """基于K线的订单管理器

    注意：本管理器内部使用 asyncio 事件循环调度异步回调，
    以便从 vn.py 的同步事件回调桥接到异步处理逻辑。"""

    def __init__(
        self,
        gateway: VNPyGateway,
        enable_smart_orders: bool = True,
        default_leverage: float = 5.0,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        """初始化订单管理器

        Args:
            gateway: VNPy交易网关
            enable_smart_orders: 是否启用智能订单
            default_leverage: 默认杠杆
        """
        self.gateway = gateway
        self.enable_smart_orders = enable_smart_orders
        self.default_leverage = default_leverage

        # 事件循环（用于跨线程调度异步回调）
        try:
            self._loop: Optional[asyncio.AbstractEventLoop] = loop or asyncio.get_running_loop()
        except RuntimeError:
            # 在无运行中事件循环的上下文中初始化时，异步回调将被安全忽略
            self._loop = None

        # 订单存储
        self.orders: Dict[str, SmartOrder] = {}
        self.executions: List[OrderExecution] = []
        # 最多保留的执行记录条数（滚动窗口）
        self._max_executions: int = 1000

        # K线数据缓存
        self.kline_data: Dict[str, List[Dict[str, Any]]] = {}
        self.last_kline_update: Dict[str, datetime] = {}

        # 回调函数
        self.order_callbacks: List[Callable] = []
        self.execution_callbacks: List[Callable] = []

        # 监控任务
        self.monitor_task: Optional[asyncio.Task] = None
        self.is_running = False

        # 注册网关回调
        self._register_gateway_callbacks()

        logger.info("K线订单管理器初始化完成")

    def _register_gateway_callbacks(self) -> None:
        """注册网关回调函数

        vn.py 的事件回调是同步的，这里通过线程安全的方式
        将异步处理函数提交到 asyncio 事件循环中执行。
        """

        def _wrap_async(cb):
            """将 async 回调包装为同步回调，安全地调度到事件循环。"""
            if not self._loop:
                # 无事件循环时，直接返回一个记录日志但不执行异步逻辑的占位实现
                def _noop(*args, **kwargs):  # noqa: D401
                    logger.debug(
                        "KLineOrderManager: no asyncio loop bound; async callback skipped"
                    )

                return _noop

            def _handler(arg):
                try:
                    fut = asyncio.run_coroutine_threadsafe(cb(arg), self._loop)
                    # 可选：为调试目的记录异常
                    def _log_result(f: asyncio.Future) -> None:
                        try:
                            _ = f.result()
                        except Exception as exc:  # noqa: BLE001
                            logger.error(f"异步订单回调执行失败: {exc}")

                    fut.add_done_callback(_log_result)
                except Exception as exc:  # noqa: BLE001
                    logger.error(f"提交异步订单回调失败: {exc}")

            return _handler

        # 使用包装后的同步回调注册到网关
        self.gateway.register_order_callback(_wrap_async(self._on_order_update))
        self.gateway.register_trade_callback(_wrap_async(self._on_trade_update))
        self.gateway.register_tick_callback(_wrap_async(self._on_tick_update))

    async def start(self) -> None:
        """启动订单管理器"""
        if self.is_running:
            return

        self.is_running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("订单管理器已启动")

    async def stop(self) -> None:
        """停止订单管理器"""
        self.is_running = False

        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        # 撤销所有待执行订单
        await self.cancel_all_pending_orders()
        logger.info("订单管理器已停止")

    async def place_order(
        self,
        strategy_id: str,
        symbol: str,
        direction: Direction,
        order_type: OrderType,
        volume: int,
        price: float = 0.0,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        trailing_stop: Optional[float] = None,
        time_in_force: OrderTIF = OrderTIF.GTT_NEXT_BAR,
        reason: str = "",
        reference: str = "",
        expire_after_seconds: Optional[int] = None,
    ) -> Optional[str]:
        """下单

        Args:
            strategy_id: 策略ID
            symbol: 交易品种
            direction: 交易方向
            order_type: 订单类型
            volume: 交易数量
            price: 价格（市价单可以为0）
            stop_loss: 止损价
            take_profit: 止盈价
            trailing_stop: 追踪止损
            time_in_force: 订单有效期
            reason: 下单原因
            reference: 参考信息

        Returns:
            订单ID或None
        """
        try:
            # 创建智能订单
            order_id = str(uuid.uuid4())
            expire_time = None

            if expire_after_seconds and expire_after_seconds > 0:
                expire_time = datetime.now() + timedelta(seconds=int(expire_after_seconds))
            elif time_in_force == OrderTIF.DAY:
                expire_time = datetime.now().replace(hour=23, minute=59, second=59)
            elif time_in_force == OrderTIF.GTT_NEXT_BAR:
                expire_time = self._next_5m_boundary(datetime.now())

            smart_order = SmartOrder(
                order_id=order_id,
                strategy_id=strategy_id,
                symbol=symbol,
                direction=direction,
                order_type=order_type,
                volume=volume,
                price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                trailing_stop=trailing_stop,
                time_in_force=time_in_force,
                expire_time=expire_time,
                reason=reason,
                reference=reference
            )

            self.orders[order_id] = smart_order

            # 如果启用智能订单且有止损止盈，创建子订单
            if self.enable_smart_orders and (stop_loss or take_profit):
                await self._create_child_orders(smart_order)

            # 立即执行主订单
            if order_type == OrderType.MARKET or price > 0:
                success = await self._execute_order(smart_order)
                if success:
                    logger.info(f"订单下单成功: {order_id} {symbol} {direction.value} {volume}手")
                    return order_id
                else:
                    # 执行失败，清理订单
                    await self._cleanup_order(order_id)
                    return None
            else:
                # 限价单等待合适价格
                logger.info(f"限价单已创建，等待执行: {order_id}")
                return order_id

        except Exception as e:
            logger.error(f"下单失败: {e}")
            return None

    async def cancel_order(self, order_id: str, reason: str = "用户撤销") -> bool:
        """撤单"""
        try:
            if order_id not in self.orders:
                logger.warning(f"订单不存在: {order_id}")
                return False

            order = self.orders[order_id]

            if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
                logger.warning(f"订单状态不允许撤销: {order.status.value}")
                return False

            # 撤销主订单
            if hasattr(order, 'vt_orderid') and order.vt_orderid:
                success = self.gateway.cancel_order(order.vt_orderid)
                if success:
                    order.status = OrderStatus.CANCELLED
                    logger.info(f"订单撤销成功: {order_id} - {reason}")

            # 撤销所有子订单
            for child_order_id in order.child_orders:
                await self.cancel_order(child_order_id, f"主订单撤销 - {reason}")

            # 调用回调
            await self._notify_order_update(order)
            return True

        except Exception as e:
            logger.error(f"撤单失败: {e}")
            return False

    async def cancel_all_pending_orders(self, strategy_id: Optional[str] = None) -> int:
        """撤销所有待执行订单"""
        cancelled_count = 0

        for order_id, order in list(self.orders.items()):
            # 策略过滤
            if strategy_id and order.strategy_id != strategy_id:
                continue

            # 状态过滤
            if order.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL]:
                if await self.cancel_order(order_id, "批量撤销"):
                    cancelled_count += 1

        logger.info(f"批量撤销完成，共撤销 {cancelled_count} 个订单")
        return cancelled_count

    def update_kline_data(self, symbol: str, kline_data: Dict[str, Any]) -> None:
        """更新K线数据"""
        try:
            timestamp = kline_data.get('timestamp', datetime.now())

            # 存储K线数据
            if symbol not in self.kline_data:
                self.kline_data[symbol] = []

            self.kline_data[symbol].append(kline_data)
            self.last_kline_update[symbol] = timestamp

            # 保持最近100根K线
            if len(self.kline_data[symbol]) > 100:
                self.kline_data[symbol] = self.kline_data[symbol][-100:]

            # 检查是否触发限价单
            asyncio.create_task(self._check_limit_orders(symbol, kline_data))

        except Exception as e:
            logger.error(f"更新K线数据失败: {e}")

    async def _execute_order(self, order: SmartOrder) -> bool:
        """执行订单"""
        try:
            # 检查订单有效期
            if order.expire_time and datetime.now() > order.expire_time:
                order.status = OrderStatus.EXPIRED
                return False

            # 确定下单价格
            price = order.price
            if order.order_type == OrderType.MARKET:
                price = 0.0  # 市价单

            # 创建VNPy订单请求
            vnpy_req = OrderRequest(
                strategy_id=order.strategy_id,
                symbol=order.symbol,
                direction=order.direction,
                order_type=order.order_type,
                volume=order.volume,
                price=price,
                offset=self._determine_offset(order),
                reference=order.reference
            )

            # 发送到网关
            vt_orderid = self.gateway.send_order(vnpy_req)

            if vt_orderid:
                order.vt_orderid = vt_orderid
                order.status = OrderStatus.SUBMITTED
                return True
            else:
                order.status = OrderStatus.REJECTED
                return False

        except Exception as e:
            logger.error(f"执行订单失败: {e}")
            order.status = OrderStatus.REJECTED
            return False

    async def _create_child_orders(self, parent_order: SmartOrder) -> None:
        """创建子订单（止损止盈）"""
        try:
            # 止损单
            if parent_order.stop_loss:
                stop_loss_order = SmartOrder(
                    order_id=str(uuid.uuid4()),
                    strategy_id=parent_order.strategy_id,
                    symbol=parent_order.symbol,
                    direction=Direction.SHORT if parent_order.direction == Direction.LONG else Direction.LONG,
                    order_type=OrderType.STOP,
                    volume=parent_order.volume,
                    price=parent_order.stop_loss,
                    parent_order=parent_order.order_id,
                    reason="止损"
                )
                self.orders[stop_loss_order.order_id] = stop_loss_order
                parent_order.child_orders.append(stop_loss_order.order_id)

            # 止盈单
            if parent_order.take_profit:
                take_profit_order = SmartOrder(
                    order_id=str(uuid.uuid4()),
                    strategy_id=parent_order.strategy_id,
                    symbol=parent_order.symbol,
                    direction=Direction.SHORT if parent_order.direction == Direction.LONG else Direction.LONG,
                    order_type=OrderType.LIMIT,
                    volume=parent_order.volume,
                    price=parent_order.take_profit,
                    parent_order=parent_order.order_id,
                    reason="止盈"
                )
                self.orders[take_profit_order.order_id] = take_profit_order
                parent_order.child_orders.append(take_profit_order.order_id)

            logger.debug(f"为订单 {parent_order.order_id} 创建了 {len(parent_order.child_orders)} 个子订单")

        except Exception as e:
            logger.error(f"创建子订单失败: {e}")

    async def _check_limit_orders(self, symbol: str, kline_data: Dict[str, Any]) -> None:
        """检查限价单是否可以执行"""
        try:
            current_price = kline_data.get('close', 0)
            if current_price <= 0:
                return

            # 检查该品种的所有限价单
            for order in list(self.orders.values()):
                if (order.symbol != symbol or
                    order.status != OrderStatus.PENDING or
                    order.order_type != OrderType.LIMIT):
                    continue

                # 检查买入限价单
                if order.direction == Direction.LONG and current_price <= order.price:
                    await self._execute_order(order)

                # 检查卖出限价单
                elif order.direction == Direction.SHORT and current_price >= order.price:
                    await self._execute_order(order)

        except Exception as e:
            logger.error(f"检查限价单失败: {e}")

    def _determine_offset(self, order: SmartOrder) -> Offset:
        """确定开平仓方向"""
        # 这里应该根据当前持仓情况来确定
        # 简化实现，默认开仓
        return Offset.OPEN

    async def _monitor_loop(self) -> None:
        """监控循环"""
        while self.is_running:
            try:
                await self._check_order_expiration()
                await self._update_trailing_stops()
                await asyncio.sleep(1)  # 每秒检查一次

            except Exception as e:
                logger.error(f"监控循环出错: {e}")
                await asyncio.sleep(5)

    def _next_5m_boundary(self, now: datetime) -> datetime:
        mins = (now.minute // 5 + 1) * 5
        return now.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=mins)

    async def _check_order_expiration(self) -> None:
        """检查订单过期"""
        current_time = datetime.now()

        for order in list(self.orders.values()):
            if (order.status == OrderStatus.PENDING and
                order.expire_time and
                current_time > order.expire_time):

                order.status = OrderStatus.EXPIRED
                await self._notify_order_update(order)
                logger.info(f"订单已过期: {order.order_id}")

    async def _update_trailing_stops(self) -> None:
        """更新追踪止损"""
        try:
            for order in list(self.orders.values()):
                if not order.trailing_stop or order.status != OrderStatus.SUBMITTED:
                    continue

                # 获取当前价格
                current_price = self._get_current_price(order.symbol)
                if current_price <= 0:
                    continue

                # 计算新的止损价
                if order.direction == Direction.LONG:
                    new_stop = current_price - order.trailing_stop
                    if new_stop > order.stop_loss:
                        order.stop_loss = new_stop
                        logger.debug(f"追踪止损更新: {order.symbol} {order.stop_loss}")

                elif order.direction == Direction.SHORT:
                    new_stop = current_price + order.trailing_stop
                    if new_stop < order.stop_loss:
                        order.stop_loss = new_stop
                        logger.debug(f"追踪止损更新: {order.symbol} {order.stop_loss}")

        except Exception as e:
            logger.error(f"更新追踪止损失败: {e}")

    def _get_current_price(self, symbol: str) -> float:
        """获取当前价格"""
        # 先尝试从tick数据获取
        tick = self.gateway.get_tick(symbol)
        if tick:
            return tick.last_price

        # 从K线数据获取最新价格
        if symbol in self.kline_data and self.kline_data[symbol]:
            return self.kline_data[symbol][-1].get('close', 0)

        return 0

    async def _cleanup_order(self, order_id: str) -> None:
        """清理订单"""
        try:
            if order_id in self.orders:
                order = self.orders[order_id]

                # 清理子订单
                for child_order_id in order.child_orders:
                    if child_order_id in self.orders:
                        del self.orders[child_order_id]

                # 清理主订单
                del self.orders[order_id]

        except Exception as e:
            logger.error(f"清理订单失败: {e}")

    async def _on_order_update(self, order_data) -> None:
        """处理订单更新"""
        try:
            # 查找对应的智能订单
            for order in self.orders.values():
                if hasattr(order, 'vt_orderid') and order.vt_orderid == order_data.vt_orderid:
                    # 更新订单状态
                    if order_data.status == Status.ALLTRADED:
                        order.status = OrderStatus.FILLED
                    elif order_data.status == Status.PARTTRADED:
                        order.status = OrderStatus.PARTIAL
                    elif order_data.status == Status.CANCELLED:
                        order.status = OrderStatus.CANCELLED
                    elif order_data.status == Status.REJECTED:
                        order.status = OrderStatus.REJECTED

                    # 更新成交信息
                    if hasattr(order_data, 'traded_volume'):
                        order.filled_volume = order_data.traded_volume

                    await self._notify_order_update(order)
                    break

        except Exception as e:
            logger.error(f"处理订单更新失败: {e}")

    async def _on_trade_update(self, trade_data) -> None:
        """处理成交更新"""
        try:
            # 查找对应的智能订单
            for order in self.orders.values():
                if hasattr(order, 'vt_orderid') and order.vt_orderid == trade_data.vt_orderid:
                    # 创建执行记录
                    execution = OrderExecution(
                        execution_id=str(uuid.uuid4()),
                        order_id=order.order_id,
                        strategy_id=order.strategy_id,
                        symbol=order.symbol,
                        direction=trade_data.direction,
                        volume=trade_data.volume,
                        price=trade_data.price,
                        timestamp=trade_data.trade_time,
                        commission=getattr(trade_data, 'commission', 0),
                    )

                    self.executions.append(execution)
                    # 滚动窗口：仅保留最近 N 条执行记录，避免长期运行时内存无限增长
                    if len(self.executions) > self._max_executions:
                        self.executions = self.executions[-self._max_executions :]

                    # 更新平均成交价格
                    total_volume = order.filled_volume
                    total_cost = order.avg_fill_price * (total_volume - trade_data.volume) + trade_data.price * trade_data.volume
                    order.avg_fill_price = total_cost / total_volume
                    order.commission += execution.commission

                    await self._notify_execution_update(execution)
                    break

        except Exception as e:
            logger.error(f"处理成交更新失败: {e}")

    async def _on_tick_update(self, tick_data) -> None:
        """处理Tick更新"""
        try:
            # 检查止损单
            symbol = tick_data.vt_symbol

            for order in list(self.orders.values()):
                if (order.symbol != symbol or
                    order.status != OrderStatus.PENDING or
                    order.order_type != OrderType.STOP):
                    continue

                current_price = tick_data.last_price

                # 检查止损触发
                if order.direction == Direction.SHORT and current_price >= order.price:  # 多头止损
                    await self._execute_order(order)
                elif order.direction == Direction.LONG and current_price <= order.price:  # 空头止损
                    await self._execute_order(order)

        except Exception as e:
            logger.error(f"处理Tick更新失败: {e}")

    async def _notify_order_update(self, order: SmartOrder) -> None:
        """通知订单更新"""
        for callback in self.order_callbacks:
            try:
                await callback(order)
            except Exception as e:
                logger.error(f"订单回调执行失败: {e}")

    async def _notify_execution_update(self, execution: OrderExecution) -> None:
        """通知执行更新"""
        for callback in self.execution_callbacks:
            try:
                await callback(execution)
            except Exception as e:
                logger.error(f"执行回调执行失败: {e}")

    def get_order(self, order_id: str) -> Optional[SmartOrder]:
        """获取订单"""
        return self.orders.get(order_id)

    def get_orders_by_strategy(self, strategy_id: str) -> List[SmartOrder]:
        """获取策略的所有订单"""
        return [order for order in self.orders.values() if order.strategy_id == strategy_id]

    def get_active_orders(self, strategy_id: Optional[str] = None) -> List[SmartOrder]:
        """获取活动订单"""
        active_orders = [order for order in self.orders.values()
                        if order.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL]]

        if strategy_id:
            active_orders = [order for order in active_orders if order.strategy_id == strategy_id]

        return active_orders

    def get_order_statistics(self, strategy_id: Optional[str] = None) -> Dict[str, Any]:
        """获取订单统计"""
        orders = list(self.orders.values())
        if strategy_id:
            orders = [order for order in orders if order.strategy_id == strategy_id]

        total_orders = len(orders)
        filled_orders = len([order for order in orders if order.status == OrderStatus.FILLED])
        cancelled_orders = len([order for order in orders if order.status == OrderStatus.CANCELLED])

        total_volume = sum(order.filled_volume for order in orders)
        total_commission = sum(order.commission for order in orders)

        return {
            "total_orders": total_orders,
            "filled_orders": filled_orders,
            "cancelled_orders": cancelled_orders,
            "fill_rate": filled_orders / total_orders if total_orders > 0 else 0,
            "total_volume": total_volume,
            "total_commission": total_commission,
            "active_orders": len(self.get_active_orders(strategy_id))
        }

    def register_order_callback(self, callback: Callable) -> None:
        """注册订单回调"""
        self.order_callbacks.append(callback)

    def register_execution_callback(self, callback: Callable) -> None:
        """注册执行回调"""
        self.execution_callbacks.append(callback)