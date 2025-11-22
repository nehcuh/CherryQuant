"""
CherryQuant AI期货交易策略
基于vn.py框架的AI驱动交易策略
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from vnpy_ctastrategy import CtaTemplate, StopOrder, BarGenerator, ArrayManager
from vnpy.trader.object import TickData, BarData, OrderData, TradeData, PositionData, AccountData, ContractData
from vnpy.trader.constant import Direction, Status, Offset

from cherryquant.ai.decision_engine.futures_engine import FuturesDecisionEngine

logger = logging.getLogger(__name__)

class CherryQuantStrategy(CtaTemplate):
    """CherryQuant AI期货交易策略"""

    strategy_name = "CherryQuant"
    vt_symbol = "rb2501.SHFE"  # 默认螺纹钢主力合约

    # 参数定义
    decision_interval = 300      # 决策间隔（秒）
    max_position_size = 10       # 最大持仓手数
    default_leverage = 5         # 默认杠杆
    risk_per_trade = 0.02        # 每笔交易风险比例

    # 变量定义
    last_decision_time = 0       # 上次决策时间
    active_orders = []           # 活动订单
    decision_engine = None       # AI决策引擎

    parameters = [
        "decision_interval",
        "max_position_size",
        "default_leverage",
        "risk_per_trade"
    ]

    variables = [
        "last_decision_time",
        "active_orders"
    ]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """初始化策略"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        # 初始化AI决策引擎
        self.decision_engine = FuturesDecisionEngine()

        # K线生成器和数组管理器
        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager(size=100)

        # 当前持仓信息
        self.current_position = 0  # 当前持仓手数
        self.avg_price = 0        # 持仓均价

        # 策略状态
        self.last_decision = None  # 上次的AI决策
        self.trading_active = False  # 交易是否激活

        logger.info(f"CherryQuant策略初始化完成: {strategy_name} - {vt_symbol}")

    def on_init(self):
        """策略初始化"""
        self.write_log("策略初始化")

        # 初始化AI决策引擎
        asyncio.create_task(self._init_ai_engine())

        # 加载历史数据
        self.load_bar(10)

    async def _init_ai_engine(self):
        """异步初始化AI引擎"""
        try:
            # 测试AI连接
            if await self.decision_engine.test_connection():
                self.write_log("AI决策引擎连接成功")
                self.trading_active = True
            else:
                self.write_log("AI决策引擎连接失败，策略将暂停交易")
                self.trading_active = False
        except Exception as e:
            self.write_log(f"AI引擎初始化错误: {e}")
            self.trading_active = False

    def on_start(self):
        """策略启动"""
        self.write_log("策略启动")
        self.last_decision_time = datetime.now().timestamp()

    def on_stop(self):
        """策略停止"""
        self.write_log("策略停止")
        self.cancel_all()

    def on_tick(self, tick: TickData):
        """Tick数据更新"""
        # 这里可以添加tick级别的逻辑
        pass

    def on_bar(self, bar: BarData):
        """K线数据更新"""
        # 更新K线数据
        self.am.update_bar(bar)

        # 检查是否需要做出新的决策
        current_time = datetime.now().timestamp()
        if (current_time - self.last_decision_time >= self.decision_interval
            and self.trading_active):

            # 异步获取AI决策
            asyncio.create_task(self._make_ai_decision(bar))

        # 更新持仓信息
        self._update_position_info()

    async def _make_ai_decision(self, bar: BarData):
        """获取AI交易决策"""
        try:
            self.write_log(f"正在获取AI决策... 当前价格: {bar.close_price}")

            # 构造账户信息
            account_info = self._get_account_info()

            # 构造持仓信息
            positions_info = self._get_positions_info()

            # 获取AI决策
            decision = await self.decision_engine.get_decision(
                symbol=self.vt_symbol.split('.')[0],  # 去掉交易所后缀
                account_info=account_info,
                current_positions=positions_info
            )

            if decision:
                self.last_decision = decision
                self.last_decision_time = datetime.now().timestamp()

                # 执行AI决策
                self._execute_decision(decision, bar.close_price)
            else:
                self.write_log("AI决策获取失败")

        except Exception as e:
            self.write_log(f"AI决策过程错误: {e}")

    def _execute_decision(self, decision: dict[str, Any], current_price: float):
        """执行AI交易决策"""
        try:
            signal = decision.get("signal")
            quantity = decision.get("quantity", 0)
            leverage = decision.get("leverage", self.default_leverage)
            confidence = decision.get("confidence", 0)
            justification = decision.get("justification", "")

            self.write_log(f"AI决策: {signal}, 数量: {quantity}, 杠杆: {leverage}, 置信度: {confidence}")
            self.write_log(f"决策理由: {justification}")

            # 风险检查
            if confidence < 0.3:
                self.write_log("AI置信度过低，跳过此交易")
                return

            # 调整交易数量（基于风险控制）
            adjusted_quantity = self._adjust_position_size(quantity, confidence, leverage)
            if adjusted_quantity <= 0:
                self.write_log("风险调整后交易数量为0，跳过交易")
                return

            # 执行交易信号
            if signal == "buy_to_enter":
                self._execute_buy(current_price, adjusted_quantity, decision)
            elif signal == "sell_to_enter":
                self._execute_sell(current_price, adjusted_quantity, decision)
            elif signal == "close":
                self._execute_close(current_price, decision)
            elif signal == "hold":
                self.write_log("AI信号: 持仓观望")

        except Exception as e:
            self.write_log(f"执行AI决策错误: {e}")

    def _execute_buy(self, price: float, quantity: int, decision: dict[str, Any]):
        """执行买入开仓"""
        if self.current_position >= 0:  # 没有空头持仓
            # 开多仓
            order_id = self.buy(price, quantity)
            if order_id:
                self.write_log(f"开多仓委托: {quantity}手 @ {price}")
                self._set_stop_targets(decision, Direction.LONG, order_id)

    def _execute_sell(self, price: float, quantity: int, decision: dict[str, Any]):
        """执行卖出开仓"""
        if self.current_position <= 0:  # 没有多头持仓
            # 开空仓
            order_id = self.short(price, quantity)
            if order_id:
                self.write_log(f"开空仓委托: {quantity}手 @ {price}")
                self._set_stop_targets(decision, Direction.SHORT, order_id)

    def _execute_close(self, price: float, decision: dict[str, Any]):
        """执行平仓"""
        if self.current_position > 0:
            # 平多仓
            order_id = self.sell(price, abs(self.current_position))
            if order_id:
                self.write_log(f"平多仓委托: {abs(self.current_position)}手 @ {price}")
        elif self.current_position < 0:
            # 平空仓
            order_id = self.cover(price, abs(self.current_position))
            if order_id:
                self.write_log(f"平空仓委托: {abs(self.current_position)}手 @ {price}")

    def _set_stop_targets(self, decision: dict[str, Any], direction: Direction, order_id: str):
        """设置止损止盈目标"""
        try:
            profit_target = decision.get("profit_target", 0)
            stop_loss = decision.get("stop_loss", 0)
            invalidation_condition = decision.get("invalidation_condition", "")

            if profit_target > 0 and stop_loss > 0:
                # 这里可以设置vn.py的止损止盈订单
                # 由于vn.py的CTP接口限制，暂时记录到策略变量中
                self.write_log(f"设置止损止盈目标: 止损 {stop_loss}, 止盈 {profit_target}")
                self.write_log(f"失效条件: {invalidation_condition}")

        except Exception as e:
            self.write_log(f"设置止损止盈错误: {e}")

    def _adjust_position_size(self, ai_quantity: int, confidence: float, leverage: int) -> int:
        """基于风险和置信度调整交易数量"""
        try:
            # 基础风险调整
            risk_adjusted = ai_quantity * confidence

            # 杠杆调整
            leverage_adjusted = risk_adjusted * (leverage / self.default_leverage)

            # 最大持仓限制
            max_allowed = self.max_position_size - abs(self.current_position)

            # 最终调整
            final_quantity = min(int(leverage_adjusted), max_allowed)
            final_quantity = max(0, final_quantity)

            return final_quantity

        except Exception as e:
            self.write_log(f"仓位调整错误: {e}")
            return 0

    def _get_account_info(self) -> dict[str, Any]:
        """获取账户信息"""
        try:
            # 这里应该从vn.py获取真实的账户信息
            # 暂时返回模拟数据
            return {
                "return_pct": 0.0,  # 总收益率
                "win_rate": 0.0,    # 胜率
                "cash_available": 100000.0,  # 可用资金
                "account_value": 100000.0    # 账户总值
            }
        except Exception as e:
            logger.error(f"获取账户信息错误: {e}")
            return {
                "return_pct": 0.0,
                "win_rate": 0.0,
                "cash_available": 100000.0,
                "account_value": 100000.0
            }

    def _get_positions_info(self) -> list[dict[str, Any]]:
        """获取持仓信息"""
        try:
            positions = []

            if self.current_position != 0:
                positions.append({
                    "symbol": self.vt_symbol.split('.')[0],
                    "quantity": abs(self.current_position),
                    "entry_price": self.avg_price,
                    "current_price": self.bar.close_price if self.bar else 0,
                    "unrealized_pnl": self._calculate_unrealized_pnl(),
                    "leverage": self.default_leverage,
                    "profit_target": 0,  # 从last_decision中获取
                    "stop_loss": 0,     # 从last_decision中获取
                    "invalidation_condition": ""
                })

            return positions

        except Exception as e:
            logger.error(f"获取持仓信息错误: {e}")
            return []

    def _calculate_unrealized_pnl(self) -> float:
        """计算未实现盈亏"""
        try:
            if self.current_position == 0 or not self.bar:
                return 0.0

            current_price = self.bar.close_price
            if self.current_position > 0:
                return (current_price - self.avg_price) * self.current_position
            else:
                return (self.avg_price - current_price) * abs(self.current_position)

        except Exception as e:
            logger.error(f"计算未实现盈亏错误: {e}")
            return 0.0

    def _update_position_info(self):
        """更新持仓信息"""
        try:
            # 这里应该从vn.py获取真实持仓信息
            # 暂时使用模拟逻辑
            pass
        except Exception as e:
            logger.error(f"更新持仓信息错误: {e}")

    def on_order(self, order: OrderData):
        """订单状态更新"""
        self.write_log(f"订单更新: {order.orderid} - {order.status.value} @ {order.price}")

    def on_trade(self, trade: TradeData):
        """成交回报"""
        self.write_log(f"成交回报: {trade.vt_symbol} {trade.direction.value} {trade.volume}手 @ {trade.price}")

        # 更新持仓信息
        if trade.direction == Direction.LONG:
            self.current_position += trade.volume
        else:
            self.current_position -= trade.volume

        # 更新持仓均价（简化计算）
        if self.current_position != 0:
            total_cost = self.avg_price * (self.current_position - trade.volume) + trade.price * trade.volume
            self.avg_price = total_cost / self.current_position

    def on_stop_order(self, stop_order: StopOrder):
        """止损订单更新"""
        self.write_log(f"止损订单更新: {stop_order.stop_orderid}")
