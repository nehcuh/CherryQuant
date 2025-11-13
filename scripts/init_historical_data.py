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
from src.cherryquant.utils.symbol_standardizer import SymbolStandardizer
import tushare as ts

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
            self.db_manager = await get_database_manager()
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
        days: int,
        contracts: Optional[List[str]] = None
    ):
        """下载期货历史数据（所有有效合约）

        Args:
            symbol: 品种代码
            exchange: 交易所代码
            timeframe: 时间周期
            days: 回溯天数
            contracts: 可选的合约列表，如果不提供则自动获取

        Returns:
            List[Tuple[str, str, MarketDataPoint]]: 包含 (合约代码, 交易所, 数据点) 的列表
        """
        if not self.tushare_pro:
            logger.error("Tushare API 未初始化")
            return []

        try:
            # 计算时间范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # 如果没有提供合约列表，则获取该品种的所有有效合约
            if contracts is None:
                contracts = self._get_active_contracts(symbol, exchange, months_back=12)

            if not contracts:
                logger.warning(f"未找到 {symbol}.{exchange} 的有效合约")
                return []

            logger.debug(f"准备下载 {symbol}.{exchange} 的 {len(contracts)} 个合约: {contracts}")

            all_data_points = []

            # 逐个合约下载数据
            for ts_code in contracts:
                try:
                    # 根据时间周期选择API
                    if timeframe == "1d":
                        # 日线数据
                        df = self.tushare_pro.fut_daily(
                            ts_code=ts_code,
                            start_date=start_date.strftime("%Y%m%d"),
                            end_date=end_date.strftime("%Y%m%d")
                        )
                        # 提取合约代码
                        contract_data = self._convert_dataframe_to_points(df, timeframe, extract_symbol=True)
                    else:
                        # 分钟线数据（需要2000+积分）- 需要分页获取
                        contract_data = await self._download_minutes_data_paginated(
                            ts_code, symbol, exchange, timeframe, start_date, end_date
                        )

                    if contract_data:
                        all_data_points.extend(contract_data)
                        logger.debug(f"  合约 {ts_code}: {len(contract_data)} 条")

                    # 避免请求过快
                    await asyncio.sleep(0.3)

                except Exception as e:
                    logger.warning(f"下载合约 {ts_code} 数据失败: {e}")
                    continue

            logger.info(f"✅ 下载 {symbol}.{exchange} {timeframe} 数据: {len(all_data_points)} 条 (来自 {len(contracts)} 个合约)")
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
    ):
        """分页下载分钟线数据，处理8000条限制和API限流

        Returns:
            List[Tuple[str, str, MarketDataPoint]]: 包含 (合约代码, 交易所, 数据点) 的列表
        """
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
        retry_count = 0
        max_retries = 3

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
                    batch_points = self._convert_dataframe_to_points(df, timeframe, extract_symbol=True)
                    all_data_points.extend(batch_points)
                    logger.debug(f"批次获取 {len(batch_points)} 条数据")

                    # 如果获取到了数据，正常移动到下一个时间段
                    current_start = current_end
                    retry_count = 0  # 重置重试计数
                else:
                    logger.debug(f"批次无数据: {current_start} 到 {current_end}")
                    # 如果没有数据，可能是因为周末/节假日，尝试跳过更大的间隔
                    # 但也要避免无限循环，所以至少前进1天
                    next_start = current_start + timedelta(days=1)
                    if next_start <= current_end:
                        current_start = next_start
                    else:
                        current_start = current_end
                    retry_count = 0

                # 避免请求过快 - 分钟线数据有严格的限流（每分钟2次）
                # 因此需要等待至少30秒
                await asyncio.sleep(35)  # 等待35秒确保不超限

            except Exception as e:
                error_msg = str(e)

                # 检查是否是限流错误
                if "每分钟最多访问该接口" in error_msg or "访问超过限制" in error_msg:
                    logger.warning(f"遇到API限流，等待60秒后重试... ({retry_count+1}/{max_retries})")
                    await asyncio.sleep(60)  # 等待1分钟

                    if retry_count < max_retries:
                        retry_count += 1
                        continue  # 重试当前批次
                    else:
                        logger.error(f"达到最大重试次数，跳过批次: {current_start} 到 {current_end}")
                        current_start = current_end
                        retry_count = 0
                else:
                    logger.error(f"下载批次数据失败 ({current_start} 到 {current_end}): {e}")
                    # 如果连续失败，跳过这个时间段
                    current_start = current_end
                    retry_count = 0
                    await asyncio.sleep(2)  # 延长等待时间

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

    def _convert_dataframe_to_points(self, df, timeframe: str, extract_symbol: bool = False):
        """将DataFrame转换为MarketDataPoint列表

        Args:
            df: Tushare返回的DataFrame
            timeframe: 时间周期
            extract_symbol: 是否提取合约代码（返回格式为 [(symbol, exchange, MarketDataPoint)]）

        Returns:
            如果 extract_symbol=True: List[Tuple[str, str, MarketDataPoint]]
            如果 extract_symbol=False: List[MarketDataPoint]
        """
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

                if extract_symbol and 'ts_code' in row:
                    # 从 ts_code 提取合约代码和交易所，并转换为VNPy格式
                    # 例如: "RB2601.SHF" -> ("rb2601", "SHFE")
                    #       "SR2501.ZCE" -> ("SR501", "CZCE")  # 注意郑商所的特殊处理
                    ts_code = str(row['ts_code'])
                    try:
                        # 使用标准化工具转换
                        vnpy_symbol, vnpy_exchange = SymbolStandardizer.tushare_to_vnpy(ts_code)
                        data_points.append((vnpy_symbol, vnpy_exchange, dp))
                    except Exception as e:
                        logger.warning(f"无法转换 ts_code {ts_code} 为VNPy格式: {e}")
                        continue
                else:
                    data_points.append(dp)

            except Exception as e:
                logger.debug(f"转换数据点失败: {e}")
                continue

        return data_points

    def _get_active_contracts(self, symbol: str, exchange: str, months_back: int = 12) -> List[str]:
        """获取指定品种的有效合约列表

        Args:
            symbol: 品种代码（如 rb, cu）
            exchange: 交易所代码（如 SHFE, DCE）
            months_back: 回溯月数，默认12个月

        Returns:
            有效合约代码列表（Tushare格式，如 ['rb2501.SHF', 'rb2505.SHF']）
        """
        try:
            # 转换交易所代码为Tushare格式
            # Tushare 的交易所代码与标准代码略有不同
            ts_exchange_map = {
                "SHFE": "SHFE",  # 上海期货交易所
                "DCE": "DCE",    # 大连商品交易所
                "CZCE": "CZCE",  # 郑州商品交易所
                "CFFEX": "CFFEX" # 中国金融期货交易所
            }
            ts_exchange = ts_exchange_map.get(exchange, exchange)

            # 获取该交易所的所有期货合约信息
            df = self.tushare_pro.fut_basic(exchange=ts_exchange, fut_type="1")

            if df is None or df.empty:
                logger.warning(f"未找到 {exchange} 交易所的合约信息")
                return []

            # 计算截止日期（当前日期往前推 months_back 个月）
            cutoff_date = datetime.now() - timedelta(days=months_back * 30)
            cutoff_date_str = cutoff_date.strftime("%Y%m%d")
            current_date_str = datetime.now().strftime("%Y%m%d")

            # 筛选指定品种的合约
            # 从 ts_code 中提取品种代码（如 RB2501.SHF -> RB）
            df['symbol_part'] = df['ts_code'].str.extract(r'([A-Za-z]+)')[0]

            # 过滤出指定品种
            symbol_df = df[df['symbol_part'].str.upper() == symbol.upper()].copy()

            if symbol_df.empty:
                logger.warning(f"未找到品种 {symbol} 的合约")
                return []

            # 筛选有效合约：
            # 1. 退市日期在当前日期之后（合约仍然有效）
            # 2. 上市日期在截止日期之后（最近的合约）
            valid_contracts = symbol_df[
                (symbol_df['delist_date'] >= current_date_str) &
                (symbol_df['list_date'] >= cutoff_date_str)
            ]

            # 如果没有找到最近的合约，放宽条件：只要退市日期在未来即可
            if valid_contracts.empty:
                valid_contracts = symbol_df[symbol_df['delist_date'] >= current_date_str]

            # 提取合约代码列表
            contracts = valid_contracts['ts_code'].tolist()

            # 按退市日期排序，优先下载临近到期的合约
            valid_contracts = valid_contracts.sort_values('delist_date')
            contracts = valid_contracts['ts_code'].tolist()

            logger.debug(f"找到 {symbol}.{exchange} 的 {len(contracts)} 个有效合约")

            return contracts

        except Exception as e:
            logger.error(f"获取 {symbol}.{exchange} 有效合约失败: {e}")
            return []

    async def save_to_database(
        self,
        timeframe: str,
        data_points_with_symbols
    ) -> int:
        """保存数据到数据库

        Args:
            timeframe: 时间周期
            data_points_with_symbols: List[Tuple[str, str, MarketDataPoint]]
                格式：[(合约代码, 交易所, 数据点), ...]

        Returns:
            保存的数据条数
        """
        if not self.db_manager or not data_points_with_symbols:
            return 0

        try:
            saved = 0
            async with self.db_manager.postgres_pool.acquire() as conn:
                for contract_symbol, exchange, dp in data_points_with_symbols:
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
                            dp.timestamp, contract_symbol, exchange, timeframe,
                            dp.open, dp.high, dp.low, dp.close,
                            dp.volume, dp.open_interest
                        )
                        saved += 1
                    except Exception as e:
                        logger.debug(f"保存数据点失败: {e}")
                        continue

            # 统计不同合约的数量用于日志输出
            unique_contracts = set((symbol, exch) for symbol, exch, _ in data_points_with_symbols)
            logger.info(f"💾 保存 {timeframe} 数据: {saved}/{len(data_points_with_symbols)} 条 (来自 {len(unique_contracts)} 个合约)")
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

                # 先获取合约信息（避免重复调用）
                contracts = self._get_active_contracts(symbol, exchange, months_back=12)
                if not contracts:
                    print(f"  ⚠️  未找到有效合约，跳过")
                    continue

                print(f"  📋 找到 {len(contracts)} 个有效合约")

                for tf in timeframes:
                    strategy = self.DATA_STRATEGIES.get(tf, {})
                    days = strategy.get("days", 30)
                    desc = strategy.get("desc", "")

                    print(f"  ⏬ 下载 {tf} 数据 ({desc})...", end=" ", flush=True)

                    # 下载数据（传入合约列表避免重复获取）
                    # 返回格式：[(合约代码, 交易所, MarketDataPoint), ...]
                    data_points_with_symbols = await self.download_futures_data(
                        symbol, exchange, tf, days, contracts=contracts
                    )

                    if data_points_with_symbols:
                        # 保存到数据库
                        saved = await self.save_to_database(
                            tf, data_points_with_symbols
                        )
                        results[exchange][f"{symbol}_{tf}"] = saved
                        total_downloaded += len(data_points_with_symbols)
                        total_saved += saved
                        print(f"✅ {saved} 条")
                    else:
                        print("⚠️ 无数据")

                    # 避免请求过快（Tushare限制：每分钟最多2次分钟线数据请求）
                    # 日线数据可以快一些，分钟线数据需要等待更长时间
                    if tf == "1d":
                        await asyncio.sleep(0.5)
                    else:
                        await asyncio.sleep(1.0)

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
    print("  1. 仅日线数据 (快速，推荐，无API限制)")
    print("  2. 日线 + 小时线 (需要高级Tushare权限，较慢)")
    print("  3. 全部数据 (需要2000+积分，非常慢)")
    print("  4. 自定义")

    choice = input("请输入选项 (1-4, 默认 1): ").strip() or "1"

    if choice == "1":
        timeframes = ["1d"]
        print("\n✅ 选择仅日线数据 - 快速且稳定")
    elif choice == "2":
        timeframes = ["1d", "1h"]
        print("\n⚠️  注意: 小时线数据有严格的API限流（每分钟2次）")
        print("   下载会非常慢，每个合约需要等待约35秒")
        confirm = input("   确认继续？(y/n): ").lower().strip()
        if confirm != 'y':
            print("   改为仅下载日线数据")
            timeframes = ["1d"]
    elif choice == "3":
        timeframes = ["1d", "1h", "30m", "10m", "5m", "1m"]
        print("\n⚠️  警告: 分钟线数据需要Tushare Pro 2000+积分")
        print("   且有严格的API限流，下载可能需要数小时")
        confirm = input("   确认继续？(y/n): ").lower().strip()
        if confirm != 'y':
            print("   改为仅下载日线数据")
            timeframes = ["1d"]
    elif choice == "4":
        print("\n可选时间周期: 1d, 1h, 30m, 10m, 5m, 1m")
        print("注意: 分钟线数据(1h及以下)有严格的API限流")
        tf_input = input("请输入时间周期（用空格分隔）: ").strip()
        timeframes = tf_input.split()
    else:
        timeframes = ["1d"]

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
