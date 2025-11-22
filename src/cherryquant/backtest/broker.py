"""
模拟经纪商 (Pydantic v2)

功能：
1. 订单撮合
2. 滑点和手续费计算
3. 持仓管理
4. 资金管理

教学要点：
1. 模拟真实交易环境
2. 订单生命周期管理
3. 成本计算（手续费+滑点）

代码风格：Python 3.12+ with Pydantic v2
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, computed_field

from cherryquant.constants import BacktestConstants


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"  # 市价单
    LIMIT = "limit"    # 限价单
    STOP = "stop"      # 止损单


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"      # 待处理
    FILLED = "filled"        # 已成交
    PARTIALLY_FILLED = "partially_filled"  # 部分成交
    CANCELLED = "cancelled"  # 已取消
    REJECTED = "rejected"    # 已拒绝


class Order(BaseModel):
    """
    订单模型（Pydantic v2）

    教学要点：
    - 使用Pydantic v2进行数据验证
    - Python 3.12+ 类型注解风格（使用 | 而非 Union）
    - computed_field装饰器用于计算属性
    """
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    price: float | None = None  # 限价单需要
    stop_price: float | None = None  # 止损单需要
    filled_quantity: int = 0
    status: OrderStatus = OrderStatus.PENDING
    order_id: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)
    filled_price: float | None = None
    commission: float = 0.0

    model_config = {"arbitrary_types_allowed": True}

    @computed_field
    @property
    def is_filled(self) -> bool:
        """订单是否已成交"""
        return self.status == OrderStatus.FILLED

    @computed_field
    @property
    def remaining_quantity(self) -> int:
        """剩余数量"""
        return self.quantity - self.filled_quantity


class Trade(BaseModel):
    """
    成交记录（Pydantic v2）
    """
    trade_id: str
    order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    commission: float
    slippage: float
    timestamp: datetime

    model_config = {"arbitrary_types_allowed": True}

    @computed_field
    @property
    def total_cost(self) -> float:
        """总成本（价格 * 数量 + 手续费）"""
        return self.price * self.quantity + self.commission


class Position(BaseModel):
    """
    持仓（Pydantic v2）
    """
    symbol: str
    quantity: int = 0  # 正数=多头，负数=空头，0=无持仓
    avg_price: float = 0.0
    current_price: float = 0.0
    realized_pnl: float = 0.0  # 已实现盈亏

    @computed_field
    @property
    def market_value(self) -> float:
        """市值"""
        return abs(self.quantity) * self.current_price

    @computed_field
    @property
    def unrealized_pnl(self) -> float:
        """浮动盈亏"""
        if self.quantity == 0:
            return 0.0

        if self.quantity > 0:  # 多头
            return self.quantity * (self.current_price - self.avg_price)

        # 空头
        return abs(self.quantity) * (self.avg_price - self.current_price)

    @computed_field
    @property
    def total_pnl(self) -> float:
        """总盈亏（已实现+未实现）"""
        return self.realized_pnl + self.unrealized_pnl

    def is_empty(self) -> bool:
        """是否空仓"""
        return self.quantity == 0


class SimulatedBroker:
    """
    模拟经纪商

    教学要点：
    1. 订单撮合逻辑
    2. 滑点和手续费计算
    3. 持仓管理
    4. 资金管理
    """

    def __init__(
        self,
        initial_capital: float = BacktestConstants.DEFAULT_INITIAL_CAPITAL,
        commission_rate: float = BacktestConstants.DEFAULT_COMMISSION_RATE,
        slippage: float = BacktestConstants.DEFAULT_SLIPPAGE,
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.commission_rate = commission_rate
        self.slippage = slippage

        self.positions: dict[str, Position] = {}
        self.orders: list[Order] = []
        self.trades: list[Trade] = []

        self._order_id_counter = 0
        self._trade_id_counter = 0

    def submit_order(
        self,
        order: Order,
        current_price: float,
        timestamp: datetime
    ) -> Trade | None:
        """
        提交订单

        Args:
            order: 订单
            current_price: 当前市场价格
            timestamp: 时间戳

        Returns:
            成交记录（如果成交）
        """
        # 生成订单ID
        self._order_id_counter += 1
        order.order_id = f"ORDER_{self._order_id_counter:06d}"
        order.timestamp = timestamp

        # 检查订单是否可以成交
        fill_price = self._get_fill_price(order, current_price)

        if fill_price is None:
            # 限价单未触发
            order.status = OrderStatus.PENDING
            self.orders.append(order)
            return None

        # 检查资金是否充足
        if order.side == OrderSide.BUY:
            commission = fill_price * order.quantity * self.commission_rate
            required_cash = fill_price * order.quantity + commission

            if required_cash > self.cash:
                order.status = OrderStatus.REJECTED
                self.orders.append(order)
                raise ValueError(
                    f"资金不足：需要 {required_cash:.2f}，可用 {self.cash:.2f}"
                )

        # 计算滑点
        if order.order_type == OrderType.MARKET:
            slippage_amount = abs(fill_price - current_price)
        else:
            slippage_amount = 0.0

        # 计算手续费
        commission = fill_price * order.quantity * self.commission_rate

        # 执行成交
        self._trade_id_counter += 1
        trade = Trade(
            trade_id=f"TRADE_{self._trade_id_counter:06d}",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            commission=commission,
            slippage=slippage_amount,
            timestamp=timestamp,
        )

        # 更新订单状态
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.filled_price = fill_price
        order.commission = commission
        self.orders.append(order)

        # 更新持仓
        self._update_position(trade)

        # 更新现金
        if order.side == OrderSide.BUY:
            self.cash -= (fill_price * order.quantity + commission)
        else:
            self.cash += (fill_price * order.quantity - commission)

        self.trades.append(trade)
        return trade

    def _get_fill_price(self, order: Order, current_price: float) -> float | None:
        """
        获取成交价格

        Args:
            order: 订单
            current_price: 当前价格

        Returns:
            成交价格（如果可以成交）
        """
        match order.order_type:
            case OrderType.MARKET:
                # 市价单：立即成交，使用当前价格+滑点
                if order.side == OrderSide.BUY:
                    return current_price * (1 + self.slippage)
                return current_price * (1 - self.slippage)

            case OrderType.LIMIT:
                # 限价单：价格符合条件才成交
                if order.price is None:
                    return None

                if order.side == OrderSide.BUY:
                    # 买入限价单：当前价 <= 限价
                    return order.price if current_price <= order.price else None

                # 卖出限价单：当前价 >= 限价
                return order.price if current_price >= order.price else None

            case OrderType.STOP:
                # 止损单：价格触发条件后以市价成交
                if order.stop_price is None:
                    return None

                triggered = (
                    (order.side == OrderSide.BUY and current_price >= order.stop_price) or
                    (order.side == OrderSide.SELL and current_price <= order.stop_price)
                )

                if not triggered:
                    return None

                # 触发后以市价成交
                if order.side == OrderSide.BUY:
                    return current_price * (1 + self.slippage)
                return current_price * (1 - self.slippage)

        return None

    def _update_position(self, trade: Trade) -> None:
        """
        更新持仓

        Args:
            trade: 成交记录
        """
        symbol = trade.symbol

        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol)

        pos = self.positions[symbol]

        if trade.side == OrderSide.BUY:
            # 买入
            if pos.quantity < 0:
                # 当前持有空头，部分或全部平仓
                close_qty = min(abs(pos.quantity), trade.quantity)
                pos.realized_pnl += close_qty * (pos.avg_price - trade.price)
                pos.quantity += trade.quantity

                if pos.quantity > 0:
                    # 平空后还有多头
                    pos.avg_price = trade.price
            else:
                # 增加多头
                if pos.quantity == 0:
                    pos.avg_price = trade.price
                else:
                    pos.avg_price = (
                        (pos.avg_price * pos.quantity + trade.price * trade.quantity) /
                        (pos.quantity + trade.quantity)
                    )
                pos.quantity += trade.quantity
        else:
            # 卖出
            if pos.quantity > 0:
                # 当前持有多头，部分或全部平仓
                close_qty = min(pos.quantity, trade.quantity)
                pos.realized_pnl += close_qty * (trade.price - pos.avg_price)
                pos.quantity -= trade.quantity

                if pos.quantity < 0:
                    # 平多后还有空头
                    pos.avg_price = trade.price
            else:
                # 增加空头
                if pos.quantity == 0:
                    pos.avg_price = trade.price
                else:
                    pos.avg_price = (
                        (pos.avg_price * abs(pos.quantity) + trade.price * trade.quantity) /
                        (abs(pos.quantity) + trade.quantity)
                    )
                pos.quantity -= trade.quantity

    def update_prices(self, prices: dict[str, float]) -> None:
        """
        更新持仓的当前价格

        Args:
            prices: 品种代码 -> 当前价格
        """
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].current_price = price

    def get_total_value(self) -> float:
        """获取总资产价值"""
        position_value = sum(pos.market_value for pos in self.positions.values())
        return self.cash + position_value

    def get_total_pnl(self) -> float:
        """获取总盈亏"""
        return self.get_total_value() - self.initial_capital

    def get_position(self, symbol: str) -> Position | None:
        """获取持仓"""
        return self.positions.get(symbol)

    def get_all_positions(self) -> list[Position]:
        """获取所有持仓"""
        return list(self.positions.values())

    def get_equity_curve_point(self, timestamp: datetime) -> dict[str, float]:
        """
        获取权益曲线点

        Args:
            timestamp: 时间戳

        Returns:
            {"timestamp": ..., "equity": ..., "cash": ..., "position_value": ...}
        """
        position_value = sum(pos.market_value for pos in self.positions.values())
        equity = self.cash + position_value

        return {
            "timestamp": timestamp,
            "equity": equity,
            "cash": self.cash,
            "position_value": position_value,
        }
