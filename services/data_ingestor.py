# ruff: noqa: E402
"""
Data Ingestor Service
Periodically pulls recent futures data (AKShare) and stores OHLCV into TimescaleDB via DatabaseManager.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List
from pathlib import Path
import sys

# Add project root to sys.path for absolute imports when run as a script
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import akshare as ak

from adapters.data_storage.database_manager import get_database_manager
from adapters.data_storage.timeframe_data_manager import TimeFrame, MarketDataPoint
from adapters.data_adapter.multi_symbol_manager import ChineseFuturesMarket
from config.database_config import DATABASE_CONFIG

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
    mapping = ChineseFuturesMarket.AKSHARE_MAPPING.get(exchange, {})
    return mapping.get(symbol, symbol.upper())


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
    try:
        df = ak.futures_main_sina(symbol=ak_symbol)
        if df is None or df.empty:
            return
        df = df.sort_values("datetime").tail(RECENT_POINTS)
        points = _to_points(df)
        await db.store_market_data(symbol, exchange, TimeFrame.FIVE_MIN, points)
        logger.info(f"Stored {len(points)} bars for {symbol}.{exchange}")
    except Exception as e:
        logger.debug(f"Ingest failed for {symbol}.{exchange}: {e}")


async def run_loop() -> None:
    setup_logging()
    logger.info("Starting data ingestor service …")
    db = await get_database_manager(DATABASE_CONFIG)

    market = ChineseFuturesMarket()
    exchanges: Dict[str, Dict[str, str]] = market.EXCHANGE_SYMBOLS

    while True:
        try:
            tasks = []
            for exchange, symbols in exchanges.items():
                count = 0
                for sym in symbols.keys():
                    if count >= DEFAULT_SYMBOL_LIMIT:
                        break
                    ak_code = _ak_code(exchange, sym)
                    tasks.append(ingest_once(db, exchange, sym, ak_code))
                    count += 1
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Ingest loop error: {e}")
        finally:
            await asyncio.sleep(FETCH_INTERVAL_SECONDS)


def main() -> None:
    asyncio.run(run_loop())


if __name__ == "__main__":
    main()
