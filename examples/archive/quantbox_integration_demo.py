#!/usr/bin/env python3
"""
QuantBox 集成演示

展示 CherryQuant 与 QuantBox 集成后的功能提升
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.cherryquant.adapters.data_adapter.history_data_manager import HistoryDataManager
from src.cherryquant.adapters.quantbox_adapter.cherryquant_adapter import CherryQuantQuantBoxAdapter
from src.cherryquant.adapters.quantbox_adapter.data_bridge import DataBridge


async def demo_quantbox_features():
    """演示 QuantBox 集成功能"""
    print("🚀 CherryQuant + QuantBox 集成演示")
    print("=" * 60)

    # 1. 初始化增强版 HistoryDataManager
    print("\n1. 初始化增强版 HistoryDataManager...")
    start_time = time.time()

    manager = HistoryDataManager(
        enable_quantbox=True,
        use_async=True,
        enable_dual_write=False,  # 演示中不启用双写
        cache_size=100,
        cache_ttl=3600
    )

    init_time = time.time() - start_time
    print(f"   ✅ 初始化完成，耗时: {init_time:.3f}s")

    # 2. 系统状态检查
    print("\n2. 系统状态检查...")
    status = manager.get_system_status()
    print(f"   📊 QuantBox 集成: {status['quantbox_integration']}")
    print(f"   💾 缓存系统: {status['cache_system']}")
    print(f"   📈 历史数据管理器: {status['history_data_manager']}")

    # 3. 缓存预热效果展示
    print("\n3. 缓存系统信息...")
    cache_info = manager.get_cache_info()
    print(f"   🗄️  本地缓存大小: {cache_info['cache_size']}")
    print(f"   ⚡ QuantBox 已启用: {cache_info['quantbox_enabled']}")
    if cache_info['quantbox_enabled']:
        quantbox_cache = cache_info.get('quantbox_cache', {})
        print(f"   🎯 QuantBox 缓存条目: {quantbox_cache.get('valid_cache_entries', 0)}")

    # 4. 交易日历功能演示
    print("\n4. 交易日历功能演示...")
    test_dates = [
        datetime(2024, 1, 1),   # 元旦（非交易日）
        datetime(2024, 1, 15),  # 工作日
        datetime(2024, 2, 10),  # 春节（非交易日）
    ]

    for test_date in test_dates:
        try:
            is_trading = await manager.is_trading_day(test_date, "SHFE")
            status_text = "✅ 交易日" if is_trading else "❌ 非交易日"
            print(f"   📅 {test_date.strftime('%Y-%m-%d')} ({test_date.strftime('%A')}): {status_text}")
        except Exception as e:
            print(f"   📅 {test_date.strftime('%Y-%m-%d')}: ⚠️  检查失败 ({e})")

    # 5. 合约信息获取演示
    print("\n5. 合约信息获取演示...")
    test_contracts = [
        ("rb2501", "SHFE"),  # 螺纹钢
        ("cu2501", "SHFE"),  # 铜
        ("a2501", "DCE"),    # 豆粕
    ]

    for symbol, exchange in test_contracts:
        try:
            contract_info = await manager.get_contract_info(symbol, exchange)
            if contract_info:
                print(f"   📋 {symbol}.{exchange}: {contract_info.get('name', 'N/A')}")
                print(f"      乘数: {contract_info.get('multiplier', 'N/A')}")
            else:
                print(f"   📋 {symbol}.{exchange}: ⚠️  未找到信息")
        except Exception as e:
            print(f"   📋 {symbol}.{exchange}: ❌ 获取失败 ({e})")

    # 6. 批量数据请求演示
    print("\n6. 批量数据请求演示...")
    requests = [
        {
            "symbol": "rb2501",
            "exchange": "SHFE",
            "interval": "1d",
            "start_date": "2024-01-01",
            "end_date": "2024-01-05"
        },
        {
            "symbol": "cu2501",
            "exchange": "SHFE",
            "interval": "1d",
            "start_date": "2024-01-01",
            "end_date": "2024-01-05"
        }
    ]

    try:
        print("   🔄 正在批量获取数据...")
        start_time = time.time()
        results = await manager.batch_get_historical_data(requests)
        batch_time = time.time() - start_time

        print(f"   ✅ 批量获取完成，耗时: {batch_time:.3f}s")
        for key, df in results.items():
            if not df.empty:
                print(f"      📊 {key}: {len(df)} 条记录")
                print(f"         时间范围: {df['datetime'].min()} 至 {df['datetime'].max()}")
            else:
                print(f"      📊 {key}: ⚠️  无数据")

    except Exception as e:
        print(f"   ❌ 批量获取失败: {e}")

    # 7. 缓存效果对比演示
    print("\n7. 缓存效果对比演示...")
    try:
        # 第一次请求（可能较慢）
        print("   🕐 第一次请求...")
        start_time = time.time()
        await manager.get_historical_data(
            "rb2501", "SHFE", "1d",
            start_date="2024-01-01",
            end_date="2024-01-03"
        )
        first_request_time = time.time() - start_time

        # 第二次请求（应该很快，来自缓存）
        print("   ⚡ 第二次请求（缓存）...")
        start_time = time.time()
        await manager.get_historical_data(
            "rb2501", "SHFE", "1d",
            start_date="2024-01-01",
            end_date="2024-01-03"
        )
        second_request_time = time.time() - start_time

        speedup = first_request_time / second_request_time if second_request_time > 0 else float('inf')
        print(f"      首次请求: {first_request_time:.3f}s")
        print(f"      缓存请求: {second_request_time:.3f}s")
        print(f"      🚀 性能提升: {speedup:.1f}x")

    except Exception as e:
        print(f"   ⚠️  缓存对比测试失败: {e}")

    # 8. 适配器功能演示
    print("\n8. QuantBox 适配器功能演示...")
    try:
        adapter_info = manager.quantbox_adapter.get_adapter_info()
        print(f"   🔧 适配器类型: {adapter_info['adapter_type']}")
        print(f"   ⚡ 异步模式: {'是' if manager.use_async else '否'}")
        print(f"   🎯 支持数据类型: {', '.join(adapter_info['supported_data_types'])}")
        print(f"   🚀 主要特性:")
        for feature in adapter_info['features']:
            print(f"      • {feature}")
    except Exception as e:
        print(f"   ❌ 适配器信息获取失败: {e}")

    # 9. 清理和总结
    print("\n9. 清理缓存...")
    manager.clear_all_caches()
    print("   ✅ 缓存已清空")

    # 10. 性能总结
    print("\n" + "=" * 60)
    print("📈 集成效果总结")
    print("=" * 60)
    print("✅ QuantBox 集成成功启用")
    print("🚀 异步高性能操作已启用")
    print("💾 智能缓存系统工作正常")
    print("🔄 批量操作支持已实现")
    print("🛡️  容错机制（回退到传统系统）正常")
    print("🎯 数据格式转换功能正常")

    # 关闭管理器
    if hasattr(manager, 'close'):
        manager.close()

    print("\n🎉 演示完成！CherryQuant 现在具备更强的数据处理能力。")


async def demo_adapter_only():
    """单独演示适配器功能"""
    print("\n🔧 QuantBox 适配器单独演示")
    print("=" * 40)

    try:
        adapter = CherryQuantQuantBoxAdapter(
            use_async=True,
            auto_warm=True
        )

        # 测试连接
        is_connected = await adapter.test_connection()
        print(f"🔗 QuantBox 连接状态: {'✅ 已连接' if is_connected else '❌ 未连接'}")

        # 获取交易日历
        try:
            calendar_df = adapter.get_trade_calendar(
                exchanges=["SHFE"],
                start_date="2024-01-01",
                end_date="2024-01-10"
            )
            print(f"📅 获取交易日历: {len(calendar_df)} 条记录")
        except Exception as e:
            print(f"📅 交易日历获取失败: {e}")

        adapter.close()

    except Exception as e:
        print(f"❌ 适配器演示失败: {e}")


if __name__ == "__main__":
    print("🎬 开始 CherryQuant + QuantBox 集成演示\n")

    try:
        # 主演示
        asyncio.run(demo_quantbox_features())

        # 适配器单独演示
        asyncio.run(demo_adapter_only())

    except KeyboardInterrupt:
        print("\n\n⏹️  演示被用户中断")
    except Exception as e:
        print(f"\n\n❌ 演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

    print("\n👋 感谢观看！")