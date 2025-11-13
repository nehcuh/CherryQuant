"""
vn.py CTP 实时记录器
从 VNPyGateway 订阅 tick，聚合为 5m/10m/30m/60m K 线，写入 MongoDB
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable, List

# 使用 MongoDB 版本的 DatabaseManager
from cherryquant.adapters.data_storage.database_manager import (
    get_database_manager,
    DatabaseManager,
)
from cherryquant.adapters.data_storage.timeframe_data_manager import TimeFrame, MarketDataPoint
from src.trading.vnpy_gateway import VNPyGateway

logger = logging.getLogger(__name__)


@dataclass
class BarState:
    start: datetime
    end: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    open_interest: int = 0


class _Aggregator:
    """单品种单周期聚合器"""

    def __init__(self, symbol: str, exchange: str, tf: TimeFrame):
        self.symbol = symbol
        self.exchange = exchange
        self.tf = tf
        self.current: Optional[BarState] = None

    def _bucket_end(self, ts: datetime) -> datetime:
        if self.tf == TimeFrame.FIVE_MIN:
            mins = (ts.minute // 5 + 1) * 5
            end = ts.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=mins)
        elif self.tf == TimeFrame.TEN_MIN:
            mins = (ts.minute // 10 + 1) * 10
            end = ts.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=mins)
        elif self.tf == TimeFrame.THIRTY_MIN:
            mins = (ts.minute // 30 + 1) * 30
            end = ts.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=mins)
        elif self.tf == TimeFrame.HOURLY:
            end = ts.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        else:
            # 默认 5m
            mins = (ts.minute // 5 + 1) * 5
            end = ts.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=mins)
        return end

    def update(self, ts: datetime, price: float, volume: Optional[int] = None, open_interest: Optional[int] = None) -> Optional[BarState]:
        """返回完成的 BarState（若有）"""
        if self.current is None:
            end = self._bucket_end(ts)
            start = end - self._tf_delta()
            self.current = BarState(start=start, end=end, open=price, high=price, low=price, close=price)
        # 若已越过当前桶，完成旧 bar 并开启新 bar
        if ts >= self.current.end:
            finished = self.current
            # 开启新 bar（对齐新的桶）
            end = self._bucket_end(ts)
            start = end - self._tf_delta()
            self.current = BarState(start=start, end=end, open=price, high=price, low=price, close=price)
            # 更新新 bar 当前 tick
            self._accumulate(price, volume, open_interest)
            return finished
        # 更新当前 bar
        self._accumulate(price, volume, open_interest)
        return None

    def flush_if_due(self, now_ts: datetime) -> Optional[BarState]:
        if self.current and now_ts >= self.current.end:
            finished = self.current
            self.current = None
            return finished
        return None

    def _accumulate(self, price: float, volume: Optional[int], open_interest: Optional[int]):
        if self.current is None:
            return
        self.current.close = price
        if price > self.current.high:
            self.current.high = price
        if price < self.current.low:
            self.current.low = price
        if volume is not None:
            # 这里简单累加 tick volume；若为总量，应改为差分
            self.current.volume += max(int(volume), 0)
        if open_interest is not None:
            self.current.open_interest = int(open_interest)

    def _tf_delta(self) -> timedelta:
        return {
            TimeFrame.FIVE_MIN: timedelta(minutes=5),
            TimeFrame.TEN_MIN: timedelta(minutes=10),
            TimeFrame.THIRTY_MIN: timedelta(minutes=30),
            TimeFrame.HOURLY: timedelta(hours=1),
        }.get(self.tf, timedelta(minutes=5))


class RealtimeRecorder:
    """基于 vn.py 的实时记录器：tick→多周期K线→MongoDB"""

    def __init__(self, gateway: VNPyGateway):
        self.gateway = gateway
        self.db: Optional[DatabaseManager] = None
        # symbol_key: {tf: aggregator}
        self.aggregators: Dict[str, Dict[TimeFrame, _Aggregator]] = {}
        self._tick_task: Optional[asyncio.Task] = None
        self._running = False

    async def initialize(self):
        if self.db is None:
            # 使用新的 MongoDB DatabaseManager（自动从配置读取）
            self.db = await get_database_manager()

    def _symbol_key(self, vt_symbol: str) -> (str, str):
        # 约定 vt_symbol 形如 rb2501.SHFE
        if '.' in vt_symbol:
            sym, ex = vt_symbol.split('.', 1)
        else:
            sym, ex = vt_symbol, "UNKNOWN"
        return sym, ex

    def _ensure_aggs(self, vt_symbol: str):
        sym, ex = self._symbol_key(vt_symbol)
        key = f"{sym}.{ex}"
        if key not in self.aggregators:
            self.aggregators[key] = {
                TimeFrame.FIVE_MIN: _Aggregator(sym, ex, TimeFrame.FIVE_MIN),
                TimeFrame.TEN_MIN: _Aggregator(sym, ex, TimeFrame.TEN_MIN),
                TimeFrame.THIRTY_MIN: _Aggregator(sym, ex, TimeFrame.THIRTY_MIN),
                TimeFrame.HOURLY: _Aggregator(sym, ex, TimeFrame.HOURLY),
            }

    async def start(self, vt_symbols: List[str]):
        await self.initialize()
        self._running = True
        # 订阅市场数据
        try:
            self.gateway.subscribe_market_data(vt_symbols)
        except Exception as e:
            logger.error(f"订阅失败: {e}")
        # 注册 tick 回调
        self.gateway.register_tick_callback(self._on_tick)
        logger.info(f"RealtimeRecorder 启动，订阅: {vt_symbols}")

    async def stop(self):
        self._running = False
        logger.info("RealtimeRecorder 停止")

    def _on_tick(self, tick):
        # 将同步回调转换为异步处理
        try:
            asyncio.create_task(self._handle_tick_async(tick))
        except RuntimeError:
            # 无事件循环时直接同步处理（测试环境）
            asyncio.run(self._handle_tick_async(tick))

    async def _handle_tick_async(self, tick):
        if not self._running:
            return
        try:
            ts: datetime = getattr(tick, 'datetime', None) or getattr(tick, 'trade_time', None) or datetime.now()
            price: float = float(getattr(tick, 'last_price', 0.0) or 0.0)
            vol: Optional[int] = getattr(tick, 'volume', None)
            oi: Optional[int] = getattr(tick, 'open_interest', None)
            vt_symbol: str = getattr(tick, 'vt_symbol', '')
            if not vt_symbol or price <= 0:
                return

            self._ensure_aggs(vt_symbol)
            sym, ex = self._symbol_key(vt_symbol)
            key = f"{sym}.{ex}"
            finished: List[BarState] = []
            for agg in self.aggregators[key].values():
                done = agg.update(ts, price, vol, oi)
                if done:
                    finished.append(done)

            if finished and self.db:
                await self._flush(sym, ex, finished)
        except Exception as e:
            logger.error(f"处理 tick 失败: {e}")

    async def _flush(self, symbol: str, exchange: str, bars: List[BarState]):
        # 将完成的 bars 写入 DB
        try:
            points: List[MarketDataPoint] = []
            tf_map = {
                timedelta(minutes=5): TimeFrame.FIVE_MIN,
                timedelta(minutes=10): TimeFrame.TEN_MIN,
                timedelta(minutes=30): TimeFrame.THIRTY_MIN,
                timedelta(hours=1): TimeFrame.HOURLY,
            }
            for bar in bars:
                tf = tf_map.get(bar.end - bar.start, TimeFrame.FIVE_MIN)
                points.append(
                    MarketDataPoint(
                        timestamp=bar.end,
                        open=bar.open,
                        high=bar.high,
                        low=bar.low,
                        close=bar.close,
                        volume=bar.volume,
                        open_interest=bar.open_interest,
                    )
                )
                await self.db.store_market_data(symbol, exchange, tf, [points[-1]])
            logger.debug(f"写入 {symbol}.{exchange} bars: {len(bars)}")
        except Exception as e:
            logger.error(f"写入 DB 失败: {e}")
