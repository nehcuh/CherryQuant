"""
AI驱动的期货品种选择和交易决策引擎
让AI分析全市场并自主选择最优交易机会
"""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import asyncio

from ..llm_client.openai_client import LLMClient
from ..prompts.ai_selection_prompts import AI_SELECTION_SYSTEM_PROMPT, AI_SELECTION_USER_PROMPT_TEMPLATE
from ...adapters.data_adapter.multi_symbol_manager import (
    MultiSymbolDataManager,
    multi_symbol_manager,
)

from ...adapters.data_adapter.contract_resolver import get_contract_resolver

logger = logging.getLogger(__name__)

class AISelectionEngine:
    """AI品种选择和交易决策引擎"""

    def __init__(
        self,
        ai_client: LLMClient,
        tushare_token: Optional[str] = None,
        contract_resolver=None,
        market_data_manager: Optional[MultiSymbolDataManager] = None,
    ):
        """初始化AI选择引擎

        Args:
            ai_client: 已初始化的 LLM 客户端（通常来自 AppContext.ai_client）
            tushare_token: Tushare Pro API令牌
            contract_resolver: 合约解析器实例（可选）
            market_data_manager: 多品种市场数据管理器（可选，未提供时使用全局实例）
        """
        self.ai_client = ai_client
        self.start_time = datetime.now()
        self.market_data_manager: MultiSymbolDataManager = market_data_manager or multi_symbol_manager
        self.portfolio = {
            "positions": [],
            "total_value": 100000.0,
            "available_cash": 100000.0,
            "risk_exposure": 0.0
        }

        # 初始化合约解析器
        if contract_resolver:
            self.contract_resolver = contract_resolver
        elif get_contract_resolver:
            self.contract_resolver = get_contract_resolver(tushare_token)
            logger.info("✅ 合约解析器初始化完成")
        else:
            self.contract_resolver = None
            logger.warning("⚠️ 合约解析器不可用，将使用固定合约代码")

    async def resolve_commodities_to_contracts(
        self,
        commodities: List[str]
    ) -> Dict[str, str]:
        """
        将品种代码列表解析为主力合约

        Args:
            commodities: 品种代码列表 (如 ["rb", "cu", "IF"])

        Returns:
            品种到合约的映射字典 (如 {"rb": "rb2501", "cu": "cu2501"})
        """
        if not self.contract_resolver:
            logger.warning("合约解析器不可用，返回空映射")
            return {}

        try:
            contracts_map = await self.contract_resolver.batch_resolve_contracts(commodities)
            logger.info(f"✅ 解析了 {len(contracts_map)} 个品种的主力合约")
            return contracts_map
        except Exception as e:
            logger.error(f"批量解析合约失败: {e}")
            return {}

    async def get_optimal_trade_decision(
        self,
        account_info: Dict[str, Any] = None,
        current_positions: List[Dict[str, Any]] = None,
        market_scope: Dict[str, Any] = None,
        commodities: Optional[List[str]] = None,
        max_retries: int = 2
    ) -> Optional[Dict[str, Any]]:
        """
        获取AI最优交易决策（包含品种选择）

        Args:
            account_info: 账户信息
            current_positions: 当前持仓
            market_scope: 市场范围配置
            commodities: 品种代码列表（如 ["rb", "cu"]），优先级高于market_scope
            max_retries: 最大重试次数

        Returns:
            包含品种选择和交易决策的完整JSON
        """
        try:
            logger.info("🔍 开始AI全市场分析...")

            # 1. 如果提供了品种列表，先解析为主力合约
            if commodities:
                logger.info(f"📦 品种池模式: 解析 {len(commodities)} 个品种的主力合约")
                contracts_map = await self.resolve_commodities_to_contracts(commodities)

                # 构造market_scope限制到这些合约
                resolved_symbols = [contract for contract in contracts_map.values() if contract]
                if resolved_symbols:
                    market_scope = market_scope or {}
                    market_scope["include_symbols"] = resolved_symbols
                    logger.info(f"✅ 已解析主力合约: {resolved_symbols}")
                else:
                    logger.warning("⚠️ 未能解析任何主力合约")

            # 2. 获取全市场数据
            market_data = await self._get_comprehensive_market_data(market_scope)
            if not market_data or "error" in market_data:
                logger.error("无法获取市场数据")
                return None

            # 3. 构造AI提示词
            system_prompt = AI_SELECTION_SYSTEM_PROMPT
            user_prompt = self._build_ai_selection_prompt(
                market_data=market_data,
                account_info=account_info or self._get_default_account_info(),
                current_positions=current_positions or []
            )

            logger.info(f"📊 分析市场数据: {market_data['total_contracts']} 个合约")

            # 4. 调用AI模型（带重试机制）
            for attempt in range(max_retries + 1):
                try:
                    logger.info(f"🤖 AI正在分析全市场 (尝试 {attempt + 1}/{max_retries + 1})...")
                    decision = await self.ai_client.get_trading_decision_async(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt
                    )

                    if decision:
                        # 清理和解析JSON
                        if isinstance(decision, str):
                            decision = self._clean_and_parse_json(decision)

                        # 验证决策
                        if self._validate_selection_decision(decision, market_data):
                            logger.info(f"✅ AI决策完成: {decision.get('selected_trade', {}).get('action', 'unknown')}")
                            logger.info(f"🎯 选择合约: {decision.get('selected_trade', {}).get('symbol', 'unknown')}")
                            return decision
                        else:
                            logger.warning(f"AI决策验证失败 (尝试 {attempt + 1})")
                    else:
                        logger.warning(f"AI返回空决策 (尝试 {attempt + 1})")

                except Exception as e:
                    logger.error(f"AI调用或解析失败 (尝试 {attempt + 1}): {e}")

                # 如果不是最后一次尝试，等待后重试
                if attempt < max_retries:
                    await asyncio.sleep(1)

            logger.error("达到最大重试次数，AI决策获取失败")
            return None

        except Exception as e:
            logger.error(f"AI选择决策过程严重错误: {e}")
            return None

    def _clean_and_parse_json(self, response_str: str) -> Optional[Dict[str, Any]]:
        """清理并解析JSON字符串（处理Markdown代码块）"""
        try:
            # 移除Markdown代码块标记
            cleaned = re.sub(r'```json\s*', '', response_str)
            cleaned = re.sub(r'```\s*', '', cleaned)
            cleaned = cleaned.strip()
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            return None

    async def _get_comprehensive_market_data(self, market_scope: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """获取全面的市场数据"""
        try:
            # 解析市场范围配置
            exclude_exchanges = []
            include_exchanges = []

            if market_scope:
                exclude_exchanges = market_scope.get("exclude_exchanges", [])
                include_exchanges = market_scope.get("include_exchanges", [])

            # 如果指定了包含的交易所，则只分析这些
            if include_exchanges:
                exchange_data = {}
                total_contracts = 0
                for exchange in include_exchanges:
                    if exchange in multi_symbol_manager.futures_market.EXCHANGE_SYMBOLS:
                        symbols = multi_symbol_manager.futures_market.EXCHANGE_SYMBOLS[exchange]
                        exchange_data_part = await self.market_data_manager._get_exchange_data(exchange, symbols)
                        if exchange_data_part:
                            exchange_data[exchange] = exchange_data_part
                            total_contracts += len(exchange_data_part)

                return {
                    "total_contracts": total_contracts,
                    "exchange_data": exchange_data,
                    "update_time": datetime.now().isoformat()
                }

            # 否则获取全市场数据（排除指定的交易所）
            market_data = await self.market_data_manager.get_all_market_data(exclude_exchanges)

            # 添加市场统计信息
            market_data.update(self._calculate_market_statistics(market_data.get("exchange_data", {})))

            return market_data

        except Exception as e:
            logger.error(f"获取综合市场数据失败: {e}")
            return None

    def _calculate_market_statistics(self, exchange_data: Dict[str, Any]) -> Dict[str, Any]:
        """计算市场统计信息"""
        try:
            all_contracts = []
            total_volume = 0
            gainers = 0
            losers = 0

            for exchange, contracts in exchange_data.items():
                for symbol, data in contracts.items():
                    if data:
                        all_contracts.append(data)
                        total_volume += data.get("volume", 0)
                        if data.get("change_pct", 0) > 0:
                            gainers += 1
                        elif data.get("change_pct", 0) < 0:
                            losers += 1

            # 计算市场情绪
            market_sentiment = "neutral"
            if gainers > losers * 1.5:
                market_sentiment = "bullish"
            elif losers > gainers * 1.5:
                market_sentiment = "bearish"

            # 计算平均波动率
            avg_volatility = 0
            if all_contracts:
                avg_volatility = sum(c.get("volatility", 0) for c in all_contracts) / len(all_contracts)

            # 计算波动率指数
            volatility_index = "low"
            if avg_volatility > 3:
                volatility_index = "high"
            elif avg_volatility > 1.5:
                volatility_index = "medium"

            return {
                "market_sentiment": market_sentiment,
                "volatility_index": volatility_index,
                "total_volume": total_volume,
                "avg_volatility": avg_volatility,
                "gainers_count": gainers,
                "losers_count": losers,
                "total_active_contracts": len(all_contracts)
            }

        except Exception as e:
            logger.error(f"计算市场统计失败: {e}")
            return {}

    def _build_ai_selection_prompt(
        self,
        market_data: Dict[str, Any],
        account_info: Dict[str, Any],
        current_positions: List[Dict[str, Any]]
    ) -> str:
        """构造AI选择提示词"""
        try:
            minutes_elapsed = int((datetime.now() - self.start_time).total_seconds() / 60)
            current_time = datetime.now().strftime('%H:%M:%S')
            # 推断交易时段（避免模板缺少 market_session 抛错）
            hour = datetime.now().hour
            if 9 <= hour < 15:
                market_session = "day"
            elif hour >= 21 or hour < 3:
                market_session = "night"
            else:
                market_session = "closed"

            # 格式化市场数据
            contract_data_str = self._format_contract_data_for_prompt(market_data.get("exchange_data", {}))

            # 格式化持仓信息
            positions_info = self._format_positions_for_prompt(current_positions)

            # 格式化板块表现
            sector_performance = self._calculate_sector_performance(market_data.get("exchange_data", {}))

            # 格式化相关性信息
            correlation_summary = self._generate_correlation_summary(market_data.get("exchange_data", {}))

            # 填充模板
            user_prompt = AI_SELECTION_USER_PROMPT_TEMPLATE.format(
                minutes_elapsed=minutes_elapsed,
                current_time=current_time,
                market_session=market_session,
                total_contracts=market_data.get("total_contracts", 0),
                market_regime=f"{market_data.get('market_sentiment', 'unknown')} / {market_data.get('volatility_index', 'unknown')} volatility",
                volatility_index=market_data.get("avg_volatility", 0),
                exchange_name="各交易所数据",
                symbol_count=len(market_data.get("exchange_data", {})),
                contract_data=contract_data_str,
                account_value=account_info.get("account_value", 100000),
                available_cash=account_info.get("cash_available", 100000),
                risk_exposure=account_info.get("total_exposure", 0),
                current_positions=len(current_positions),
                daily_pnl=account_info.get("daily_pnl", 0),
                daily_pnl_pct=account_info.get("daily_pnl_pct", 0),
                positions_info=positions_info,
                sector_performance=sector_performance,
                correlation_summary=correlation_summary
            )

            return user_prompt

        except Exception as e:
            logger.error(f"构造AI选择提示词失败: {e}")
            return "数据构造失败，无法进行分析"

    def _format_contract_data_for_prompt(self, exchange_data: Dict[str, Any]) -> str:
        """格式化合约数据用于AI提示词"""
        try:
            formatted_parts = []

            for exchange, contracts in exchange_data.items():
                if not contracts:
                    continue

                formatted_parts.append(f"### {exchange} - {len(contracts)} 个合约")

                for symbol, data in sorted(contracts.items(), key=lambda x: x[1].get("change_pct", 0), reverse=True):
                    if data:
                        trend_status = "强上涨" if data["trend_strength"] > 0.5 else "强下跌" if data["trend_strength"] < -0.5 else "震荡"
                        rsi_status = "超买" if data["rsi"] > 70 else "超卖" if data["rsi"] < 30 else "正常"

                        formatted_parts.append(f"""
**{data['name']} ({symbol.upper()})**
- 价格: ¥{data['current_price']:.2f} ({data['change_pct']:+.2f}%)
- 成交量: {data['volume']:,} | 流动性: {data['liquidity_score']:.0f}/100
- 波动率: {data['volatility']:.2f}% | 趋势强度: {data['trend_strength']:+.2f}
- RSI: {data['rsi']:.1f} ({rsi_status}) | 均线: MA5={data['ma5']:.2f} MA20={data['ma20']:.2f}
- 技术状态: {trend_status}
""")

            return "\n".join(formatted_parts)

        except Exception as e:
            logger.error(f"格式化合约数据失败: {e}")
            return "数据格式化失败"

    def _format_positions_for_prompt(self, positions: List[Dict[str, Any]]) -> str:
        """格式化持仓信息"""
        try:
            if not positions:
                return "无持仓"

            formatted = []
            for pos in positions:
                formatted.append(f"""- {pos.get('symbol', 'Unknown')}: {pos.get('quantity', 0)}手 @ ¥{pos.get('entry_price', 0):.2f} (PnL: ¥{pos.get('unrealized_pnl', 0):+.2f})""")

            return "\n".join(formatted)

        except Exception as e:
            logger.error(f"格式化持仓信息失败: {e}")
            return "持仓信息格式化失败"

    def _calculate_sector_performance(self, exchange_data: Dict[str, Any]) -> str:
        """计算板块表现"""
        try:
            sectors = {
                "金属": ["cu", "al", "zn", "ni", "sn", "au", "ag", "pb"],
                "黑色": ["rb", "i", "j", "jm", "hc", "fu"],
                "农产品": ["a", "c", "m", "y", "p", "jd", "lh", "rm", "oi", "sr", "cf"],
                "化工": ["pp", "l", "v", "eg", "ta", "ma", "fg", "ur", "sa", "pf"],
                "金融": ["IF", "IC", "IH", "T", "TF", "TS", "TL"]
            }

            sector_performance = {}
            for sector, symbols in sectors.items():
                sector_data = []
                for exchange, contracts in exchange_data.items():
                    for symbol, data in contracts.items():
                        if symbol in symbols and data:
                            sector_data.append(data["change_pct"])

                if sector_data:
                    avg_change = sum(sector_data) / len(sector_data)
                    sector_performance[sector] = avg_change

            formatted = []
            for sector, change in sorted(sector_performance.items(), key=lambda x: x[1], reverse=True):
                formatted.append(f"- {sector}: {change:+.2f}%")

            return "\n".join(formatted) if formatted else "板块数据不足"

        except Exception as e:
            logger.error(f"计算板块表现失败: {e}")
            return "板块分析失败"

    def _generate_correlation_summary(self, exchange_data: Dict[str, Any]) -> str:
        """生成相关性分析摘要"""
        try:
            # 简化的相关性分析
            total_contracts = sum(len(contracts) for contracts in exchange_data.values())
            return f"总共分析 {total_contracts} 个合约，建议分散投资降低相关性风险"

        except Exception as e:
            logger.error(f"生成相关性摘要失败: {e}")
            return "相关性分析失败"

    def _get_default_account_info(self) -> Dict[str, Any]:
        """获取默认账户信息"""
        return {
            "account_value": self.portfolio["total_value"],
            "cash_available": self.portfolio["available_cash"],
            "total_exposure": self.portfolio["risk_exposure"],
            "daily_pnl": 0.0,
            "daily_pnl_pct": 0.0
        }

    def _validate_selection_decision(self, decision: Dict[str, Any], market_data: Dict[str, Any] = None) -> bool:
        """验证AI选择决策的格式和业务逻辑"""
        try:
            if not isinstance(decision, dict):
                logger.error("决策必须是字典格式")
                return False

            required_fields = [
                "market_analysis", "top_opportunities", "selected_trade"
            ]

            for field in required_fields:
                if field not in decision:
                    logger.error(f"缺少必需字段: {field}")
                    return False

            # 验证selected_trade字段
            selected_trade = decision["selected_trade"]
            trade_required_fields = [
                "action", "symbol", "exchange", "quantity",
                "leverage", "confidence", "selection_rationale"
            ]

            for field in trade_required_fields:
                if field not in selected_trade:
                    logger.error(f"selected_trade缺少必需字段: {field}")
                    return False

            # 验证置信度
            confidence = selected_trade.get("confidence", 0)
            if not 0 <= confidence <= 1:
                logger.error("confidence必须在0-1之间")
                return False

            # 业务逻辑验证：检查合约是否存在于市场数据中
            if market_data:
                symbol = selected_trade.get("symbol")
                if symbol and symbol.lower() != "none":
                    found = False
                    for exchange, contracts in market_data.get("exchange_data", {}).items():
                        if symbol.lower() in [s.lower() for s in contracts.keys()]:
                            found = True
                            break
                    if not found:
                        logger.warning(f"AI推荐了不在市场数据中的合约: {symbol} (可能是幻觉)")
                        # 这里可以选择返回False拒绝，或者仅警告
                        # 为了安全，建议拒绝
                        return False

            return True

        except Exception as e:
            logger.error(f"AI选择决策验证失败: {e}")
            return False

    async def test_connection(self) -> bool:
        """测试AI连接"""
        return await self.ai_client.test_connection()

    def update_portfolio_position(self, action: str, symbol: str, quantity: int, price: float):
        """更新投资组合持仓"""
        try:
            if action in ["buy_to_enter", "sell_to_enter"]:
                # 开仓
                self.portfolio["positions"].append({
                    "symbol": symbol,
                    "quantity": quantity,
                    "entry_price": price,
                    "entry_time": datetime.now().isoformat()
                })
                # 更新风险敞口
                position_value = quantity * price
                self.portfolio["risk_exposure"] += position_value
                self.portfolio["available_cash"] -= position_value * 0.1  # 简化保证金计算

            elif action == "close":
                # 平仓
                for i, pos in enumerate(self.portfolio["positions"]):
                    if pos["symbol"] == symbol:
                        pnl = (price - pos["entry_price"]) * pos["quantity"]
                        self.portfolio["total_value"] += pnl
                        self.portfolio["available_cash"] += pos["quantity"] * price * 0.1
                        self.portfolio["risk_exposure"] -= pos["quantity"] * pos["entry_price"]
                        self.portfolio["positions"].pop(i)
                        break

        except Exception as e:
            logger.error(f"更新投资组合失败: {e}")

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """获取投资组合摘要"""
        return {
            "total_value": self.portfolio["total_value"],
            "available_cash": self.portfolio["available_cash"],
            "risk_exposure": self.portfolio["risk_exposure"],
            "positions_count": len(self.portfolio["positions"]),
            "current_positions": self.portfolio["positions"]
        }
