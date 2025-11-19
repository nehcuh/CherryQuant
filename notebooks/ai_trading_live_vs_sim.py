"""AI Trading: 模拟账户 vs 实盘执行 对比示例

本脚本示范如何在 Jupyter Notebook / IPython 环境中
通过 CherryQuant Web API 对比：
- StrategyAgent 记录的模拟交易 (recent_trades)
- KLineOrderManager 回传的实盘执行 (live_executions)

使用方式（推荐在项目根目录下运行）：

1. 先启动完整系统（包含 Web API）：

    uv run python scripts/runners/run_cherryquant_complete.py

2. 在另一个终端 / Jupyter Lab 中运行此脚本或将其逐段拷贝到 Notebook：

    uv run python notebooks/ai_trading_live_vs_sim.py

3. 将其复制到 `ai_trading_live_vs_sim.ipynb` 中，可作为课堂示例使用。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import List, Dict, Any

import pandas as pd
import requests

try:
    import matplotlib.pyplot as plt
except ImportError:  # 在无图形环境或未安装 matplotlib 时降级为纯表格模式
    plt = None

# 根据实际部署修改；默认假设 CherryQuant API 运行在本机 8000 端口
BASE_URL = "http://localhost:8000"

# 示例策略 ID：默认使用 config/strategies.json 中的 trend_following_01
DEFAULT_STRATEGY_ID = "trend_following_01"


def fetch_strategy_executions(
    strategy_id: str,
    base_url: str = BASE_URL,
) -> Dict[str, Any]:
    """从 Web API 获取单个策略的模拟交易与实盘执行信息。

    依赖端点：GET /api/v1/strategies/{strategy_id}/executions
    """
    url = f"{base_url}/api/v1/strategies/{strategy_id}/executions"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def to_dataframe(records: List[Dict[str, Any]]) -> pd.DataFrame:
    """辅助函数：将记录列表转为 DataFrame，并尝试解析时间字段。"""
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # 尝试解析常见时间字段
    for col in ["timestamp", "entry_time"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="ignore")

    return df


def compute_simulated_pnl(sim_df: pd.DataFrame) -> pd.DataFrame:
    """根据 recent_trades 计算模拟账户的累计盈亏曲线。"""
    if sim_df.empty or "pnl" not in sim_df.columns:
        return pd.DataFrame()

    t_col = "timestamp" if "timestamp" in sim_df.columns else "entry_time"
    df = sim_df.copy()
    df[t_col] = pd.to_datetime(df[t_col], errors="coerce")
    df = df.dropna(subset=[t_col])
    df = df.sort_values(t_col)
    df["cum_pnl"] = df["pnl"].cumsum()
    return df[[t_col, "cum_pnl"]].rename(columns={t_col: "timestamp"})


def compute_live_pnl(live_df: pd.DataFrame) -> pd.DataFrame:
    """根据 live_executions 近似计算实盘执行的累计已实现盈亏曲线。

    简化规则：
    - 按 symbol 维护持仓 pos (>0 多头, <0 空头) 和平均持仓价 avg_price
    - 方向为 long/short 或 buy/sell
    - 反向成交优先用于平仓，产生 realized_pnl；超出部分视为反向开仓
    - 注意：此处仅计算【已实现盈亏】(Realized PnL)，忽略持仓浮盈 (Unrealized PnL)，与 StrategyAgent 的模拟逻辑一致。
    """
    if live_df.empty:
        return pd.DataFrame()
    if "timestamp" not in live_df.columns:
        return pd.DataFrame()

    df = live_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    df = df.sort_values("timestamp")

    required = {"direction", "volume", "price"}
    if not required.issubset(df.columns):
        return pd.DataFrame()

    state: Dict[str, Dict[str, Any]] = {}
    records: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        symbol = row.get("symbol")
        if not symbol:
            continue
        direction = str(row.get("direction") or "").lower()
        qty = row.get("volume")
        price = row.get("price")
        ts = row["timestamp"]
        if qty is None or price is None:
            continue

        sign = 1 if direction in ("long", "buy") else -1 if direction in ("short", "sell") else None
        if sign is None:
            continue

        sym_state = state.setdefault(symbol, {"pos": 0, "avg_price": 0.0, "realized_pnl": 0.0})
        pos = sym_state["pos"]
        avg_price = sym_state["avg_price"]
        realized = sym_state["realized_pnl"]
        remaining = float(qty)

        # 1) 先用反向成交平仓
        if pos != 0 and pos * sign < 0:
            closing_qty = min(abs(pos), remaining)
            if closing_qty > 0:
                if pos > 0 and sign == -1:  # 多头平仓
                    realized += (price - avg_price) * closing_qty
                elif pos < 0 and sign == 1:  # 空头平仓
                    realized += (avg_price - price) * closing_qty
                pos += sign * closing_qty
                remaining -= closing_qty
                if pos == 0:
                    avg_price = 0.0

        # 2) 剩余部分按当前方向开仓/加仓
        if remaining > 0:
            if pos == 0 or pos * sign > 0:
                total_qty = abs(pos) + remaining
                if total_qty > 0:
                    if pos == 0:
                        avg_price = price
                    else:
                        avg_price = (avg_price * abs(pos) + price * remaining) / total_qty
                pos += sign * remaining

        sym_state["pos"] = pos
        sym_state["avg_price"] = avg_price
        sym_state["realized_pnl"] = realized

        records.append({"timestamp": ts, "symbol": symbol, "cum_pnl": realized})

    if not records:
        return pd.DataFrame()

    res = pd.DataFrame(records)
    # 汇总到策略级别：同一时间点按 symbol 求和
    res = res.groupby("timestamp", as_index=False)["cum_pnl"].sum()
    return res


def main(strategy_id: str = DEFAULT_STRATEGY_ID) -> None:
    print(f"=== Fetching executions for strategy: {strategy_id} ===")

    data = fetch_strategy_executions(strategy_id)
    recent_trades = data.get("recent_trades", [])
    live_executions = data.get("live_executions", [])

    sim_df = to_dataframe(recent_trades)
    live_df = to_dataframe(live_executions)

    print("\n[1] 模拟交易（StrategyAgent 内部） recent_trades — 前几行：")
    if sim_df.empty:
        print("  (无模拟交易记录)")
    else:
        print(sim_df.head())

    print("\n[2] 实盘执行（KLineOrderManager 回调） live_executions — 前几行：")
    if live_df.empty:
        print("  (无实盘执行记录；可能尚未在 Live 模式真实下单)")
    else:
        print(live_df.head())

    # 示例：按时间对比累计 PnL
    if not sim_df.empty and not live_df.empty:
        print("\n[3] 简单统计对比：")
        print(f"  模拟交易笔数: {len(sim_df)}")
        print(f"  实盘执行笔数: {len(live_df)}")

        sim_pnl = compute_simulated_pnl(sim_df)
        live_pnl = compute_live_pnl(live_df)

        if plt is not None and not sim_pnl.empty and not live_pnl.empty:
            plt.figure(figsize=(10, 4))
            sim_pnl.set_index("timestamp")["cum_pnl"].plot(label="Sim PnL", alpha=0.8)
            live_pnl.set_index("timestamp")["cum_pnl"].plot(label="Live PnL", alpha=0.8)
            plt.title(f"Strategy {strategy_id}: 模拟账户 vs 实盘执行 累计盈亏对比")
            plt.xlabel("时间")
            plt.ylabel("累计盈亏 (单位制约略)")
            plt.legend()
            plt.tight_layout()
            plt.show()
        elif plt is not None:
            print("(提示：PnL 数据不足，无法绘制 PnL 曲线)")
        else:
            print("(提示：未安装 matplotlib，仅展示表格统计)")


if __name__ == "__main__":
    main()
