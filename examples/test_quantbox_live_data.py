#!/usr/bin/env python3
"""
测试 QuantBox 实际数据获取功能

验证 MongoDB 连接、Tushare API 和完整的数据获取流程
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
import time
import pandas as pd

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.cherryquant.adapters.data_adapter.history_data_manager import HistoryDataManager
from src.cherryquant.adapters.quantbox_adapter.cherryquant_adapter import CherryQuantQuantBoxAdapter


async def test_quantbox_connection():
    """测试 QuantBox 连接和基本功能"""
    print("🔧 测试 QuantBox 连接和基本功能")
    print("=" * 50)

    try:
        # 测试适配器连接
        print("\n1. 测试适配器初始化...")
        adapter = CherryQuantQuantBoxAdapter(
            use_async=True,
            auto_warm=True
        )

        print("   ✅ 适配器初始化成功")

        # 测试连接
        print("\n2. 测试数据库连接...")
        is_connected = await adapter.test_connection()
        print(f"   📊 连接状态: {'✅ 已连接' if is_connected else '❌ 未连接'}")

        # 测试交易日历获取
        print("\n3. 测试交易日历获取...")
        try:
            calendar_df = await adapter.get_trade_calendar_async(
                exchanges=["SHSE"],
                start_date="2024-01-01",
                end_date="2024-01-10"
            )
            print(f"   📅 获取交易日历: {len(calendar_df)} 条记录")
            if not calendar_df.empty:
                print(f"      时间范围: {calendar_df['date'].min()} - {calendar_df['date'].max()}")
        except Exception as e:
            print(f"   ❌ 交易日历获取失败: {e}")

        # 测试期货合约获取
        print("\n4. 测试期货合约获取...")
        try:
            contracts_df = await adapter.get_future_contracts_async(
                exchanges="SHFE",
                date="2024-01-15"
            )
            print(f"   📋 获取期货合约: {len(contracts_df)} 条记录")
            if not contracts_df.empty:
                print(f"      示例合约: {contracts_df.head(3)['symbol'].tolist()}")
        except Exception as e:
            print(f"   ❌ 期货合约获取失败: {e}")

        # 测试期货日线数据
        print("\n5. 测试期货日线数据获取...")
        try:
            daily_df = await adapter.get_future_daily_async(
                symbols="SHFE.rb2501",
                start_date="2024-01-01",
                end_date="2024-01-05"
            )
            print(f"   📈 获取日线数据: {len(daily_df)} 条记录")
            if not daily_df.empty:
                print(f"      数据列: {list(daily_df.columns)}")
                print(f"      示例数据:")
                print(daily_df.head(2))
        except Exception as e:
            print(f"   ❌ 日线数据获取失败: {e}")

        adapter.close()
        return True

    except Exception as e:
        print(f"❌ QuantBox 测试失败: {e}")
        return False


async def test_enhanced_history_manager():
    """测试增强版 HistoryDataManager"""
    print("\n\n🚀 测试增强版 HistoryDataManager")
    print("=" * 50)

    try:
        # 初始化管理器
        print("\n1. 初始化增强版管理器...")
        start_time = time.time()

        manager = HistoryDataManager(
            enable_quantbox=True,
            use_async=True,
            enable_dual_write=True,  # 启用双写来测试
            cache_size=50,
            cache_ttl=1800  # 30分钟
        )

        init_time = time.time() - start_time
        print(f"   ✅ 初始化完成，耗时: {init_time:.3f}s")

        # 系统状态检查
        print("\n2. 系统状态检查...")
        status = manager.get_system_status()
        print(f"   📊 QuantBox 集成: {status['quantbox_integration']}")
        print(f"   💾 缓存系统: {status['cache_system']}")
        print(f"   📈 历史数据管理器: {status['history_data_manager']}")

        # 测试 QuantBox 连接
        print("\n3. 测试 QuantBox 连接...")
        qb_connected = await manager.test_quantbox_connection()
        print(f"   🔗 QuantBox 连接: {'✅ 成功' if qb_connected else '❌ 失败'}")

        # 测试实际数据获取
        print("\n4. 测试实际数据获取...")
        test_cases = [
            {"symbol": "rb2501", "exchange": "SHFE", "interval": "1d"},
            {"symbol": "cu2501", "exchange": "SHFE", "interval": "1d"},
        ]

        for i, case in enumerate(test_cases, 1):
            print(f"\n   4.{i} 获取 {case['symbol']}.{case['exchange']} 数据...")
            start_time = time.time()

            try:
                df = await manager.get_historical_data(
                    symbol=case["symbol"],
                    exchange=case["exchange"],
                    interval=case["interval"],
                    start_date="2024-01-01",
                    end_date="2024-01-05",
                    prefer_quantbox=True
                )

                fetch_time = time.time() - start_time
                print(f"      ⏱️  耗时: {fetch_time:.3f}s")

                if not df.empty:
                    print(f"      ✅ 获取成功: {len(df)} 条记录")
                    print(f"      📊 时间范围: {df['datetime'].min()} - {df['datetime'].max()}")
                    print(f"      💰 价格范围: {df['close'].min():.2f} - {df['close'].max():.2f}")
                    print(f"      📈 成交量: {df['volume'].sum():,}")
                else:
                    print(f"      ⚠️  无数据返回")

            except Exception as e:
                print(f"      ❌ 获取失败: {e}")

        # 测试批量获取
        print("\n5. 测试批量数据获取...")
        batch_requests = [
            {
                "symbol": "rb2501",
                "exchange": "SHFE",
                "interval": "1d",
                "start_date": "2024-01-01",
                "end_date": "2024-01-03"
            },
            {
                "symbol": "cu2501",
                "exchange": "SHFE",
                "interval": "1d",
                "start_date": "2024-01-01",
                "end_date": "2024-01-03"
            }
        ]

        try:
            print("   🔄 批量获取中...")
            start_time = time.time()

            results = await manager.batch_get_historical_data(batch_requests)
            batch_time = time.time() - start_time

            print(f"   ✅ 批量获取完成，耗时: {batch_time:.3f}s")
            for key, df in results.items():
                if not df.empty:
                    print(f"      📊 {key}: {len(df)} 条记录")
                else:
                    print(f"      📊 {key}: 无数据")

        except Exception as e:
            print(f"   ❌ 批量获取失败: {e}")

        # 测试合约信息
        print("\n6. 测试合约信息获取...")
        test_contracts = [
            ("rb2501", "SHFE"),
            ("cu2501", "SHFE"),
            ("ag2501", "SHFE")
        ]

        for symbol, exchange in test_contracts:
            try:
                contract_info = await manager.get_contract_info(symbol, exchange)
                if contract_info:
                    print(f"      📋 {symbol}.{exchange}: ✅ {contract_info.get('name', 'N/A')}")
                    print(f"         乘数: {contract_info.get('multiplier', 'N/A')}")
                else:
                    print(f"      📋 {symbol}.{exchange}: ⚠️  未找到信息")
            except Exception as e:
                print(f"      📋 {symbol}.{exchange}: ❌ 获取失败")

        # 测试交易日历
        print("\n7. 测试交易日历功能...")
        test_dates = [
            datetime(2024, 1, 15),  # 工作日
            datetime(2024, 1, 20),  # 周六
            datetime(2024, 2, 10),  # 春节
        ]

        for test_date in test_dates:
            try:
                is_trading = await manager.is_trading_day(test_date, "SHFE")
                status_text = "✅ 交易日" if is_trading else "❌ 非交易日"
                print(f"      📅 {test_date.strftime('%Y-%m-%d %A')}: {status_text}")
            except Exception as e:
                print(f"      📅 {test_date.strftime('%Y-%m-%d')}: ❌ 检查失败")

        # 缓存效果测试
        print("\n8. 测试缓存效果...")
        try:
            # 第一次请求
            start_time = time.time()
            await manager.get_historical_data(
                "rb2501", "SHFE", "1d",
                start_date="2024-01-01",
                end_date="2024-01-02"
            )
            first_time = time.time() - start_time

            # 第二次请求（应该从缓存获取）
            start_time = time.time()
            await manager.get_historical_data(
                "rb2501", "SHFE", "1d",
                start_date="2024-01-01",
                end_date="2024-01-02"
            )
            second_time = time.time() - start_time

            speedup = first_time / second_time if second_time > 0 else float('inf')
            print(f"      首次请求: {first_time:.3f}s")
            print(f"      缓存请求: {second_time:.3f}s")
            print(f"      🚀 性能提升: {speedup:.1f}x")

        except Exception as e:
            print(f"      ⚠️  缓存测试失败: {e}")

        # 显示最终状态
        print("\n9. 最终系统状态...")
        cache_info = manager.get_cache_info()
        print(f"   📊 本地缓存大小: {cache_info['cache_size']}")
        print(f"   ⚡ QuantBox 已启用: {cache_info['quantbox_enabled']}")

        if cache_info['quantbox_enabled']:
            qb_cache = cache_info.get('quantbox_cache', {})
            print(f"   🎯 QuantBox 缓存条目: {qb_cache.get('valid_cache_entries', 0)}")

        # 清理
        manager.clear_all_caches()
        if hasattr(manager, 'close'):
            manager.close()

        print("\n   ✅ 测试完成！")
        return True

    except Exception as e:
        print(f"❌ HistoryDataManager 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_data_quality():
    """测试数据质量和完整性"""
    print("\n\n🔍 测试数据质量和完整性")
    print("=" * 50)

    try:
        manager = HistoryDataManager(enable_quantbox=True, use_async=True)

        # 获取测试数据
        df = await manager.get_historical_data(
            "rb2501", "SHFE", "1d",
            start_date="2024-01-01",
            end_date="2024-01-10"
        )

        if df.empty:
            print("   ⚠️  无法获取数据，跳过质量测试")
            return False

        print(f"   📊 获取到 {len(df)} 条记录")
        print(f"   📅 时间范围: {df['datetime'].min()} - {df['datetime'].max()}")

        # 检查数据完整性
        print("\n   数据完整性检查:")
        required_columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            print(f"      ❌ 缺少列: {missing_columns}")
        else:
            print("      ✅ 所有必要列都存在")

        # 检查数据类型
        print("\n   数据类型检查:")
        print(f"      datetime: {df['datetime'].dtype}")
        print(f"      price columns: {df['open'].dtype}, {df['high'].dtype}, {df['low'].dtype}, {df['close'].dtype}")
        print(f"      volume: {df['volume'].dtype}")

        # 检查数据逻辑性
        print("\n   数据逻辑性检查:")
        invalid_data = 0

        # OHLC 逻辑检查
        invalid_ohlc = df[
            (df['high'] < df['low']) |
            (df['high'] < df['open']) |
            (df['high'] < df['close']) |
            (df['low'] > df['open']) |
            (df['low'] > df['close'])
        ]

        if not invalid_ohlc.empty:
            print(f"      ❌ 发现 {len(invalid_ohlc)} 条 OHLC 逻辑错误")
            invalid_data += len(invalid_ohlc)
        else:
            print("      ✅ OHLC 数据逻辑正确")

        # 价格和成交量检查
        negative_prices = df[
            (df['open'] <= 0) | (df['high'] <= 0) |
            (df['low'] <= 0) | (df['close'] <= 0)
        ]

        negative_volume = df[df['volume'] < 0]

        if not negative_prices.empty:
            print(f"      ❌ 发现 {len(negative_prices)} 条负价格数据")
            invalid_data += len(negative_prices)
        else:
            print("      ✅ 价格数据为正数")

        if not negative_volume.empty:
            print(f"      ❌ 发现 {len(negative_volume)} 条负成交量数据")
            invalid_data += len(negative_volume)
        else:
            print("      ✅ 成交量数据非负")

        # 数据统计
        print("\n   数据统计:")
        print(f"      最高价: {df['high'].max():.2f}")
        print(f"      最低价: {df['low'].min():.2f}")
        print(f"      平均收盘价: {df['close'].mean():.2f}")
        print(f"      总成交量: {df['volume'].sum():,}")
        print(f"      平均日成交量: {df['volume'].mean():.0f}")

        manager.close()

        if invalid_data == 0:
            print("\n   ✅ 数据质量检查通过")
            return True
        else:
            print(f"\n   ❌ 发现 {invalid_data} 条数据质量问题")
            return False

    except Exception as e:
        print(f"❌ 数据质量测试失败: {e}")
        return False


async def main():
    """主测试函数"""
    print("🎬 CherryQuant + QuantBox 完整功能测试")
    print("=" * 60)
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔧 Python 版本: {sys.version}")

    # 测试结果统计
    test_results = []

    # 1. 测试 QuantBox 基础功能
    print("\n" + "=" * 60)
    result1 = await test_quantbox_connection()
    test_results.append(("QuantBox 基础功能", result1))

    # 2. 测试增强版 HistoryDataManager
    print("\n" + "=" * 60)
    result2 = await test_enhanced_history_manager()
    test_results.append(("HistoryDataManager 增强", result2))

    # 3. 测试数据质量
    print("\n" + "=" * 60)
    result3 = await test_data_quality()
    test_results.append(("数据质量检查", result3))

    # 测试结果总结
    print("\n\n📊 测试结果总结")
    print("=" * 60)

    passed = 0
    total = len(test_results)

    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！CherryQuant + QuantBox 集成工作正常。")
        print("\n🚀 您现在可以享受高性能的数据处理功能了！")
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败，请检查配置和连接。")
        print("\n📝 可能的问题:")
        print("   1. Tushare Token 配置错误")
        print("   2. MongoDB 连接问题")
        print("   3. 网络连接问题")
        print("   4. 数据源限制")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  测试被用户中断")
    except Exception as e:
        print(f"\n\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()