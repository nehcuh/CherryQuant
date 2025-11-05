"""
多策略代理管理器
负责管理和协调多个AI策略代理的运行
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, asdict
import json
import os

from .strategy_agent import StrategyAgent, StrategyConfig, AgentStatus
from adapters.data_storage.database_manager import DatabaseManager

logger = logging.getLogger(__name__)

@dataclass
class PortfolioRiskConfig:
    """组合风险配置"""
    max_total_capital_usage: float = 0.8  # 最大总资金使用率
    max_correlation_threshold: float = 0.7  # 最大相关性阈值
    max_sector_concentration: float = 0.4  # 最大单一板块集中度
    portfolio_stop_loss: float = 0.1  # 组合止损比例
    daily_loss_limit: float = 0.05  # 每日亏损限制
    max_leverage_total: float = 3.0  # 总杠杆限制

class AgentManager:
    """多策略代理管理器"""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        market_data_manager: Optional[Any] = None,
        risk_config: Optional[PortfolioRiskConfig] = None
    ):
        """初始化代理管理器

        Args:
            db_manager: 数据库管理器
            market_data_manager: 市场数据管理器
            risk_config: 组合风险配置
        """
        self.db_manager = db_manager
        self.market_data_manager = market_data_manager
        self.risk_config = risk_config or PortfolioRiskConfig()

        # 代理管理
        self.agents: Dict[str, StrategyAgent] = {}
        self.active_agents: Set[str] = set()
        self.total_initial_capital = 0.0

        # 状态管理
        self.is_running = False
        self.start_time = datetime.now()
        self.last_risk_check = datetime.now()

        # 统计信息
        self.total_trades = 0
        self.total_pnl = 0.0
        self.portfolio_value = 0.0
        self.daily_pnl = 0.0
        self.daily_trades = 0

        logger.info("代理管理器初始化完成")

    async def load_strategies_from_config(self, config_file: str = "config/strategies.json") -> None:
        """从配置文件加载策略"""
        try:
            if not os.path.exists(config_file):
                logger.warning(f"策略配置文件不存在: {config_file}")
                return

            with open(config_file, 'r', encoding='utf-8') as f:
                strategies_data = json.load(f)

            # 加载品种池配置
            commodity_pools = strategies_data.get("commodity_pools", {})
            logger.info(f"加载了 {len(commodity_pools)} 个品种池配置")

            for strategy_data in strategies_data.get("strategies", []):
                # 解析品种池
                commodity_pool = strategy_data.get("commodity_pool")
                if commodity_pool:
                    if commodity_pool == "all":
                        # 全市场：汇总所有品种池
                        all_commodities = []
                        for pool in commodity_pools.values():
                            all_commodities.extend(pool.get("commodities", []))
                        strategy_data["commodities"] = list(set(all_commodities))
                        logger.info(f"策略 {strategy_data['strategy_id']} 使用全市场品种池: {len(strategy_data['commodities'])} 个品种")
                    elif commodity_pool in commodity_pools:
                        # 指定品种池
                        strategy_data["commodities"] = commodity_pools[commodity_pool].get("commodities", [])
                        logger.info(f"策略 {strategy_data['strategy_id']} 使用品种池 '{commodity_pool}': {commodity_pools[commodity_pool].get('name', '')}")
                    else:
                        logger.warning(f"未找到品种池 '{commodity_pool}'，策略 {strategy_data['strategy_id']} 将无可用品种")
                        strategy_data["commodities"] = []

                await self.add_strategy(StrategyConfig(**strategy_data))

            logger.info(f"从配置文件加载了 {len(strategies_data.get('strategies', []))} 个策略")

        except Exception as e:
            logger.error(f"加载策略配置失败: {e}")

    async def add_strategy(self, config: StrategyConfig) -> bool:
        """添加新策略"""
        try:
            if config.strategy_id in self.agents:
                logger.warning(f"策略ID已存在: {config.strategy_id}")
                return False

            # 创建策略代理
            agent = StrategyAgent(
                config=config,
                db_manager=self.db_manager,
                market_data_manager=self.market_data_manager
            )

            self.agents[config.strategy_id] = agent
            self.total_initial_capital += config.initial_capital

            logger.info(f"添加策略: {config.strategy_name} ({config.strategy_id})")
            return True

        except Exception as e:
            logger.error(f"添加策略失败: {e}")
            return False

    async def remove_strategy(self, strategy_id: str) -> bool:
        """移除策略"""
        try:
            if strategy_id not in self.agents:
                logger.warning(f"策略不存在: {strategy_id}")
                return False

            agent = self.agents[strategy_id]

            # 停止策略
            if agent.status != AgentStatus.IDLE:
                await agent.stop()

            # 从总资金中扣除
            self.total_initial_capital -= agent.config.initial_capital

            # 移除代理
            del self.agents[strategy_id]
            self.active_agents.discard(strategy_id)

            logger.info(f"移除策略: {strategy_id}")
            return True

        except Exception as e:
            logger.error(f"移除策略失败: {e}")
            return False

    async def start_all(self) -> None:
        """启动所有策略"""
        logger.info("启动所有策略代理")
        self.is_running = True

        # 启动每个策略代理
        tasks = []
        for strategy_id, agent in self.agents.items():
            if agent.config.is_active:
                self.active_agents.add(strategy_id)
                task = asyncio.create_task(agent.start())
                tasks.append(task)

        # 启动风险监控任务
        risk_monitor_task = asyncio.create_task(self._risk_monitor_loop())
        tasks.append(risk_monitor_task)

        # 启动状态更新任务
        status_update_task = asyncio.create_task(self._status_update_loop())
        tasks.append(status_update_task)

        # 等待所有任务完成
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"策略管理器运行出错: {e}")

    async def stop_all(self) -> None:
        """停止所有策略"""
        logger.info("停止所有策略代理")
        self.is_running = False

        # 停止每个策略代理
        for strategy_id, agent in self.agents.items():
            await agent.stop()

    async def start_strategy(self, strategy_id: str) -> bool:
        """启动单个策略"""
        if strategy_id not in self.agents:
            logger.error(f"策略不存在: {strategy_id}")
            return False

        agent = self.agents[strategy_id]
        if agent.config.is_active:
            self.active_agents.add(strategy_id)
            asyncio.create_task(agent.start())
            logger.info(f"启动策略: {strategy_id}")
            return True
        else:
            logger.warning(f"策略 {strategy_id} 未激活")
            return False

    async def stop_strategy(self, strategy_id: str) -> bool:
        """停止单个策略"""
        if strategy_id not in self.agents:
            logger.error(f"策略不存在: {strategy_id}")
            return False

        await self.agents[strategy_id].stop()
        self.active_agents.discard(strategy_id)
        logger.info(f"停止策略: {strategy_id}")
        return True

    async def pause_strategy(self, strategy_id: str) -> bool:
        """暂停策略"""
        if strategy_id not in self.agents:
            return False

        await self.agents[strategy_id].pause()
        logger.info(f"暂停策略: {strategy_id}")
        return True

    async def resume_strategy(self, strategy_id: str) -> bool:
        """恢复策略"""
        if strategy_id not in self.agents:
            return False

        await self.agents[strategy_id].resume()
        logger.info(f"恢复策略: {strategy_id}")
        return True

    async def _risk_monitor_loop(self) -> None:
        """风险监控循环"""
        while self.is_running:
            try:
                await self._check_portfolio_risk()
                await asyncio.sleep(60)  # 每分钟检查一次风险
            except Exception as e:
                logger.error(f"风险监控出错: {e}")
                await asyncio.sleep(30)

    async def _check_portfolio_risk(self) -> None:
        """检查组合风险"""
        try:
            # 更新组合统计
            await self._update_portfolio_stats()

            # 检查总资金使用率
            total_capital_usage = self._calculate_total_capital_usage()
            if total_capital_usage > self.risk_config.max_total_capital_usage:
                await self._handle_high_capital_usage(total_capital_usage)

            # 检查每日亏损限制
            if self.daily_pnl < -self.total_initial_capital * self.risk_config.daily_loss_limit:
                logger.warning(f"达到每日亏损限制，暂停所有策略")
                await self._emergency_stop_all("每日亏损限制")

            # 检查组合止损
            if self.portfolio_value < self.total_initial_capital * (1 - self.risk_config.portfolio_stop_loss):
                logger.warning(f"达到组合止损线，平仓所有策略")
                await self._emergency_stop_all("组合止损")

            # 检查板块集中度
            sector_concentration = self._calculate_sector_concentration()
            if sector_concentration > self.risk_config.max_sector_concentration:
                logger.warning(f"板块集中度过高: {sector_concentration:.2%}")
                await self._handle_high_sector_concentration(sector_concentration)

        except Exception as e:
            logger.error(f"风险检查出错: {e}")

    async def _status_update_loop(self) -> None:
        """状态更新循环"""
        while self.is_running:
            try:
                await self._update_portfolio_stats()

                # 记录状态到数据库
                if self.db_manager:
                    await self._record_portfolio_status()

                await asyncio.sleep(30)  # 每30秒更新一次状态

            except Exception as e:
                logger.error(f"状态更新出错: {e}")
                await asyncio.sleep(30)

    async def _update_portfolio_stats(self) -> None:
        """更新组合统计"""
        total_value = 0.0
        total_trades = 0
        total_pnl = 0.0
        winning_trades = 0

        for agent in self.agents.values():
            status = agent.get_status()
            total_value += status["account_value"]
            total_trades += status["total_trades"]
            total_pnl += status["total_pnl"]
            winning_trades += int(status["total_trades"] * status["win_rate"])

        self.portfolio_value = total_value
        self.total_trades = total_trades
        self.total_pnl = total_pnl

    def _calculate_total_capital_usage(self) -> float:
        """计算总资金使用率"""
        total_used = 0.0
        for agent in self.agents.values():
            status = agent.get_status()
            total_used += status["account_value"] - status["cash_available"]

        return total_used / max(self.total_initial_capital, 1)

    def _calculate_sector_concentration(self) -> float:
        """计算板块集中度"""
        sector_positions = {}
        total_positions = 0

        for agent in self.agents.values():
            for position in agent.positions.values():
                sector = self._get_symbol_sector(position.symbol)
                sector_positions[sector] = sector_positions.get(sector, 0) + position.quantity
                total_positions += position.quantity

        if total_positions == 0:
            return 0.0

        max_sector_positions = max(sector_positions.values()) if sector_positions else 0
        return max_sector_positions / total_positions

    def _get_symbol_sector(self, symbol: str) -> str:
        """获取品种所属板块"""
        # 简化的板块映射
        sector_mapping = {
            "rb": "黑色金属", "i": "黑色金属", "j": "黑色金属", "jm": "黑色金属",
            "cu": "有色金属", "al": "有色金属", "zn": "有色金属", "ni": "有色金属",
            "au": "贵金属", "ag": "贵金属",
            "a": "农产品", "m": "农产品", "c": "农产品", "y": "农产品",
        }

        commodity = symbol[:2].lower()
        return sector_mapping.get(commodity, "其他")

    async def _handle_high_capital_usage(self, usage: float) -> None:
        """处理高资金使用率"""
        logger.warning(f"资金使用率过高: {usage:.2%}")

        # 按收益率排序，暂停表现差的策略
        agent_performances = []
        for strategy_id, agent in self.agents.items():
            if strategy_id in self.active_agents:
                status = agent.get_status()
                performance = status["return_pct"]
                agent_performances.append((performance, strategy_id))

        agent_performances.sort()  # 升序排序，收益率低的在前

        # 暂停表现差的策略直到资金使用率降到安全水平
        for performance, strategy_id in agent_performances:
            if usage <= self.risk_config.max_total_capital_usage * 0.8:
                break
            await self.pause_strategy(strategy_id)
            # 重新计算使用率
            usage = self._calculate_total_capital_usage()

    async def _handle_high_sector_concentration(self, concentration: float) -> None:
        """处理高板块集中度"""
        # 找出集中度最高的板块中的策略
        sector_agents = {}
        for strategy_id, agent in self.agents.items():
            for position in agent.positions.values():
                sector = self._get_symbol_sector(position.symbol)
                if sector not in sector_agents:
                    sector_agents[sector] = []
                sector_agents[sector].append((strategy_id, position.quantity))

        # 找出数量最多的板块
        max_sector = max(sector_agents.keys(), key=lambda s: sum(q for _, q in sector_agents[s]))

        # 暂停该板块中部分策略
        sector_agent_list = sorted(
            [(s, q) for s, q in sector_agents[max_sector]],
            key=lambda x: x[1],
            reverse=True
        )

        for strategy_id, quantity in sector_agent_list:
            if concentration <= self.risk_config.max_sector_concentration * 0.8:
                break
            await self.pause_strategy(strategy_id)
            concentration = self._calculate_sector_concentration()

    async def _emergency_stop_all(self, reason: str) -> None:
        """紧急停止所有策略"""
        logger.error(f"紧急停止所有策略: {reason}")

        for agent in self.agents.values():
            await agent._close_all_positions(reason)
            await agent.stop()

        self.active_agents.clear()

    async def _record_portfolio_status(self) -> None:
        """记录组合状态到数据库"""
        try:
            portfolio_data = {
                "timestamp": datetime.now(),
                "portfolio_value": self.portfolio_value,
                "total_pnl": self.total_pnl,
                "daily_pnl": self.daily_pnl,
                "total_trades": self.total_trades,
                "active_strategies": len(self.active_agents),
                "total_strategies": len(self.agents),
                "capital_usage": self._calculate_total_capital_usage(),
                "sector_concentration": self._calculate_sector_concentration(),
            }

            if self.db_manager:
                await self.db_manager.record_portfolio_status(portfolio_data)

        except Exception as e:
            logger.error(f"记录组合状态失败: {e}")

    def get_portfolio_status(self) -> Dict[str, Any]:
        """获取组合状态"""
        agent_statuses = {sid: agent.get_status() for sid, agent in self.agents.items()}

        return {
            "manager_status": {
                "is_running": self.is_running,
                "start_time": self.start_time.isoformat(),
                "active_strategies": len(self.active_agents),
                "total_strategies": len(self.agents),
                "total_initial_capital": self.total_initial_capital,
                "portfolio_value": self.portfolio_value,
                "total_pnl": self.total_pnl,
                "daily_pnl": self.daily_pnl,
                "total_trades": self.total_trades,
                "capital_usage": self._calculate_total_capital_usage(),
                "sector_concentration": self._calculate_sector_concentration(),
                "portfolio_return": (self.portfolio_value - self.total_initial_capital) / max(self.total_initial_capital, 1),
            },
            "agents": agent_statuses,
            "risk_config": asdict(self.risk_config)
        }

    def get_strategy_details(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """获取策略详细信息"""
        if strategy_id not in self.agents:
            return None

        agent = self.agents[strategy_id]
        status = agent.get_status()

        # 添加持仓详情
        positions = []
        for position in agent.positions.values():
            positions.append({
                "symbol": position.symbol,
                "quantity": position.quantity,
                "entry_price": position.entry_price,
                "current_price": position.current_price,
                "unrealized_pnl": position.unrealized_pnl,
                "leverage": position.leverage,
                "stop_loss": position.stop_loss,
                "take_profit": position.take_profit,
                "entry_time": position.entry_time.isoformat(),
            })

        # 添加最近交易记录
        recent_trades = []
        for trade in agent.trades[-10:]:  # 最近10笔交易
            recent_trades.append({
                "trade_id": trade.trade_id,
                "symbol": trade.symbol,
                "direction": trade.direction.value,
                "order_type": trade.order_type.value,
                "quantity": trade.quantity,
                "price": trade.price,
                "timestamp": trade.timestamp.isoformat(),
                "pnl": trade.pnl,
                "commission": trade.commission,
            })

        status.update({
            "config": asdict(agent.config),
            "positions": positions,
            "recent_trades": recent_trades,
        })

        return status