# ruff: noqa: E402
"""
Data Ingestor Service
⚠️  已废弃 - 此服务依赖 AKShare，已被 QuantBox 替代
============================================================================
推荐使用：
1. HistoryDataManager (基于 QuantBox) - 用于历史数据获取
2. RealtimeRecorder (基于 VNPy) - 用于实时数据记录
============================================================================
此文件保留仅用于参考，不应在生产环境中使用
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List


# import akshare as ak  # 已废弃，使用 QuantBox 替代

from cherryquant.adapters.data_storage.timeframe_data_manager import TimeFrame, MarketDataPoint
from cherryquant.adapters.data_adapter.multi_symbol_manager import ChineseFuturesMarket

logger = logging.getLogger("data_ingestor")

DEFAULT_SYMBOL_LIMIT = 50  # per exchange
FETCH_INTERVAL_SECONDS = 60  # run every minute
RECENT_POINTS = 120  # how many recent rows to keep per run


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def _ak_code(exchange: str, symbol: str) -> str:
    """
    Convert internal symbol to AKShare main continuous code.
    Rules:
    - If symbol contains digits (e.g., rb2501), strip digits to get commodity
    - Use uppercase commodity + '0' (e.g., rb -> RB0, IF -> IF0)
    - Fallback to uppercased input
    """
    try:
        import re
        commodity = re.sub(r"\d+", "", symbol or "").strip()
        if not commodity:
            return (symbol or "").upper()
        # Some AKShare codes are single-letter (e.g., i -> I0) or multi-letter (jm -> JM0)
        return f"{commodity.upper()}0"
    except Exception:
        return (symbol or "").upper()


def _to_points(df) -> List[MarketDataPoint]:
    points: List[MarketDataPoint] = []
    for _, row in df.iterrows():
        ts = row["datetime"] if "datetime" in df.columns else datetime.now()
        points.append(
            MarketDataPoint(
                timestamp=ts,
                open=float(row.get("open", row["close"])),
                high=float(row.get("high", row["close"])),
                low=float(row.get("low", row["close"])),
                close=float(row["close"]),
                volume=int(row.get("volume", 0)),
            )
        )
    return points


async def ingest_once(db, exchange: str, symbol: str, ak_symbol: str) -> None:
    """已废弃 - AKShare 已移除"""
    logger.warning("⚠️  ingest_once 已废弃，请使用 HistoryDataManager (QuantBox) 或 RealtimeRecorder (VNPy)")
    return
    # try:
    #     df = ak.futures_main_sina(symbol=ak_symbol)  # AKShare 已移除
    #     if df is None or df.empty:
    #         return
    #     df = df.sort_values("datetime").tail(RECENT_POINTS)
    #     points = _to_points(df)
    #     await db.store_market_data(symbol, exchange, TimeFrame.FIVE_MIN, points)
    #     logger.info(f"Stored {len(points)} bars for {symbol}.{exchange}")
    # except Exception as e:
    #     logger.debug(f"Ingest failed for {symbol}.{exchange}: {e}")


async def run_loop() -> None:
    """已废弃的轮询主循环占位实现.

    历史说明：原本通过 AKShare + DatabaseManager 定时拉取主力合约数据，
    现已由 QuantBox 历史数据 + vn.py RealtimeRecorder 取代。
    这个占位实现仅保留日志提示，避免误用旧接口。
    """
    setup_logging()
    logger.warning(
        "⚠️  DataIngestor 服务已废弃，请使用 HistoryDataManager(QuantBox) 和 RealtimeRecorder(vn.py) 替代"
    )
    return


def main() -> None:
    asyncio.run(run_loop())


if __name__ == "__main__":
    main()
