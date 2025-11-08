#!/usr/bin/env python3
"""
历史数据初始化工具
用于首次启动时批量下载期货历史数据到数据库
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
import pandas as pd



from cherryquant.adapters.data_storage.database_manager import get_database_manager
from cherryquant.adapters.data_storage.timeframe_data_manager import TimeFrame, MarketDataPoint
from config.database_config import get_database_config
import tushare as ts

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HistoricalDataInitializer:
    """历史数据初始化器"""

    # 主流期货品种
    POPULAR_SYMBOLS = {
        "SHFE": ["rb", "hc", "cu", "al", "zn", "au", "ag", "ni"],  # 上期所
        "DCE": ["i", "j", "jm", "a", "c", "m", "y", "p"],  # 大商所
        "CZCE": ["SR", "CF", "TA", "MA", "RM", "OI"],  # 郑商所
        "CFFEX": ["IF", "IC", "IH", "T", "TF"]  # 中金所
    }

    # 数据下载策略
    DATA_STRATEGIES = {
        "1d": {"name": "日线", "days": 365, "desc": "最近1年"},
        "1m": {"name": "1分钟", "days": 5, "desc": "最近5天"},
        "5m": {"name": "5分钟", "days": 30, "desc": "最近1个月"},
        "10m": {"name": "10分钟", "days": 60, "desc": "最近2个月"},
        "30m": {"name": "30分钟", "days": 180, "desc": "最近半年"},
        "1h": {"name": "1小时", "days": 365, "desc": "最近1年"},
    }

    def __init__(self, tushare_token: str):
        """初始化"""
        self.tushare_token = tushare_token
        self.tushare_pro = None
        self.db_manager = None

        if tushare_token and tushare_token != "your_tushare_pro_token_here":
            try:
                ts.set_token(tushare_token)
                self.tushare_pro = ts.pro_api()
                logger.info("✅ Tushare Pro API 初始化成功")
            except Exception as e:
                logger.error(f"❌ Tushare Pro API 初始化失败: {e}")
        else:
            logger.warning("⚠️ Tushare Token 未配置")

    async def _ensure_db_manager(self) -> None:
        """确保数据库管理器已初始化"""
        if self.db_manager is None:
            db_config = get_database_config()
            self.db_manager = await get_database_manager(db_config)
            logger.info("✅ 数据库连接已建立")

    async def check_database_status(self) -> Dict[str, int]:
        """检查数据库中的数据状态"""
        try:
            await self._ensure_db_manager()

            async with self.db_manager.postgres_pool.acquire() as conn:
                # 统计各时间周期的数据量
                stats = {}
                for timeframe in ["5m", "10m", "30m", "1H", "1d"]:
                    result = await conn.fetchval(
                        "SELECT COUNT(*) FROM market_data WHERE timeframe = $1",
                        timeframe
                    )
                    stats[timeframe] = result or 0

                return stats

        except Exception as e:
            logger.error(f"检查数据库状态失败: {e}")
            return {}

    async def download_futures_data(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
        days: int
    ) -> List[MarketDataPoint]:
        """下载期货历史数据"""
        if not self.tushare_pro:
            logger.error("Tushare API 未初始化")
            return []

        try:
            # 计算时间范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # Tushare 品种代码格式（需要主力合约）
            # 简化处理：暂时使用当前主力合约
            ts_code = self._get_dominant_contract(symbol, exchange)

            if not ts_code:
                logger.warning(f"无法获取 {symbol} 的主力合约")
                return []

            # 根据时间周期选择API
            if timeframe == "1d":
                # 日线数据
                df = self.tushare_pro.fut_daily(
                    ts_code=ts_code,
                    start_date=start_date.strftime("%Y%m%d"),
                    end_date=end_date.strftime("%Y%m%d")
                )
                all_data_points = self._convert_dataframe_to_points(df, timeframe)
            else:
                # 分钟线数据（需要2000+积分）- 需要分页获取
                all_data_points = await self._download_minutes_data_paginated(
                    ts_code, symbol, exchange, timeframe, start_date, end_date
                )

            logger.info(f"✅ 下载 {symbol}.{exchange} {timeframe} 数据: {len(all_data_points)} 条")
            return all_data_points

        except Exception as e:
            logger.error(f"下载 {symbol} 数据失败: {e}")
            return []

    async def _download_minutes_data_paginated(
        self,
        ts_code: str,
        symbol: str,
        exchange: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[MarketDataPoint]:
        """分页下载分钟线数据，处理8000条限制"""
        freq_map = {
            "5m": "5min",
            "10m": "10min",
            "30m": "30min",
            "1h": "60min"
        }
        freq = freq_map.get(timeframe, "5min")

        # 根据频率计算安全的时间间隔（确保不超过8000条）
        interval_days = self._get_safe_interval_days(timeframe)

        all_data_points = []
        current_start = start_date

        while current_start < end_date:
            # 计算当前批次的结束时间
            current_end = min(current_start + timedelta(days=interval_days), end_date)

            try:
                logger.debug(f"下载 {symbol}.{exchange} {timeframe} 数据: {current_start} 到 {current_end}")

                df = self.tushare_pro.ft_mins(
                    ts_code=ts_code,
                    freq=freq,
                    start_date=current_start.strftime("%Y%m%d %H:%M:%S"),
                    end_date=current_end.strftime("%Y%m%d %H:%M:%S")
                )

                if df is not None and not df.empty:
                    batch_points = self._convert_dataframe_to_points(df, timeframe)
                    all_data_points.extend(batch_points)
                    logger.debug(f"批次获取 {len(batch_points)} 条数据")

                    # 如果获取到了数据，正常移动到下一个时间段
                    current_start = current_end
                else:
                    logger.debug(f"批次无数据: {current_start} 到 {current_end}")
                    # 如果没有数据，可能是因为周末/节假日，尝试跳过更大的间隔
                    # 但也要避免无限循环，所以至少前进1天
                    next_start = current_start + timedelta(days=1)
                    if next_start <= current_end:
                        current_start = next_start
                    else:
                        current_start = current_end

                # 避免请求过快
                await asyncio.sleep(0.3)

            except Exception as e:
                logger.error(f"下载批次数据失败 ({current_start} 到 {current_end}): {e}")
                # 如果连续失败，跳过这个时间段
                current_start = current_end
                await asyncio.sleep(1)  # 延长等待时间

        return all_data_points

    def _get_safe_interval_days(self, timeframe: str) -> int:
        """根据时间周期返回安全的天数间隔（确保不超过8000条）"""
        # 更精确的计算，考虑交易时间（假设每天6.5小时交易时间）
        # 实际期货交易时间更长，但保守估计使用6.5小时
        trading_hours_per_day = 6.5

        if timeframe == "1m":
            minutes_per_day = int(trading_hours_per_day * 60)  # ~390分钟/天
            safe_days = int(8000 / minutes_per_day * 0.9)  # 90%安全系数
            return max(1, safe_days)  # 至少1天
        elif timeframe == "5m":
            intervals_per_day = int(trading_hours_per_day * 12)  # ~78个5分钟K线/天
            safe_days = int(8000 / intervals_per_day * 0.9)
            return max(5, safe_days)
        elif timeframe == "10m":
            intervals_per_day = int(trading_hours_per_day * 6)  # ~39个10分钟K线/天
            safe_days = int(8000 / intervals_per_day * 0.9)
            return max(10, safe_days)
        elif timeframe == "30m":
            intervals_per_day = int(trading_hours_per_day * 2)  # ~13个30分钟K线/天
            safe_days = int(8000 / intervals_per_day * 0.9)
            return max(30, safe_days)
        elif timeframe == "1h":
            intervals_per_day = int(trading_hours_per_day)  # ~6个1小时K线/天
            safe_days = int(8000 / intervals_per_day * 0.9)
            return max(60, safe_days)
        else:
            # 默认使用5m的设置
            return 25

    def _convert_dataframe_to_points(self, df, timeframe: str) -> List[MarketDataPoint]:
        """将DataFrame转换为MarketDataPoint列表"""
        if df is None or df.empty:
            return []

        data_points = []
        for _, row in df.iterrows():
            try:
                # 分钟线数据的trade_date格式可能是 "YYYY-MM-DD HH:MM:SS"
                trade_date_str = str(row['trade_date'])
                if ' ' in trade_date_str:
                    # 分钟线格式
                    timestamp = datetime.strptime(trade_date_str, "%Y-%m-%d %H:%M:%S")
                else:
                    # 日线格式
                    timestamp = datetime.strptime(trade_date_str, "%Y%m%d")

                dp = MarketDataPoint(
                    timestamp=timestamp,
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=int(row['vol']) if 'vol' in row and pd.notna(row['vol']) else 0,
                    open_interest=int(row['oi']) if 'oi' in row and pd.notna(row['oi']) else 0
                )
                data_points.append(dp)
            except Exception as e:
                logger.debug(f"转换数据点失败: {e}")
                continue

        return data_points

    def _get_dominant_contract(self, symbol: str, exchange: str) -> Optional[str]:
        """获取主力合约代码（简化版本）"""
        try:
            # 查询主力合约映射
            df = self.tushare_pro.fut_mapping(ts_code=f"{symbol.upper()}.{exchange}")
            if df is not None and not df.empty:
                return df.iloc[0]['mapping_ts_code']
        except Exception as e:
            logger.debug(f"获取主力合约失败: {e}")

        # 降级方案：推算近月合约
        year = datetime.now().year
        month = datetime.now().month + 1
        if month > 12:
            year += 1
            month = 1

        return f"{symbol}{year % 100}{month:02d}.{exchange}"

    async def save_to_database(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
        data_points: List[MarketDataPoint]
    ) -> int:
        """保存数据到数据库"""
        if not self.db_manager or not data_points:
            return 0

        try:
            saved = 0
            async with self.db_manager.postgres_pool.acquire() as conn:
                for dp in data_points:
                    try:
                        await conn.execute(
                            """
                            INSERT INTO market_data (
                                time, symbol, exchange, timeframe,
                                open_price, high_price, low_price, close_price,
                                volume, open_interest
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                            ON CONFLICT (time, symbol, exchange, timeframe) DO NOTHING
                            """,
                            dp.timestamp, symbol, exchange, timeframe,
                            dp.open, dp.high, dp.low, dp.close,
                            dp.volume, dp.open_interest
                        )
                        saved += 1
                    except Exception as e:
                        logger.debug(f"保存数据点失败: {e}")
                        continue

            logger.info(f"💾 保存 {symbol}.{exchange} {timeframe}: {saved}/{len(data_points)} 条")
            return saved

        except Exception as e:
            logger.error(f"保存数据到数据库失败: {e}")
            return 0

    async def initialize_data(
        self,
        symbols: Optional[Dict[str, List[str]]] = None,
        timeframes: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, int]]:
        """初始化历史数据"""
        # 确保数据库连接已建立
        await self._ensure_db_manager()

        if symbols is None:
            symbols = self.POPULAR_SYMBOLS

        if timeframes is None:
            timeframes = ["1d", "5m", "30m", "1h"]

        results = {}
        total_downloaded = 0
        total_saved = 0

        print("\n" + "="*70)
        print("🚀 开始下载历史数据")
        print("="*70)

        for exchange, symbol_list in symbols.items():
            results[exchange] = {}

            for symbol in symbol_list:
                print(f"\n📊 处理品种: {symbol}.{exchange}")

                for tf in timeframes:
                    strategy = self.DATA_STRATEGIES.get(tf, {})
                    days = strategy.get("days", 30)
                    desc = strategy.get("desc", "")

                    print(f"  ⏬ 下载 {tf} 数据 ({desc})...", end=" ", flush=True)

                    # 下载数据
                    data_points = await self.download_futures_data(
                        symbol, exchange, tf, days
                    )

                    if data_points:
                        # 保存到数据库
                        saved = await self.save_to_database(
                            symbol, exchange, tf, data_points
                        )
                        results[exchange][f"{symbol}_{tf}"] = saved
                        total_downloaded += len(data_points)
                        total_saved += saved
                        print(f"✅ {saved} 条")
                    else:
                        print("⚠️ 无数据")

                    # 避免请求过快
                    await asyncio.sleep(0.5)

        print("\n" + "="*70)
        print(f"✅ 数据初始化完成！")
        print(f"📥 共下载: {total_downloaded} 条")
        print(f"💾 已保存: {total_saved} 条")
        print("="*70 + "\n")

        return results


async def interactive_init():
    """交互式初始化"""
    print("\n" + "="*70)
    print("🍒 CherryQuant 历史数据初始化工具")
    print("="*70)

    # 获取 Tushare Token
    tushare_token = os.getenv("TUSHARE_TOKEN")
    if not tushare_token or tushare_token == "your_tushare_pro_token_here":
        print("\n❌ 错误: TUSHARE_TOKEN 未配置")
        print("请在 .env 文件中配置 TUSHARE_TOKEN")
        print("注意: 下载分钟线数据需要 Tushare Pro 2000+ 积分")
        return

    # 初始化器
    initializer = HistoricalDataInitializer(tushare_token)

    # 检查数据库状态
    print("\n🔍 检查数据库状态...")
    stats = await initializer.check_database_status()

    print("\n当前数据库中的数据量:")
    for tf, count in stats.items():
        print(f"  {tf:6s}: {count:8d} 条")

    total_records = sum(stats.values())
    print(f"\n总计: {total_records} 条记录")

    # 询问是否需要下载
    if total_records > 0:
        print("\n数据库中已有数据。")
        response = input("是否要重新下载/补充数据？(y/n): ").lower().strip()
        if response != 'y':
            print("已取消。")
            return
    else:
        print("\n⚠️  数据库为空，建议下载历史数据以启动系统。")
        response = input("是否现在下载？(y/n): ").lower().strip()
        if response != 'y':
            print("已取消。可以随时运行此脚本初始化数据。")
            return

    # 选择下载策略
    print("\n请选择要下载的数据类型:")
    print("  1. 仅日线数据 (快速，适合测试)")
    print("  2. 日线 + 小时线 (推荐)")
    print("  3. 全部数据 (日线、小时、30分钟、10分钟、5分钟、1分钟)")
    print("  4. 自定义")

    choice = input("请输入选项 (1-4, 默认 2): ").strip() or "2"

    if choice == "1":
        timeframes = ["1d"]
    elif choice == "2":
        timeframes = ["1d", "1h"]
    elif choice == "3":
        timeframes = ["1d", "1h", "30m", "10m", "5m", "1m"]
    elif choice == "4":
        print("\n可选时间周期: 1d, 1h, 30m, 10m, 5m, 1m")
        tf_input = input("请输入时间周期（用空格分隔）: ").strip()
        timeframes = tf_input.split()
    else:
        timeframes = ["1d", "1h"]

    print(f"\n将下载以下时间周期: {', '.join(timeframes)}")

    # 显示下载策略
    print("\n数据下载策略:")
    for tf in timeframes:
        strategy = initializer.DATA_STRATEGIES.get(tf, {})
        print(f"  {tf:6s}: {strategy.get('desc', 'N/A')}")

    # 选择品种
    print("\n选择要下载的品种:")
    print("  1. 主流品种 (黑色系、有色、化工、农产品、金融，约30个品种)")
    print("  2. 仅黑色系 (rb, hc, i, j, jm)")
    print("  3. 全部品种 (所有交易所)")

    symbol_choice = input("请输入选项 (1-3, 默认 1): ").strip() or "1"

    if symbol_choice == "2":
        symbols = {"SHFE": ["rb", "hc"], "DCE": ["i", "j", "jm"]}
    elif symbol_choice == "3":
        symbols = initializer.POPULAR_SYMBOLS
    else:
        # 主流品种（简化）
        symbols = {
            "SHFE": ["rb", "hc", "cu", "al"],
            "DCE": ["i", "j", "jm", "m"],
            "CZCE": ["SR", "CF", "TA"],
            "CFFEX": ["IF", "IC"]
        }

    # 确认
    total_combinations = sum(len(v) for v in symbols.values()) * len(timeframes)
    print(f"\n将下载 {total_combinations} 个数据集")
    print("⚠️  注意: 这可能需要几分钟到十几分钟时间")

    confirm = input("\n确认开始下载？(y/n): ").lower().strip()
    if confirm != 'y':
        print("已取消。")
        return

    # 开始下载
    results = await initializer.initialize_data(symbols, timeframes)

    print("\n✅ 初始化完成！现在可以启动 CherryQuant 系统了。")


async def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] == '--auto':
        # 自动模式：快速初始化最小数据集
        print("🤖 自动模式：快速初始化...")
        tushare_token = os.getenv("TUSHARE_TOKEN")
        initializer = HistoricalDataInitializer(tushare_token)

        # 仅下载主流品种的日线数据
        symbols = {
            "SHFE": ["rb", "cu"],
            "DCE": ["i", "j"],
        }
        await initializer.initialize_data(symbols, ["1d"])
    else:
        # 交互模式
        await interactive_init()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 已取消")
    except Exception as e:
        logger.error(f"程序异常: {e}", exc_info=True)
