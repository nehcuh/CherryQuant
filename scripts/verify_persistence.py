# ruff: noqa: E402
"""
Verification script: persists market_data (AKShare), creates an AI decision and a trade entry/close,
then prints row counts from TimescaleDB.
"""

import asyncio
from datetime import datetime
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import akshare as ak
from adapters.data_storage.database_manager import get_database_manager
from adapters.data_storage.timeframe_data_manager import TimeFrame, MarketDataPoint
from config.database_config import DATABASE_CONFIG


async def main() -> None:
    db = await get_database_manager(DATABASE_CONFIG)

    # 1) Persist recent bars for rb.SHFE from AKShare
    import pandas as pd
    df = ak.futures_main_sina(symbol="RB0")
    assert df is not None and not df.empty, "AKShare returned empty data for RB0"
    # Standardize time column
    if "datetime" not in df.columns:
        if "date" in df.columns:
            df["datetime"] = pd.to_datetime(df["date"])  # type: ignore
        elif "time" in df.columns:
            df["datetime"] = pd.to_datetime(df["time"])  # type: ignore
        else:
            df["datetime"] = pd.Timestamp.utcnow()
    df = df.sort_values("datetime").tail(60)
    points = [
        MarketDataPoint(
            timestamp=row["datetime"],
            open=float(row.get("open", row.get("close", 0)) or 0),
            high=float(row.get("high", row.get("close", 0)) or 0),
            low=float(row.get("low", row.get("close", 0)) or 0),
            close=float(row.get("close", 0) or 0),
            volume=int(row.get("volume", 0) or 0),
        )
        for _, row in df.iterrows()
    ]
    await db.store_market_data("rb", "SHFE", TimeFrame.FIVE_MIN, points)

    # 2) Create an AI decision record
    last_row = df.iloc[-1]
    last_close = float(
        last_row.get("close", last_row.get("price", last_row.get("open", 0))) or 0
    )
    decision = {
        "decision_time": datetime.now(),
        "symbol": "rb",
        "exchange": "SHFE",
        "action": "buy_to_enter",
        "quantity": 1,
        "leverage": 5,
        "entry_price": last_close,
        "profit_target": last_close * 1.02,
        "stop_loss": last_close * 0.98,
        "confidence": 0.6,
        "opportunity_score": 70,
        "selection_rationale": "Verification decision",
        "technical_analysis": "Verification",
        "risk_factors": "Verification",
        "market_regime": "trending",
        "volatility_index": "medium",
        "status": "pending",
    }
    decision_ok = await db.store_ai_decision(decision)

    # 3) Create a trade entry referencing the decision, then close it
    trade_id = await db.create_trade_entry(
        {
            "symbol": "rb",
            "exchange": "SHFE",
            "direction": "long",
            "quantity": 1,
            "entry_price": decision["entry_price"],
            "entry_time": datetime.now(),
            "entry_fee": 0.0,
            "ai_decision_id": decision.get("id"),
        }
    )
    assert trade_id is not None, "Failed to create trade entry"

    await db.close_trade(
        trade_id=trade_id,
        exit_price=decision["entry_price"] * 1.001,
        exit_time=datetime.now(),
        exit_fee=0.0,
        gross_pnl=(decision["entry_price"] * 0.001),
        net_pnl=(decision["entry_price"] * 0.001),
        pnl_percentage=None,
    )

    # 4) Simple counts
    stats = await db.get_data_statistics()
    print("OK: market_data total:", stats.get("market_data", {}).get("total_records", 0))
    print("OK: ai_decisions total:", stats.get("ai_decisions", {}).get("total_decisions", 0))
    print("OK: trades total:", stats.get("trades", {}).get("total_trades", 0))


if __name__ == "__main__":
    asyncio.run(main())
