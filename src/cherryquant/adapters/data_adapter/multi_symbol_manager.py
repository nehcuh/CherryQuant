"""
多品种期货市场数据管理器
支持中国四大期货交易所的所有品种数据获取和分析
（M2 改造：移除 AKShare 依赖，改为从 TimescaleDB 快照读取）
"""

import asyncio
import logging
from typing import Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from cherryquant.adapters.data_storage.database_manager import DatabaseManager
from cherryquant.adapters.data_storage.timeframe_data_manager import TimeFrame

logger = logging.getLogger(__name__)

class ChineseFuturesMarket:
    """中国期货市场数据管理"""

    # 四大期货交易所的品种映射
    EXCHANGE_SYMBOLS = {
        "SHFE": {
            "rb": "螺纹钢",
            "cu": "沪铜",
            "al": "沪铝",
            "zn": "沪锌",
            "au": "沪金",
            "ag": "沪银",
            "ni": "沪镍",
            "sn": "沪锡",
            "pb": "沪铅",
            "bu": "沥青",
            "hc": "热轧卷板",
            "fu": "燃料油",
            "ru": "天然橡胶",
            "sp": "纸浆"
        },
        "DCE": {
            "i": "铁矿石",
            "j": "焦炭",
            "jm": "焦煤",
            "a": "豆一",
            "c": "玉米",
            "m": "豆粕",
            "y": "豆油",
            "p": "棕榈油",
            "jd": "鸡蛋",
            "pp": "聚丙烯",
            "l": "聚乙烯",
            "v": "聚氯乙烯",
            "eg": "乙二醇",
            "fb": "纤维板",
            "bb": "胶合板",
            "lh": "生猪",
            "pg": "液化石油气"
        },
        "CZCE": {
            "sr": "白糖",
            "cf": "棉花",
            "ta": "PTA",
            "oi": "菜籽油",
            "rm": "菜籽粕",
            "ma": "甲醇",
            "fg": "玻璃",
            "tc": "动力煤",
            "sm": "硅铁",
            "sf": "硅锰",
            "ur": "尿素",
            "sa": "纯碱",
            "pf": "苯乙烯",
            "pk": "花生",
            "wh": "强麦",
            "ws": "晚籼稻",
            "wt": "早籼稻"
        },
        "CFFEX": {
            "IF": "沪深300",
            "IC": "中证500",
            "IH": "上证50",
            "T": "10年期国债",
            "TF": "5年期国债",
            "TS": "2年期国债",
            "TL": "30年期国债"
        }
    }

    # 旧的 AKShare 映射已移除

class MultiSymbolDataManager:
    """多品种数据管理器（从 DB 快照读取）

    注意：不再在内部创建数据库连接，而是要求调用方注入
    已初始化好的 DatabaseManager 实例，这样可以保持 adapters 层
    对配置和环境变量的无感知，更符合清晰的分层设计。
    """

    def __init__(self, db_manager: DatabaseManager | None = None):
        self.futures_market = ChineseFuturesMarket()
        self.cache: dict[str, Any] = {}
        self.last_update: dict[str, datetime] = {}
        self.cache_duration = 300  # 5分钟缓存
        self.db_manager: DatabaseManager | None = db_manager

    async def _ensure_db(self) -> DatabaseManager:
        if self.db_manager is None:
            raise RuntimeError(
                "MultiSymbolDataManager.db_manager 未设置；请在组合根或调用方中注入 DatabaseManager"
            )
        return self.db_manager

    async def get_all_market_data(self, exclude_exchanges: list[str] = None) -> dict[str, Any]:
        """获取所有期货品种的市场数据（从 DB 读取 5m 快照，若无则跳过）"""
        try:
            logger.info("开始获取全市场数据（DB 快照）...")
            await self._ensure_db()

            all_data = {}
            total_contracts = 0

            # 遍历所有交易所
            for exchange, symbols in self.futures_market.EXCHANGE_SYMBOLS.items():
                if exclude_exchanges and exchange in exclude_exchanges:
                    continue

                exchange_data = await self._get_exchange_data(exchange, symbols)
                if exchange_data:
                    all_data[exchange] = exchange_data
                    total_contracts += len(exchange_data)

            logger.info(f"成功获取 {total_contracts} 个合约的数据（DB）")

            return {
                "total_contracts": total_contracts,
                "exchange_data": all_data,
                "update_time": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"获取全市场数据失败: {e}")
            return {"error": str(e)}

    async def _get_exchange_data(self, exchange: str, symbols: dict[str, str]) -> dict[str, Any]:
        """获取单个交易所的数据（DB 快照）"""
        try:
            exchange_data: dict[str, Any] = {}

            # 并发获取所有品种数据
            tasks = []
            for symbol, name in symbols.items():
                tasks.append(self._get_symbol_data(exchange, symbol, name))

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"获取品种数据失败: {result}")
                    elif result:
                        sym = result["symbol"]
                        exchange_data[sym] = result

            return exchange_data

        except Exception as e:
            logger.error(f"获取{exchange}交易所数据失败: {e}")
            return {}

    async def _get_symbol_data(self, exchange: str, symbol: str, name: str) -> dict[str, Any | None]:
        """获取单个品种数据（优先 DB 5m 快照）"""
        try:
            # 缓存命中
            cache_key = f"{exchange}_{symbol}"
            if (
                cache_key in self.cache and
                (datetime.now() - self.last_update.get(cache_key, datetime.min)).seconds < self.cache_duration
            ):
                return self.cache[cache_key]

            # 拉取最近 120 根 5m bar
            await self._ensure_db()
            points = await self.db_manager.get_market_data(symbol, exchange, TimeFrame.FIVE_MIN, limit=120)
            if not points:
                return None

            # 转 DataFrame，确保所有数值字段都是float类型
            data = [
                {
                    'datetime': p.timestamp,
                    'open': float(p.open),
                    'high': float(p.high),
                    'low': float(p.low),
                    'close': float(p.close),
                    'volume': float(p.volume),
                    'open_interest': float(getattr(p, 'open_interest', 0)),
                }
                for p in points
            ]
            df = pd.DataFrame(data).sort_values('datetime')
            if df.empty:
                return None

            # 指标
            df['ma5'] = df['close'].rolling(window=5).mean()
            df['ma20'] = df['close'].rolling(window=20).mean()
            df['volume_ma'] = df['volume'].rolling(window=20).mean()
            df['rsi'] = self._calculate_rsi(df['close'], 14)

            latest = df.iloc[-1]
            recent = df.tail(20)

            symbol_data = {
                "symbol": symbol,
                "name": name,
                "exchange": exchange,
                "current_price": float(latest['close']),
                "volume": int(latest['volume']) if not pd.isna(latest['volume']) else 0,
                "open_interest": int(latest.get('open_interest', 0)) if not pd.isna(latest.get('open_interest', 0)) else 0,
                "change_pct": float(((latest['close'] / df.iloc[-2]['close']) - 1) * 100) if len(df) > 1 else 0,
                "high_24h": float(recent['high'].max()),
                "low_24h": float(recent['low'].min()),

                # 技术指标
                "ma5": float(latest['ma5']) if not pd.isna(latest['ma5']) else 0,
                "ma20": float(latest['ma20']) if not pd.isna(latest['ma20']) else 0,
                "rsi": float(latest['rsi']) if not pd.isna(latest['rsi']) else 50,
                "volume_ratio": float(latest['volume'] / latest['volume_ma']) if latest.get('volume_ma', 0) else 1,

                # 价格序列（用于AI分析）
                "prices_5m": [float(p) for p in recent['close'].tolist()],
                "volumes_5m": [int(v) for v in recent['volume'].tolist()],
                "highs_5m": [float(h) for h in recent['high'].tolist()],
                "lows_5m": [float(l) for l in recent['low'].tolist()],

                # 市场质量指标
                "liquidity_score": self._calculate_liquidity_score(latest['volume']) if not pd.isna(latest['volume']) else 0,
                "volatility": self._calculate_volatility(recent['close']),
                "trend_strength": self._calculate_trend_strength(latest, df),

                "update_time": datetime.now().isoformat()
            }

            # 缓存
            self.cache[cache_key] = symbol_data
            self.last_update[cache_key] = datetime.now()
            return symbol_data

        except Exception as e:
            logger.error(f"获取{symbol}数据失败: {e}")
            return None

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_liquidity_score(self, volume: float) -> float:
        """计算流动性评分 (0-100)"""
        # 基于成交量计算流动性评分
        if volume >= 100000:
            return 100
        elif volume >= 50000:
            return 80
        elif volume >= 20000:
            return 60
        elif volume >= 10000:
            return 40
        elif volume >= 5000:
            return 20
        else:
            return 10

    def _calculate_volatility(self, prices: pd.Series) -> float:
        """计算波动率"""
        if len(prices) < 2:
            return 0
        returns = prices.pct_change().dropna()
        volatility = returns.std() * 100  # 转换为百分比
        return float(volatility)

    def _calculate_trend_strength(self, latest_row: pd.Series, df: pd.DataFrame) -> float:
        """计算趋势强度 (-1 到 1)"""
        try:
            current_price = latest_row['close']
            ma5 = latest_row['ma5'] if not pd.isna(latest_row['ma5']) else current_price
            ma20 = latest_row['ma20'] if not pd.isna(latest_row['ma20']) else current_price

            # 计算趋势强度
            if current_price > ma5 > ma20:
                return 0.8  # 强上涨
            elif current_price > ma5 < ma20:
                return 0.4  # 弱上涨
            elif current_price < ma5 < ma20:
                return -0.8  # 强下跌
            elif current_price < ma5 > ma20:
                return -0.4  # 弱下跌
            else:
                return 0.0  # 震荡
        except:
            return 0.0

    def get_top_movers(self, limit: int = 10) -> dict[str, list[dict]]:
        """获取涨幅榜"""
        try:
            all_data = self.cache.values()

            # 按涨跌幅排序
            gainers = sorted([d for d in all_data if d["change_pct"] > 0],
                           key=lambda x: x["change_pct"], reverse=True)[:limit]
            losers = sorted([d for d in all_data if d["change_pct"] < 0],
                           key=lambda x: x["change_pct"])[:limit]

            return {
                "top_gainers": gainers,
                "top_losers": losers
            }
        except Exception as e:
            logger.error(f"获取涨幅榜失败: {e}")
            return {"top_gainers": [], "top_losers": []}

    def get_liquid_contracts(self, min_volume: int = 20000) -> list[dict]:
        """获取高流动性合约"""
        try:
            liquid = [d for d in self.cache.values() if d["volume"] >= min_volume]
            return sorted(liquid, key=lambda x: x["volume"], reverse=True)
        except Exception as e:
            logger.error(f"获取高流动性合约失败: {e}")
            return []

    def format_for_ai_prompt(self, market_data: dict[str, Any]) -> str:
        """格式化数据用于AI提示词"""
        try:
            if "error" in market_data:
                return "数据获取失败，无法进行市场分析"

            exchange_data = market_data["exchange_data"]
            formatted_parts = []

            for exchange, contracts in exchange_data.items():
                if not contracts:
                    continue

                formatted_parts.append(f"### {exchange} 交易所 - {len(contracts)} 个合约")

                for symbol, data in contracts.items():
                    if data:
                        formatted_parts.append(f"""
**{data['name']} ({symbol.upper()})**
- 当前价格: {data['current_price']:.2f}
- 涨跌幅: {data['change_pct']:+.2f}%
- 成交量: {data['volume']:,}
- 流动性评分: {data['liquidity_score']:.0f}
- 波动率: {data['volatility']:.2f}%
- RSI: {data['rsi']:.1f}
- 趋势强度: {data['trend_strength']:+.2f}
- 技术状态: {'强上涨' if data['trend_strength'] > 0.5 else '强下跌' if data['trend_strength'] < -0.5 else '震荡'}
""")

            return "\n".join(formatted_parts)

        except Exception as e:
            logger.error(f"格式化AI提示词数据失败: {e}")
            return "数据格式化失败"

    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
        self.last_update.clear()
        logger.info("已清空数据缓存")

# 全局多品种数据管理器实例
multi_symbol_manager = MultiSymbolDataManager()
