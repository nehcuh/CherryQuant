"""
期货AI决策引擎
结合市场数据和AI模型，生成交易决策
"""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import numpy as np

from ..prompts.futures_prompts import FUTURES_SYSTEM_PROMPT, FUTURES_USER_PROMPT_TEMPLATE
from ..llm_client.openai_client import LLMClient
from cherryquant.adapters.data_adapter.market_data_manager import MarketDataManager
from cherryquant.adapters.data_storage.database_manager import DatabaseManager
from cherryquant.utils.indicators import calculate_rsi, calculate_macd, calculate_ma

logger = logging.getLogger(__name__)

class FuturesDecisionEngine:
    """期货AI决策引擎"""

    def __init__(
        self,
        ai_client: LLMClient,
        db_manager: DatabaseManager | None = None,
        market_data_manager: MarketDataManager | None = None,
    ):
        """初始化决策引擎

        Args:
            ai_client: 已初始化的 LLM 客户端（通常来自 AppContext.ai_client）
            db_manager: 可选的数据库管理器，用于优先从本地数据库读取/写入
            market_data_manager: 可选的数据管理器，用于行情回退获取
        """
        self.ai_client = ai_client
        self.start_time = datetime.now()
        self.db_manager = db_manager
        self.market_data_manager = market_data_manager

    async def get_decision(
        self,
        symbol: str,
        account_info: dict[str, Any],
        current_positions: list[dict[str, Any | None]] = None,
        exchange: str = "SHFE"
    ) -> dict[str, Any | None]:
        """
        获取交易决策

        Args:
            symbol: 期货合约代码（如 'rb2501'）
            account_info: 账户信息
            current_positions: 当前持仓列表
            exchange: 交易所代码

        Returns:
            交易决策字典，或None（如果失败）
        """
        try:
            # 获取市场数据（优先本地数据库，其次外部数据源）
            market_data = await self._get_market_data(symbol, exchange)
            if not market_data:
                logger.error(f"获取{symbol}市场数据失败")
                return None

            # 构造提示词
            system_prompt = FUTURES_SYSTEM_PROMPT
            user_prompt = self._build_user_prompt(
                symbol=symbol,
                market_data=market_data,
                account_info=account_info,
                current_positions=current_positions or []
            )

            logger.info(f"正在为{symbol}请求AI决策...")

            # 调用AI模型
            try:
                decision = await self.ai_client.get_trading_decision_async(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt
                )

                if decision:
                    logger.info(f"AI决策成功: {decision}")
                    return decision
                else:
                    logger.warning("AI决策为空，使用模拟决策路径")
                    return self._simulate_decision(symbol, market_data)
            except Exception as e:
                logger.error(f"AI决策引擎调用失败: {e}")
                return self._simulate_decision(symbol, market_data)

        except Exception as e:
            logger.error(f"获取决策时发生错误: {e}")
            return None

    async def _get_market_data(self, symbol: str, exchange: str = "SHFE") -> dict[str, Any | None]:
        """
        获取期货市场数据（从 DB 读取 5m/10m/30m/60m；DB 缺失时生成模拟序列）
        """
        try:
            sym = (symbol or '').lower()
            # 读取 DB 中 5m 为主视角
            df5 = None
            if self.db_manager:
                from cherryquant.adapters.data_storage.timeframe_data_manager import TimeFrame as TF
                try:
                    pts5 = await self.db_manager.get_market_data(sym, exchange, TF.FIVE_MIN, limit=120)
                    if pts5:
                        df5 = pd.DataFrame([
                            {
                                'datetime': p.timestamp,
                                'open': p.open,
                                'high': p.high,
                                'low': p.low,
                                'close': p.close,
                                'volume': p.volume,
                            }
                            for p in pts5
                        ]).sort_values('datetime')
                except Exception as e:
                    logger.debug(f"DB 读取 5m 失败: {e}")

            if df5 is None or df5.empty:
                # 尝试从market_data_manager获取实时价格
                base = 3500.0  # 默认基准价格
                if self.market_data_manager:
                    try:
                        # 提取品种代码（去除数字）用于获取主力合约实时价格
                        commodity = re.sub(r'\d+', '', symbol).lower()

                        realtime_price = await self.market_data_manager.get_realtime_price(commodity)
                        if realtime_price is not None and realtime_price > 0:
                            base = realtime_price
                            logger.info(f"使用实时价格生成数据序列: {symbol}({commodity}) = {base}")
                        else:
                            logger.warning(f"无法获取{symbol}实时价格，使用模拟基准价格: {base}")
                    except Exception as e:
                        logger.warning(f"获取实时价格失败: {e}，使用模拟基准价格: {base}")
                else:
                    logger.warning(f"market_data_manager未初始化，使用模拟基准价格: {base}")

                # 生成模拟序列，以实时价格为基准
                ts = pd.date_range(end=pd.Timestamp.now(), periods=120, freq='5min')
                vals = []
                price = base
                for t in ts:
                    change = (hash((t.minute, t.hour)) % 5 - 2) * 0.5
                    price = max(1.0, price + change)
                    vals.append({
                        'datetime': t,
                        'open': price * 0.999,
                        'high': price * 1.002,
                        'low': price * 0.998,
                        'close': price,
                        'volume': 10000,
                    })
                df5 = pd.DataFrame(vals)

            # 指标计算（5m）
            df5['ma5'] = calculate_ma(df5['close'], window=5)
            df5['ma20'] = calculate_ma(df5['close'], window=20)
            df5['rsi'] = calculate_rsi(df5['close'], period=14)
            df5['macd'], df5['macd_signal'], df5['macd_hist'] = calculate_macd(df5['close'])
            
            latest = df5.iloc[-1]
            recent5 = df5.tail(20)

            # 读取其他时间框架（10m/30m/1H）并做简要摘要
            mtf = {}
            if self.db_manager:
                from cherryquant.adapters.data_storage.timeframe_data_manager import TimeFrame as TF
                for tf_key, tf_enum in [('10m', TF.TEN_MIN), ('30m', TF.THIRTY_MIN), ('1h', TF.HOURLY)]:
                    try:
                        pts = await self.db_manager.get_market_data(sym, exchange, tf_enum, limit=100)
                        if pts:
                            d = pd.DataFrame([{ 'dt': p.timestamp, 'close': p.close } for p in pts]).sort_values('dt')
                            if len(d) >= 15:
                                mtf[tf_key] = {
                                    'rsi': float(calculate_rsi(d['close'], 14).iloc[-1]),
                                }
                    except Exception:
                        pass

            return {
                'current_price': float(latest['close']),
                'current_ma5': float(latest['ma5']) if not pd.isna(latest['ma5']) else 0,
                'current_ma20': float(latest['ma20']) if not pd.isna(latest['ma20']) else 0,
                'current_macd': float(latest['macd']) if not pd.isna(latest['macd']) else 0,
                'current_rsi': float(latest['rsi']) if not pd.isna(latest['rsi']) else 50,
                'current_volume': int(latest['volume']) if not pd.isna(latest['volume']) else 0,
                'prices_list': [float(x) for x in recent5['close'].tolist()],
                'ma5_list': [float(x) if not pd.isna(x) else 0 for x in recent5['ma5'].tolist()],
                'ma20_list': [float(x) if not pd.isna(x) else 0 for x in recent5['ma20'].tolist()],
                'macd_list': [float(x) if not pd.isna(x) else 0 for x in recent5['macd'].tolist()],
                'rsi_list': [float(x) if not pd.isna(x) else 50 for x in recent5['rsi'].tolist()],
                'volumes_list': [int(x) if not pd.isna(x) else 0 for x in recent5['volume'].tolist()],
                'timestamp': datetime.now().isoformat(),
                'mtf': mtf,
            }
        except Exception as e:
            logger.error(f"获取市场数据时发生错误: {e}")
            return None

    def _build_user_prompt(
        self,
        symbol: str,
        market_data: dict[str, Any],
        account_info: dict[str, Any],
        current_positions: list[dict[str, Any]]
    ) -> str:
        """
        构造用户提示词

        Args:
            symbol: 期货合约代码
            market_data: 市场数据
            account_info: 账户信息
            current_positions: 当前持仓

        Returns:
            构造好的用户提示词
        """
        # 计算运行时间
        minutes_elapsed = int((datetime.now() - self.start_time).total_seconds() / 60)

        # 格式化持仓信息
        if current_positions:
            positions_info = "```python\n[\n"
            for pos in current_positions:
                positions_info += f"  {{\n"
                positions_info += f"    'symbol': '{pos.get('symbol', '')}',\n"
                positions_info += f"    'quantity': {pos.get('quantity', 0)},\n"
                positions_info += f"    'entry_price': {pos.get('entry_price', 0)},\n"
                positions_info += f"    'current_price': {pos.get('current_price', 0)},\n"
                positions_info += f"    'unrealized_pnl': {pos.get('unrealized_pnl', 0)},\n"
                positions_info += f"    'leverage': {pos.get('leverage', 1)},\n"
                positions_info += f"    'exit_plan': {{\n"
                positions_info += f"      'profit_target': {pos.get('profit_target', 0)},\n"
                positions_info += f"      'stop_loss': {pos.get('stop_loss', 0)},\n"
                positions_info += f"      'invalidation_condition': '{pos.get('invalidation_condition', '')}'\n"
                positions_info += f"    }}\n"
                positions_info += f"  }},\n"
            positions_info += "]\n```"
        else:
            positions_info = "```python\n[]\n```"

        # 填充模板
        user_prompt = FUTURES_USER_PROMPT_TEMPLATE.format(
            minutes_elapsed=minutes_elapsed,
            symbol=symbol,
            current_price=market_data['current_price'],
            current_ma5=market_data['current_ma5'],
            current_ma20=market_data['current_ma20'],
            current_macd=market_data['current_macd'],
            current_rsi=market_data['current_rsi'],
            current_volume=market_data['current_volume'],
            prices_list=", ".join([f"{x:.2f}" for x in market_data['prices_list']]),
            ma5_list=", ".join([f"{x:.2f}" for x in market_data['ma5_list']]),
            ma20_list=", ".join([f"{x:.2f}" for x in market_data['ma20_list']]),
            macd_list=", ".join([f"{x:.4f}" for x in market_data['macd_list']]),
            rsi_list=", ".join([f"{x:.2f}" for x in market_data['rsi_list']]),
            volumes_list=", ".join([str(x) for x in market_data['volumes_list']]),
            return_pct=account_info.get('return_pct', 0),
            win_rate=account_info.get('win_rate', 0),
            cash_available=account_info.get('cash_available', 0),
            account_value=account_info.get('account_value', 0),
            positions_info=positions_info
        )

        # 附加多时间框架摘要
        mtf = market_data.get('mtf', {})
        if mtf:
            lines = ["\n---\n## MULTI-TIMEFRAME CONTEXT (10m/30m/1h)"]
            for tf_key in ['10m', '30m', '1h']:
                if tf_key in mtf:
                    rsi = mtf[tf_key].get('rsi')
                    if rsi is not None:
                        lines.append(f"- {tf_key.upper()} RSI: {rsi:.1f}")
            user_prompt += "\n" + "\n".join(lines)

        return user_prompt

    async def test_connection(self) -> bool:
        """测试AI连接"""
        return await self.ai_client.test_connection()

    async def close(self) -> None:
        """释放底层资源（如HTTP客户端）"""
        try:
            await self.ai_client.aclose()
        except Exception:
            pass

    def _simulate_decision(self, symbol: str, market_data: dict[str, Any]) -> dict[str, Any]:
        """在无可用 LLM 时的简单规则模拟决策（基于 5m）"""
        prices = market_data.get('prices_list', [])
        ma5_last = market_data.get('current_ma5', 0)
        ma20_last = market_data.get('current_ma20', 0)
        rsi_last = market_data.get('current_rsi', 50)
        price = market_data.get('current_price', 0)
        action = 'hold'
        confidence = 0.4
        if ma5_last and ma20_last:
            if ma5_last > ma20_last and rsi_last > 55:
                action = 'buy_to_enter'
                confidence = min(0.6 + (rsi_last - 55) / 100, 0.85)
            elif ma5_last < ma20_last and rsi_last < 45:
                action = 'sell_to_enter'
                confidence = min(0.6 + (45 - rsi_last) / 100, 0.85)
        # 简单止盈止损：以最近波动的倍数
        stop_gap = max(price * 0.003, 5)  # 0.3%
        take_gap = stop_gap * 2
        if action == 'buy_to_enter':
            sl = price - stop_gap
            tp = price + take_gap
        elif action == 'sell_to_enter':
            sl = price + stop_gap
            tp = price - take_gap
        else:
            sl = 0.0
            tp = 0.0
        qty = 1 if confidence < 0.6 else 2
        return {
            "signal": action,
            "symbol": symbol,
            "quantity": qty if action != 'hold' else 0,
            "leverage": 3,
            "profit_target": round(tp, 2) if tp else 0.0,
            "stop_loss": round(sl, 2) if sl else 0.0,
            "confidence": round(confidence, 2),
            "invalidation_condition": "5m MA5 与 MA20 再次反向交叉",
            "justification": "基于 5m MA 与 RSI 的简化规则模拟决策（无可用 LLM）",
        }
