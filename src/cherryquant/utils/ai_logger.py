"""
AI交易日志系统
专门用于记录AI决策、交易活动和策略性能的详细日志
"""

import json
import logging
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from dataclasses import dataclass, asdict
from enum import Enum
import aiofiles

class LogLevel(Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class LogCategory(Enum):
    """日志类别"""
    AI_DECISION = "ai_decision"
    TRADE_EXECUTION = "trade_execution"
    POSITION_MANAGEMENT = "position_management"
    RISK_MANAGEMENT = "risk_management"
    STRATEGY_PERFORMANCE = "strategy_performance"
    SYSTEM_STATUS = "system_status"
    ERROR = "error"

@dataclass
class AIDecisionLog:
    """AI决策日志"""
    timestamp: datetime
    strategy_id: str
    strategy_name: str
    symbol: str
    action: str
    quantity: int
    price: float
    confidence: float
    reasoning: str
    market_data: dict[str, Any]
    technical_indicators: dict[str, Any]
    risk_factors: list[str]
    execution_result: str | None = None

@dataclass
class TradeExecutionLog:
    """交易执行日志"""
    timestamp: datetime
    strategy_id: str
    trade_id: str
    symbol: str
    direction: str
    order_type: str
    quantity: int
    price: float
    commission: float
    execution_time: float
    status: str
    error_message: str | None = None

@dataclass
class PositionLog:
    """持仓管理日志"""
    timestamp: datetime
    strategy_id: str
    symbol: str
    action: str  # open, close, modify
    quantity: int
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    stop_loss: float | None
    take_profit: float | None

@dataclass
class RiskEventLog:
    """风险事件日志"""
    timestamp: datetime
    strategy_id: str
    event_type: str
    severity: str
    description: str
    current_capital_usage: float
    current_drawdown: float
    position_correlation: float
    action_taken: str

class AITradingLogger:
    """AI交易日志管理器"""

    def __init__(
        self,
        log_dir: str = "logs",
        enable_file_logging: bool = True,
        enable_database_logging: bool = True,
        db_manager: Any | None = None
    ):
        """初始化AI交易日志管理器

        Args:
            log_dir: 日志目录
            enable_file_logging: 是否启用文件日志
            enable_database_logging: 是否启用数据库日志
            db_manager: 数据库管理器
        """
        self.log_dir = Path(log_dir)
        self.enable_file_logging = enable_file_logging
        self.enable_database_logging = enable_database_logging
        self.db_manager = db_manager

        # 创建日志目录
        self.log_dir.mkdir(exist_ok=True)
        (self.log_dir / "ai_decisions").mkdir(exist_ok=True)
        (self.log_dir / "trades").mkdir(exist_ok=True)
        (self.log_dir / "positions").mkdir(exist_ok=True)
        (self.log_dir / "risks").mkdir(exist_ok=True)
        (self.log_dir / "performance").mkdir(exist_ok=True)

        # 日志队列和缓冲
        self.log_queue: list[dict[str, Any]] = []
        self.batch_size = 100
        self.flush_interval = 60  # 60秒

        # 启动后台任务
        self._running = False
        self._flush_task: asyncio.Task | None = None

    async def start(self) -> None:
        """启动日志系统"""
        self._running = True
        self._flush_task = asyncio.create_task(self._background_flush())
        logging.info("AI交易日志系统已启动")

    async def stop(self) -> None:
        """停止日志系统"""
        self._running = False
        if self._flush_task:
            await self._flush_task
        await self._flush_logs()  # 最后一次刷新
        logging.info("AI交易日志系统已停止")

    async def log_ai_decision(self, decision_log: AIDecisionLog) -> None:
        """记录AI决策"""
        try:
            log_entry = {
                "category": LogCategory.AI_DECISION.value,
                "timestamp": decision_log.timestamp.isoformat(),
                "data": asdict(decision_log)
            }

            # 添加到队列
            self.log_queue.append(log_entry)

            # 文件日志
            if self.enable_file_logging:
                await self._write_to_file(
                    "ai_decisions",
                    f"{decision_log.strategy_id}_{decision_log.timestamp.strftime('%Y%m%d')}.jsonl",
                    log_entry
                )

            # 数据库日志
            if self.enable_database_logging and self.db_manager:
                await self._write_to_database_ai_decision(decision_log)

        except Exception as e:
            logging.error(f"记录AI决策失败: {e}")

    async def log_trade_execution(self, trade_log: TradeExecutionLog) -> None:
        """记录交易执行"""
        try:
            log_entry = {
                "category": LogCategory.TRADE_EXECUTION.value,
                "timestamp": trade_log.timestamp.isoformat(),
                "data": asdict(trade_log)
            }

            # 添加到队列
            self.log_queue.append(log_entry)

            # 文件日志
            if self.enable_file_logging:
                await self._write_to_file(
                    "trades",
                    f"{trade_log.strategy_id}_{trade_log.timestamp.strftime('%Y%m%d')}.jsonl",
                    log_entry
                )

            # 数据库日志
            if self.enable_database_logging and self.db_manager:
                await self._write_to_database_trade(trade_log)

        except Exception as e:
            logging.error(f"记录交易执行失败: {e}")

    async def log_position_change(self, position_log: PositionLog) -> None:
        """记录持仓变化"""
        try:
            log_entry = {
                "category": LogCategory.POSITION_MANAGEMENT.value,
                "timestamp": position_log.timestamp.isoformat(),
                "data": asdict(position_log)
            }

            # 添加到队列
            self.log_queue.append(log_entry)

            # 文件日志
            if self.enable_file_logging:
                await self._write_to_file(
                    "positions",
                    f"{position_log.strategy_id}_{position_log.timestamp.strftime('%Y%m%d')}.jsonl",
                    log_entry
                )

        except Exception as e:
            logging.error(f"记录持仓变化失败: {e}")

    async def log_risk_event(self, risk_log: RiskEventLog) -> None:
        """记录风险事件"""
        try:
            log_entry = {
                "category": LogCategory.RISK_MANAGEMENT.value,
                "timestamp": risk_log.timestamp.isoformat(),
                "data": asdict(risk_log)
            }

            # 添加到队列
            self.log_queue.append(log_entry)

            # 文件日志
            if self.enable_file_logging:
                await self._write_to_file(
                    "risks",
                    f"{risk_log.strategy_id}_{risk_log.timestamp.strftime('%Y%m%d')}.jsonl",
                    log_entry
                )

        except Exception as e:
            logging.error(f"记录风险事件失败: {e}")

    async def log_strategy_performance(
        self,
        strategy_id: str,
        strategy_name: str,
        performance_data: dict[str, Any]
    ) -> None:
        """记录策略性能"""
        try:
            log_entry = {
                "category": LogCategory.STRATEGY_PERFORMANCE.value,
                "timestamp": datetime.now().isoformat(),
                "strategy_id": strategy_id,
                "strategy_name": strategy_name,
                "data": performance_data
            }

            # 添加到队列
            self.log_queue.append(log_entry)

            # 文件日志
            if self.enable_file_logging:
                await self._write_to_file(
                    "performance",
                    f"{strategy_id}_{datetime.now().strftime('%Y%m%d')}.jsonl",
                    log_entry
                )

            # 数据库日志
            if self.enable_database_logging and self.db_manager:
                await self.db_manager.record_strategy_performance(strategy_id, performance_data)

        except Exception as e:
            logging.error(f"记录策略性能失败: {e}")

    async def get_decision_logs(
        self,
        strategy_id: str | None = None,
        symbol: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        """获取决策日志"""
        try:
            if self.enable_database_logging and self.db_manager:
                # 从数据库查询
                return await self._query_database_logs(
                    "ai_decisions", strategy_id, symbol, start_time, end_time, limit
                )
            else:
                # 从文件查询
                return await self._query_file_logs(
                    "ai_decisions", strategy_id, start_time, end_time, limit
                )

        except Exception as e:
            logging.error(f"获取决策日志失败: {e}")
            return []

    async def get_trade_logs(
        self,
        strategy_id: str | None = None,
        symbol: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        """获取交易日志"""
        try:
            if self.enable_database_logging and self.db_manager:
                return await self.db_manager.get_trade_history(strategy_id, symbol, limit)
            else:
                return await self._query_file_logs(
                    "trades", strategy_id, start_time, end_time, limit
                )

        except Exception as e:
            logging.error(f"获取交易日志失败: {e}")
            return []

    async def get_daily_summary(self, date: datetime | None = None) -> dict[str, Any]:
        """获取每日总结"""
        if date is None:
            date = datetime.now()

        try:
            start_time = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = start_time + timedelta(days=1)

            # 获取当天的所有日志
            decision_logs = await self.get_decision_logs(start_time=start_time, end_time=end_time)
            trade_logs = await self.get_trade_logs(start_time=start_time, end_time=end_time)

            # 统计分析
            summary = {
                "date": date.strftime("%Y-%m-%d"),
                "total_decisions": len(decision_logs),
                "executed_trades": len(trade_logs),
                "unique_strategies": len(set(log.get("strategy_id") for log in trade_logs)),
                "unique_symbols": len(set(log.get("symbol") for log in trade_logs)),
                "total_volume": sum(log.get("quantity", 0) for log in trade_logs),
                "decisions_by_strategy": {},
                "trades_by_strategy": {},
                "decisions_by_symbol": {},
                "trades_by_symbol": {},
            }

            # 按策略统计
            for log in decision_logs:
                strategy_id = log.get("strategy_id", "unknown")
                summary["decisions_by_strategy"][strategy_id] = summary["decisions_by_strategy"].get(strategy_id, 0) + 1

            for log in trade_logs:
                strategy_id = log.get("strategy_id", "unknown")
                symbol = log.get("symbol", "unknown")
                summary["trades_by_strategy"][strategy_id] = summary["trades_by_strategy"].get(strategy_id, 0) + 1
                summary["trades_by_symbol"][symbol] = summary["trades_by_symbol"].get(symbol, 0) + 1

            return summary

        except Exception as e:
            logging.error(f"获取每日总结失败: {e}")
            return {}

    async def _write_to_file(self, category: str, filename: str, log_entry: dict[str, Any]) -> None:
        """写入文件日志"""
        try:
            file_path = self.log_dir / category / filename
            async with aiofiles.open(file_path, 'a', encoding='utf-8') as f:
                await f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            logging.error(f"写入文件日志失败: {e}")

    async def _write_to_database_ai_decision(self, decision_log: AIDecisionLog) -> None:
        """写入数据库AI决策"""
        try:
            decision_data = {
                "decision_time": decision_log.timestamp,
                "symbol": decision_log.symbol,
                "exchange": "UNKNOWN",  # 需要从其他地方获取
                "action": decision_log.action,
                "quantity": decision_log.quantity,
                "leverage": 1.0,  # 需要从策略配置获取
                "entry_price": decision_log.price,
                "confidence": decision_log.confidence,
                "selection_rationale": decision_log.reasoning,
                "technical_analysis": json.dumps(decision_log.technical_indicators),
                "risk_factors": json.dumps(decision_log.risk_factors),
                "status": decision_log.execution_result or "pending"
            }

            await self.db_manager.store_ai_decision(decision_data)

        except Exception as e:
            logging.error(f"写入数据库AI决策失败: {e}")

    async def _write_to_database_trade(self, trade_log: TradeExecutionLog) -> None:
        """写入数据库交易记录"""
        try:
            trade_data = {
                "trade_id": trade_log.trade_id,
                "strategy_id": trade_log.strategy_id,
                "symbol": trade_log.symbol,
                "direction": trade_log.direction,
                "order_type": trade_log.order_type,
                "quantity": trade_log.quantity,
                "price": trade_log.price,
                "timestamp": trade_log.timestamp,
                "commission": trade_log.commission,
                "pnl": 0.0,  # 平仓时更新
                "status": trade_log.status
            }

            await self.db_manager.record_trade(trade_data)

        except Exception as e:
            logging.error(f"写入数据库交易记录失败: {e}")

    async def _background_flush(self) -> None:
        """后台定时刷新日志"""
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                await self._flush_logs()
            except Exception as e:
                logging.error(f"后台刷新日志失败: {e}")

    async def _flush_logs(self) -> None:
        """刷新日志队列"""
        if not self.log_queue:
            return

        try:
            # 批量处理日志
            batch = self.log_queue[:self.batch_size]
            self.log_queue = self.log_queue[self.batch_size:]

            # 这里可以添加批量写入数据库的逻辑
            # 目前只是确保日志队列不会无限增长

            logging.debug(f"刷新了 {len(batch)} 条日志")

        except Exception as e:
            logging.error(f"刷新日志失败: {e}")

    async def _query_file_logs(
        self,
        category: str,
        strategy_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        """从文件查询日志"""
        try:
            logs = []
            category_dir = self.log_dir / category

            if not category_dir.exists():
                return logs

            # 获取所有相关文件
            files = list(category_dir.glob("*.jsonl"))
            if strategy_id:
                files = [f for f in files if strategy_id in f.name]

            # 读取文件内容
            for file_path in files:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    async for line in f:
                        try:
                            log_entry = json.loads(line.strip())
                            log_time = datetime.fromisoformat(log_entry['timestamp'])

                            # 时间过滤
                            if start_time and log_time < start_time:
                                continue
                            if end_time and log_time >= end_time:
                                continue

                            logs.append(log_entry)

                            if len(logs) >= limit:
                                return logs

                        except json.JSONDecodeError:
                            continue

            # 按时间排序并限制数量
            logs.sort(key=lambda x: x['timestamp'], reverse=True)
            return logs[:limit]

        except Exception as e:
            logging.error(f"从文件查询日志失败: {e}")
            return []

    async def _query_database_logs(
        self,
        category: str,
        strategy_id: str | None = None,
        symbol: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        """从数据库查询日志"""
        # 这里可以根据不同的category实现不同的数据库查询
        # 目前简化实现
        return []

# 全局AI日志管理器实例
ai_logger: AITradingLogger | None = None

async def get_ai_logger(
    log_dir: str = "logs",
    enable_file_logging: bool = True,
    enable_database_logging: bool = True,
    db_manager: Any | None = None
) -> AITradingLogger:
    """获取AI日志管理器实例"""
    global ai_logger
    if ai_logger is None:
        ai_logger = AITradingLogger(
            log_dir=log_dir,
            enable_file_logging=enable_file_logging,
            enable_database_logging=enable_database_logging,
            db_manager=db_manager
        )
        await ai_logger.start()
    return ai_logger