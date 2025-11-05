"""
AI策略代理 - 单个策略实例
包含策略隔离、账户管理、决策执行等功能
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from ..decision_engine.futures_engine import FuturesDecisionEngine
from ..llm_client.openai_client import AsyncOpenAIClient

logger = logging.getLogger(__name__)

class AgentStatus(Enum):
    """代理状态"""
    IDLE = "idle"
    THINKING = "thinking"
    PLACING_ORDER = "placing_order"
    MANAGING_POSITION = "managing_position"
    ERROR = "error"
    PAUSED = "paused"

class OrderType(Enum):
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

class OrderDirection(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"

@dataclass
class StrategyConfig:
    """策略配置"""
    strategy_id: str
    strategy_name: str
    initial_capital: float
    max_position_size: int
    max_positions: int
    leverage: float
    risk_per_trade: float
    decision_interval: int  # 决策间隔（秒）
    confidence_threshold: float
    ai_model: str = "gpt-4"
    ai_temperature: float = 0.1
    is_active: bool = True
    manual_override: bool = False

    # 新增：品种池配置
    commodity_pool: Optional[str] = None  # 品种池名称 (如 "black", "metal", "all")
    max_symbols: int = 3  # AI可选择的最大品种数
    selection_mode: str = "ai_driven"  # ai_driven 或 manual
    description: Optional[str] = None

    # 向后兼容：支持直接指定品种列表
    symbols: Optional[List[str]] = None
    commodities: Optional[List[str]] = None  # 品种代码列表

@dataclass
class Position:
    """持仓信息"""
    symbol: str
    quantity: int
    entry_price: float
    entry_time: datetime
    current_price: float
    unrealized_pnl: float
    leverage: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy_id: str = ""

@dataclass
class Trade:
    """交易记录"""
    trade_id: str
    strategy_id: str
    symbol: str
    direction: OrderDirection
    order_type: OrderType
    quantity: int
    price: float
    timestamp: datetime
    commission: float
    pnl: float = 0.0
    status: str = "executed"

class StrategyAgent:
    """AI策略代理"""

    def __init__(
        self,
        config: StrategyConfig,
        db_manager: Optional[Any] = None,
        market_data_manager: Optional[Any] = None
    ):
        """初始化策略代理

        Args:
            config: 策略配置
            db_manager: 数据库管理器
            market_data_manager: 市场数据管理器
        """
        self.config = config
        self.db_manager = db_manager
        self.market_data_manager = market_data_manager

        # 状态管理
        self.status = AgentStatus.IDLE
        self.start_time = datetime.now()
        self.last_decision_time = None
        self.error_count = 0

        # 账户管理
        self.account_value = config.initial_capital
        self.cash_available = config.initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []

        # 性能指标
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.max_drawdown = 0.0
        self.peak_value = config.initial_capital

        # AI决策引擎
        self.decision_engine = FuturesDecisionEngine(
            db_manager=db_manager,
            market_data_manager=market_data_manager
        )

        logger.info(f"策略代理初始化完成: {config.strategy_name} ({config.strategy_id})")

    async def start(self) -> None:
        """启动策略代理"""
        if not self.config.is_active:
            logger.info(f"策略 {self.config.strategy_id} 未激活，跳过启动")
            return

        logger.info(f"启动策略代理: {self.config.strategy_name}")
        self.status = AgentStatus.IDLE

        # 主循环
        try:
            while self.config.is_active and self.status != AgentStatus.ERROR:
                await self._trading_loop()
                await asyncio.sleep(self.config.decision_interval)

        except Exception as e:
            logger.error(f"策略代理 {self.config.strategy_id} 运行出错: {e}")
            self.status = AgentStatus.ERROR
            self.error_count += 1

    async def stop(self) -> None:
        """停止策略代理"""
        logger.info(f"停止策略代理: {self.config.strategy_name}")
        self.config.is_active = False
        self.status = AgentStatus.IDLE

        # 平仓所有持仓
        if self.positions:
            await self._close_all_positions("策略停止")

    async def pause(self) -> None:
        """暂停策略代理"""
        logger.info(f"暂停策略代理: {self.config.strategy_name}")
        self.status = AgentStatus.PAUSED

    async def resume(self) -> None:
        """恢复策略代理"""
        logger.info(f"恢复策略代理: {self.config.strategy_name}")
        self.status = AgentStatus.IDLE

    async def _trading_loop(self) -> None:
        """交易主循环"""
        if self.status == AgentStatus.PAUSED:
            return

        try:
            self.status = AgentStatus.THINKING
            self.last_decision_time = datetime.now()

            # 更新账户价值
            await self._update_account_value()

            # 检查风险限制
            if not await self._check_risk_limits():
                self.status = AgentStatus.IDLE
                return

            # 为每个关注的品种生成决策
            for symbol in self.config.symbols:
                try:
                    await self._process_symbol(symbol)
                except Exception as e:
                    logger.error(f"处理品种 {symbol} 时出错: {e}")
                    continue

            self.status = AgentStatus.IDLE

        except Exception as e:
            logger.error(f"交易循环出错: {e}")
            self.status = AgentStatus.ERROR
            self.error_count += 1

    async def _process_symbol(self, symbol: str) -> None:
        """处理单个品种"""
        # 获取当前持仓
        current_position = self.positions.get(symbol)
        positions_list = [asdict(pos) for pos in self.positions.values()] if current_position else []

        # 构建账户信息
        account_info = {
            "strategy_id": self.config.strategy_id,
            "cash_available": self.cash_available,
            "account_value": self.account_value,
            "total_trades": self.total_trades,
            "win_rate": self.winning_trades / max(self.total_trades, 1),
            "return_pct": (self.account_value - self.config.initial_capital) / self.config.initial_capital,
            "max_drawdown": self.max_drawdown,
            "leverage": self.config.leverage,
        }

        # 获取AI决策
        decision = await self.decision_engine.get_decision(
            symbol=symbol,
            account_info=account_info,
            current_positions=positions_list
        )

        if decision:
            await self._execute_decision(symbol, decision)

    async def _execute_decision(self, symbol: str, decision: Dict[str, Any]) -> None:
        """执行AI决策"""
        try:
            action = decision.get("action", "hold")
            quantity = decision.get("quantity", 0)
            price = decision.get("price", 0)
            confidence = decision.get("confidence", 0)

            # 检查置信度阈值
            if confidence < self.config.confidence_threshold:
                logger.info(f"决策置信度 {confidence:.2f} 低于阈值 {self.config.confidence_threshold}，跳过执行")
                return

            # 检查手动覆盖
            if self.config.manual_override:
                logger.info(f"策略 {self.config.strategy_id} 处于手动覆盖模式，跳过AI决策")
                return

            self.status = AgentStatus.PLACING_ORDER

            current_position = self.positions.get(symbol)

            if action == "buy" and quantity > 0:
                await self._execute_buy(symbol, quantity, price, decision)
            elif action == "sell" and quantity > 0:
                await self._execute_sell(symbol, quantity, price, decision)
            elif action == "hold":
                await self._manage_position(symbol, decision)
            else:
                logger.warning(f"未知决策类型: {action}")

        except Exception as e:
            logger.error(f"执行决策时出错: {e}")
            self.status = AgentStatus.IDLE

    async def _execute_buy(self, symbol: str, quantity: int, price: float, decision: Dict[str, Any]) -> None:
        """执行买入操作"""
        # 计算需要的保证金
        margin_needed = quantity * price * self.config.leverage * 0.1  # 假设保证金比例10%

        if margin_needed > self.cash_available:
            logger.warning(f"资金不足，需要 {margin_needed:.2f}，可用 {self.cash_available:.2f}")
            return

        # 检查最大持仓限制
        if quantity > self.config.max_position_size:
            quantity = self.config.max_position_size
            logger.info(f"调整下单数量至最大限制: {quantity}")

        # 生成交易记录
        trade = Trade(
            trade_id=f"{self.config.strategy_id}_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_buy",
            strategy_id=self.config.strategy_id,
            symbol=symbol,
            direction=OrderDirection.BUY,
            order_type=OrderType.LIMIT if price > 0 else OrderType.MARKET,
            quantity=quantity,
            price=price,
            timestamp=datetime.now(),
            commission=quantity * 0.1  # 假设手续费
        )

        # 更新持仓
        current_position = self.positions.get(symbol)
        if current_position is None:
            # 新建持仓
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                entry_price=price,
                entry_time=datetime.now(),
                current_price=price,
                unrealized_pnl=0.0,
                leverage=self.config.leverage,
                stop_loss=decision.get("stop_loss"),
                take_profit=decision.get("take_profit"),
                strategy_id=self.config.strategy_id
            )
        else:
            # 加仓
            total_cost = current_position.quantity * current_position.entry_price + quantity * price
            total_quantity = current_position.quantity + quantity
            avg_price = total_cost / total_quantity

            current_position.quantity = total_quantity
            current_position.entry_price = avg_price
            current_position.stop_loss = decision.get("stop_loss")
            current_position.take_profit = decision.get("take_profit")

        # 更新现金
        self.cash_available -= margin_needed + trade.commission

        # 记录交易
        self.trades.append(trade)
        self.total_trades += 1

        # 记录到数据库
        await self._record_trade(trade)

        logger.info(f"执行买入: {symbol} {quantity}手 @ {price:.2f}, 决策置信度: {decision.get('confidence', 0):.2f}")

    async def _execute_sell(self, symbol: str, quantity: int, price: float, decision: Dict[str, Any]) -> None:
        """执行卖出操作"""
        current_position = self.positions.get(symbol)
        if current_position is None or current_position.quantity <= 0:
            logger.warning(f"无持仓可卖: {symbol}")
            return

        # 调整卖出数量
        if quantity > current_position.quantity:
            quantity = current_position.quantity

        # 生成交易记录
        trade = Trade(
            trade_id=f"{self.config.strategy_id}_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_sell",
            strategy_id=self.config.strategy_id,
            symbol=symbol,
            direction=OrderDirection.SELL,
            order_type=OrderType.LIMIT if price > 0 else OrderType.MARKET,
            quantity=quantity,
            price=price,
            timestamp=datetime.now(),
            commission=quantity * 0.1
        )

        # 计算盈亏
        pnl = (price - current_position.entry_price) * quantity * self.config.leverage
        trade.pnl = pnl - trade.commission

        # 更新持仓
        if quantity >= current_position.quantity:
            # 平仓
            del self.positions[symbol]
            logger.info(f"平仓: {symbol} {quantity}手 @ {price:.2f}, 盈亏: {pnl:.2f}")
        else:
            # 部分平仓
            current_position.quantity -= quantity
            logger.info(f"减仓: {symbol} {quantity}手 @ {price:.2f}, 盈亏: {pnl:.2f}")

        # 更新现金和账户价值
        margin_returned = quantity * price * self.config.leverage * 0.1  # 返回保证金
        self.cash_available += margin_returned + pnl - trade.commission

        # 更新统计
        self.total_trades += 1
        self.total_pnl += pnl
        if pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

        # 记录交易
        self.trades.append(trade)
        await self._record_trade(trade)

        logger.info(f"执行卖出: {symbol} {quantity}手 @ {price:.2f}, 实现盈亏: {pnl:.2f}")

    async def _manage_position(self, symbol: str, decision: Dict[str, Any]) -> None:
        """管理现有持仓"""
        current_position = self.positions.get(symbol)
        if current_position is None:
            return

        # 更新止损止盈
        if "stop_loss" in decision:
            current_position.stop_loss = decision["stop_loss"]
        if "take_profit" in decision:
            current_position.take_profit = decision["take_profit"]

        # 检查是否需要止损止盈
        current_price = decision.get("current_price", current_position.current_price)
        current_position.current_price = current_price
        current_position.unrealized_pnl = (current_price - current_position.entry_price) * current_position.quantity * current_position.leverage

        # 止损检查
        if current_position.stop_loss and current_price <= current_position.stop_loss:
            await self._execute_sell(symbol, current_position.quantity, current_price, {"action": "sell", "reason": "止损"})

        # 止盈检查
        elif current_position.take_profit and current_price >= current_position.take_profit:
            await self._execute_sell(symbol, current_position.quantity, current_price, {"action": "sell", "reason": "止盈"})

    async def _update_account_value(self) -> None:
        """更新账户价值"""
        total_unrealized_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
        self.account_value = self.cash_available + total_unrealized_pnl

        # 更新最大回撤
        if self.account_value > self.peak_value:
            self.peak_value = self.account_value

        current_drawdown = (self.peak_value - self.account_value) / self.peak_value
        if current_drawdown > self.max_drawdown:
            self.max_drawdown = current_drawdown

    async def _check_risk_limits(self) -> bool:
        """检查风险限制"""
        # 检查最大回撤
        if self.max_drawdown > 0.15:  # 15%最大回撤
            logger.warning(f"最大回撤超限: {self.max_drawdown:.2%}")
            return False

        # 检查持仓数量限制
        if len(self.positions) >= self.config.max_positions:
            return False

        # 检查单品种持仓限制
        for position in self.positions.values():
            if position.quantity > self.config.max_position_size:
                logger.warning(f"单品种持仓超限: {position.symbol} {position.quantity}")
                return False

        return True

    async def _close_all_positions(self, reason: str = "策略停止") -> None:
        """平仓所有持仓"""
        for symbol, position in list(self.positions.items()):
            try:
                await self._execute_sell(
                    symbol,
                    position.quantity,
                    position.current_price,
                    {"action": "sell", "reason": reason}
                )
            except Exception as e:
                logger.error(f"平仓失败 {symbol}: {e}")

    async def _record_trade(self, trade: Trade) -> None:
        """记录交易到数据库"""
        try:
            if self.db_manager:
                await self.db_manager.record_trade(asdict(trade))
        except Exception as e:
            logger.error(f"记录交易到数据库失败: {e}")

    def get_status(self) -> Dict[str, Any]:
        """获取代理状态"""
        return {
            "strategy_id": self.config.strategy_id,
            "strategy_name": self.config.strategy_name,
            "status": self.status.value,
            "is_active": self.config.is_active,
            "account_value": self.account_value,
            "cash_available": self.cash_available,
            "positions_count": len(self.positions),
            "total_trades": self.total_trades,
            "win_rate": self.winning_trades / max(self.total_trades, 1),
            "total_pnl": self.total_pnl,
            "max_drawdown": self.max_drawdown,
            "return_pct": (self.account_value - self.config.initial_capital) / self.config.initial_capital,
            "error_count": self.error_count,
            "last_decision_time": self.last_decision_time.isoformat() if self.last_decision_time else None,
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds()
        }