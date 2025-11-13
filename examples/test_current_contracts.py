#!/usr/bin/env python3
"""
测试当前可用合约的数据获取

使用近期可用的合约代码进行测试
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.cherryquant.adapters.data_adapter.history_data_manager import HistoryDataManager


async def test_current_contracts():
    """测试当前可用合约"""
    print("🔍 测试当前可用合约数据获取")
    print("=" * 50)

    manager = HistoryDataManager(enable_quantbox=True, use_async=True)

    # 使用当前或近期可用的合约
    test_contracts = [
        # 上期所主力合约（2024年）
        {"symbol": "cu2406", "exchange": "SHFE", "name": "沪铜2406"},
        {"symbol": "rb2410", "exchange": "SHFE", "name": "螺纹钢2410"},
        {"symbol": "au2406", "exchange": "SHFE", "name": "沪金2406"},
        {"symbol": "ag2406", "exchange": "SHFE", "name": "沪银2406"},

        # 大商所主力合约
        {"symbol": "m2409", "exchange": "DCE", "name": "豆粕2409"},
        {"symbol": "a2409", "exchange": "DCE", "name": "豆一2409"},
        {"symbol": "y2409", "exchange": "DCE", "name": "豆油2409"},

        # 郑商所主力合约
        {"symbol": "CF409", "exchange": "CZCE", "name": "郑棉409"},
        {"symbol": "SR409", "exchange": "CZCE", "name": "郑糖409"},

        # 中金所主力合约
        {"symbol": "IF2406", "exchange": "CFFEX", "name": "沪深300股指2406"},
    ]

    successful_contracts = []
    failed_contracts = []

    for i, contract in enumerate(test_contracts, 1):
        print(f"\n{i}. 测试 {contract['name']} ({contract['symbol']}.{contract['exchange']})")

        try:
            start_time = time.time()

            # 使用QuantBox优先
            df = await manager.get_historical_data(
                symbol=contract['symbol'],
                exchange=contract['exchange'],
                interval='1d',
                start_date='2024-05-01',
                end_date='2024-05-10',
                prefer_quantbox=True
            )

            fetch_time = time.time() - start_time

            if not df.empty:
                print(f"   ✅ 成功获取 {len(df)} 条记录，耗时: {fetch_time:.3f}s")
                print(f"      时间范围: {df['datetime'].min().strftime('%Y-%m-%d')} - {df['datetime'].max().strftime('%Y-%m-%d')}")
                print(f"      价格范围: {df['close'].min():.2f} - {df['close'].max():.2f}")
                print(f"      成交量: {df['volume'].sum():,}")

                successful_contracts.append({
                    'symbol': contract['symbol'],
                    'exchange': contract['exchange'],
                    'name': contract['name'],
                    'count': len(df),
                    'time': fetch_time
                })
            else:
                print(f"   ❌ 无数据返回，耗时: {fetch_time:.3f}s")
                failed_contracts.append(contract)

        except Exception as e:
            print(f"   ❌ 获取失败: {e}")
            failed_contracts.append(contract)

    # 测试结果总结
    print(f"\n\n📊 测试结果总结")
    print("=" * 50)
    print(f"✅ 成功获取: {len(successful_contracts)} 个合约")
    print(f"❌ 失败: {len(failed_contracts)} 个合约")

    if successful_contracts:
        print(f"\n✅ 成功的合约:")
        for contract in successful_contracts:
            print(f"   {contract['name']} ({contract['symbol']}): {contract['count']} 条数据")

    if failed_contracts:
        print(f"\n❌ 失败的合约:")
        for contract in failed_contracts:
            print(f"   {contract['name']} ({contract['symbol']})")

    # 性能分析
    if successful_contracts:
        avg_time = sum(c['time'] for c in successful_contracts) / len(successful_contracts)
        total_data = sum(c['count'] for c in successful_contracts)

        print(f"\n📈 性能分析:")
        print(f"   平均获取时间: {avg_time:.3f}s")
        print(f"   总数据条数: {total_data:,}")
        print(f"   缓存状态: {manager.get_cache_info()['quantbox_enabled']}")

    manager.close()

    return len(successful_contracts) > 0


async def test_trading_calendar():
    """测试交易日历功能"""
    print(f"\n\n📅 测试交易日历功能")
    print("=" * 50)

    from src.cherryquant.adapters.quantbox_adapter.cherryquant_adapter import CherryQuantQuantBoxAdapter

    adapter = CherryQuantQuantBoxAdapter(use_async=True, auto_warm=True)

    # 测试不同交易所的交易日历
    exchanges = ["SHSE", "SZSE", "SHFE", "DCE", "CZCE", "CFFEX"]

    for exchange in exchanges:
        try:
            df = await adapter.get_trade_calendar_async(
                exchanges=[exchange],
                start_date="2024-06-01",
                end_date="2024-06-10"
            )

            print(f"   📅 {exchange}: {len(df)} 条交易日")
            if not df.empty and len(df) > 0:
                print(f"      示例: {df['date'].head(3).tolist()}")

        except Exception as e:
            print(f"   ❌ {exchange}: 获取失败 - {e}")

    adapter.close()


async def main():
    """主函数"""
    print("🎬 CherryQuant + QuantBox 当前合约测试")
    print("=" * 60)
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 测试当前合约
    success = await test_current_contracts()

    # 测试交易日历
    await test_trading_calendar()

    print(f"\n\n🎉 测试完成！")
    if success:
        print("✅ 成功获取到真实数据，QuantBox 集成工作正常！")
        print("🚀 您现在可以开始使用高性能的数据管理功能了。")
    else:
        print("⚠️  所有测试合约都无数据，可能需要检查合约代码或数据源配置。")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  测试被用户中断")
    except Exception as e:
        print(f"\n\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()