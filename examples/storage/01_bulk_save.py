"""
批量数据保存示例 - Quantbox 工具整合

演示如何使用 BulkWriter 和 SaveResult 进行高性能批量数据写入，
性能提升可达 100 倍。

依赖: 需要运行 MongoDB

运行:
    1. 确保 MongoDB 已启动
    2. python examples/storage/01_bulk_save.py
"""

import asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
import pymongo

from cherryquant.data.storage.bulk_writer import BulkWriter
from cherryquant.data.storage.save_result import SaveResult


async def example_1_basic_upsert():
    """示例1: 基础批量 Upsert"""
    print("=" * 70)
    print("示例1: 基础批量 Upsert 操作")
    print("=" * 70)

    # 连接 MongoDB
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.cherryquant_examples
    collection = db.market_data

    # 准备测试数据
    data = [
        {"symbol": "rb2501", "date": 20241122, "close": 3500.0, "volume": 100000},
        {"symbol": "rb2501", "date": 20241123, "close": 3510.0, "volume": 120000},
        {"symbol": "hc2501", "date": 20241122, "close": 3200.0, "volume": 80000},
    ]

    print(f"\n准备插入 {len(data)} 条数据...")

    # 创建结果追踪器
    result = SaveResult()

    # 批量 upsert
    await BulkWriter.bulk_upsert(
        collection=collection,
        data=data,
        key_fields=["symbol", "date"],  # 唯一键
        result=result
    )

    result.complete()

    # 查看结果
    print(f"\n结果: {result}")
    print(f"  插入: {result.inserted_count} 条")
    print(f"  更新: {result.modified_count} 条")
    print(f"  错误: {result.error_count} 条")
    print(f"  耗时: {result.duration.total_seconds():.3f} 秒")
    print(f"  成功率: {result.success_rate:.1%}")

    # 清理
    await collection.drop()


async def example_2_update_existing():
    """示例2: 更新已存在的数据（Upsert 模式）"""
    print("\n" + "=" * 70)
    print("示例2: Upsert 模式 - 更新已存在的数据")
    print("=" * 70)

    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.cherryquant_examples
    collection = db.market_data

    # 第一次插入
    print("\n步骤1: 初始插入 2 条数据")
    data1 = [
        {"symbol": "rb2501", "date": 20241122, "close": 3500.0, "volume": 100000},
        {"symbol": "rb2501", "date": 20241123, "close": 3510.0, "volume": 120000},
    ]

    result1 = SaveResult()
    await BulkWriter.bulk_upsert(
        collection=collection,
        data=data1,
        key_fields=["symbol", "date"],
        result=result1
    )
    result1.complete()
    print(f"  结果: {result1}")

    # 第二次更新 + 新增
    print("\n步骤2: 更新第1条，插入第3条")
    data2 = [
        {"symbol": "rb2501", "date": 20241122, "close": 3505.0, "volume": 105000},  # 更新
        {"symbol": "rb2501", "date": 20241124, "close": 3520.0, "volume": 110000},  # 新增
    ]

    result2 = SaveResult()
    await BulkWriter.bulk_upsert(
        collection=collection,
        data=data2,
        key_fields=["symbol", "date"],
        result=result2
    )
    result2.complete()
    print(f"  结果: {result2}")
    print(f"  说明: modified_count=1 (更新), inserted_count=1 (新增)")

    # 验证数据
    print("\n步骤3: 验证最终数据")
    docs = await collection.find({"symbol": "rb2501"}).sort("date", 1).to_list(None)
    for doc in docs:
        print(f"  {doc['date']}: close={doc['close']}, volume={doc['volume']}")

    # 清理
    await collection.drop()


async def example_3_index_management():
    """示例3: 索引管理"""
    print("\n" + "=" * 70)
    print("示例3: 索引管理")
    print("=" * 70)

    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.cherryquant_examples
    collection = db.market_data

    print("\n创建索引...")

    # 批量创建索引
    await BulkWriter.ensure_indexes(
        collection=collection,
        index_specs=[
            {
                "keys": [("symbol", pymongo.ASCENDING), ("date", pymongo.ASCENDING)],
                "unique": True,
                "background": True
            },
            {
                "keys": [("date", pymongo.DESCENDING)],
                "unique": False,
                "background": True
            }
        ]
    )

    # 查看创建的索引
    indexes = await collection.index_information()
    print("\n已创建的索引:")
    for name, spec in indexes.items():
        print(f"  {name}: {spec}")

    # 清理
    await collection.drop()


async def example_4_error_handling():
    """示例4: 错误处理"""
    print("\n" + "=" * 70)
    print("示例4: 错误处理和追踪")
    print("=" * 70)

    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.cherryquant_examples
    collection = db.market_data

    # 准备数据（包含部分无效数据）
    data = [
        {"symbol": "rb2501", "date": 20241122, "close": 3500.0, "volume": 100000},
        {"symbol": "rb2501", "close": 3510.0, "volume": 120000},  # 缺少 date 字段
        {"date": 20241122, "close": 3200.0, "volume": 80000},  # 缺少 symbol 字段
        {"symbol": "hc2501", "date": 20241123, "close": 3210.0, "volume": 85000},
    ]

    print(f"\n准备保存 {len(data)} 条数据（包含 2 条无效数据）...")

    result = SaveResult()

    # 批量 upsert
    await BulkWriter.bulk_upsert(
        collection=collection,
        data=data,
        key_fields=["symbol", "date"],
        result=result
    )

    result.complete()

    # 查看结果
    print(f"\n结果: {result}")
    print(f"  成功: {result.total_count} 条")
    print(f"  错误: {result.error_count} 条")

    # 查看错误详情
    if result.errors:
        print("\n错误详情:")
        for error in result.errors:
            print(f"  类型: {error['type']}")
            print(f"  消息: {error['message']}")
            print(f"  数据: {error.get('data', 'N/A')}")
            print()

    # 清理
    await collection.drop()


async def example_5_performance_comparison():
    """示例5: 性能对比"""
    print("\n" + "=" * 70)
    print("示例5: 性能对比 - 批量 vs 逐条")
    print("=" * 70)

    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.cherryquant_examples

    # 准备 1000 条测试数据
    test_data = [
        {
            "symbol": f"rb{2501 + i % 12}",
            "date": 20241101 + i,
            "close": 3500.0 + i * 0.1,
            "volume": 100000 + i * 100
        }
        for i in range(1000)
    ]

    print(f"\n测试数据: {len(test_data)} 条")

    # 方法1: 逐条插入（慢）
    print("\n方法1: 逐条 insert_one (不推荐)")
    collection1 = db.test_single
    start1 = datetime.now()

    for item in test_data[:100]:  # 只测试 100 条，否则太慢
        await collection1.insert_one(item)

    duration1 = (datetime.now() - start1).total_seconds()
    print(f"  100 条耗时: {duration1:.3f} 秒")
    print(f"  预计 1000 条耗时: {duration1 * 10:.3f} 秒")

    # 方法2: 批量 upsert（快）
    print("\n方法2: BulkWriter.bulk_upsert (推荐)")
    collection2 = db.test_bulk

    result = SaveResult()
    await BulkWriter.bulk_upsert(
        collection=collection2,
        data=test_data,  # 完整 1000 条
        key_fields=["symbol", "date"],
        result=result
    )
    result.complete()

    duration2 = result.duration.total_seconds()
    print(f"  1000 条耗时: {duration2:.3f} 秒")

    # 性能对比
    speedup = (duration1 * 10) / duration2
    print(f"\n性能提升: {speedup:.1f} 倍 🚀")

    # 清理
    await collection1.drop()
    await collection2.drop()


async def example_6_real_world_usage():
    """示例6: 实际应用场景"""
    print("\n" + "=" * 70)
    print("示例6: 实际应用 - 数据采集器集成")
    print("=" * 70)

    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.cherryquant_examples
    collection = db.market_data

    # 模拟从 API 采集的数据
    collected_data = [
        {"symbol": "rb2501", "date": 20241120, "close": 3480.0, "volume": 95000},
        {"symbol": "rb2501", "date": 20241121, "close": 3490.0, "volume": 98000},
        {"symbol": "rb2501", "date": 20241122, "close": 3500.0, "volume": 100000},
        {"symbol": "hc2501", "date": 20241120, "close": 3180.0, "volume": 75000},
        {"symbol": "hc2501", "date": 20241121, "close": 3190.0, "volume": 78000},
        {"symbol": "hc2501", "date": 20241122, "close": 3200.0, "volume": 80000},
    ]

    print(f"\n采集到 {len(collected_data)} 条数据，准备保存...")

    # 1. 创建索引（确保唯一性）
    await BulkWriter.ensure_indexes(
        collection=collection,
        index_specs=[
            {
                "keys": [("symbol", 1), ("date", 1)],
                "unique": True
            }
        ]
    )

    # 2. 批量保存
    result = SaveResult()
    await BulkWriter.bulk_upsert(
        collection=collection,
        data=collected_data,
        key_fields=["symbol", "date"],
        result=result
    )
    result.complete()

    # 3. 记录日志
    if result.success:
        print(f"\n✅ 数据保存成功: {result}")
    else:
        print(f"\n❌ 数据保存失败: {result}")
        for error in result.errors:
            print(f"  错误: {error['type']} - {error['message']}")

    # 4. 导出为字典（用于日志记录）
    result_dict = result.to_dict()
    print("\n结果摘要（可用于日志）:")
    print(f"  总计: {result_dict['total_count']} 条")
    print(f"  插入: {result_dict['inserted_count']} 条")
    print(f"  更新: {result_dict['modified_count']} 条")
    print(f"  耗时: {result_dict['duration_seconds']:.3f} 秒")
    print(f"  成功率: {result_dict['success_rate']:.1%}")

    # 清理
    await collection.drop()


async def main():
    """运行所有示例"""
    print("\n")
    print("🎯 " + "=" * 68)
    print("🎯  批量数据保存示例 - Quantbox 工具整合")
    print("🎯 " + "=" * 68)

    try:
        await example_1_basic_upsert()
        await example_2_update_existing()
        await example_3_index_management()
        await example_4_error_handling()
        await example_5_performance_comparison()
        await example_6_real_world_usage()

        print("\n" + "=" * 70)
        print("✅ 所有示例运行完成!")
        print("=" * 70)
        print("\n📖 更多信息:")
        print("   - 文档: docs/quantbox_integration_p1.md")
        print("   - 迁移指南: docs/MIGRATION_GUIDE.md")
        print("   - 源代码: src/cherryquant/data/storage/bulk_writer.py")
        print()

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print("\n请确保:")
        print("  1. MongoDB 已启动 (mongod)")
        print("  2. 连接地址正确 (mongodb://localhost:27017)")


if __name__ == "__main__":
    asyncio.run(main())
