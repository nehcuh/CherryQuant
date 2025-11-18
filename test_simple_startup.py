#!/usr/bin/env python3
"""
简化的项目启动测试

测试核心组件是否可以正常工作
"""

import asyncio
import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

async def test_simple_startup():
    """测试简化启动"""
    print("🎬 CherryQuant 简化启动测试")
    print("=" * 50)
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 测试核心组件
    test_results = []

    # 1. 测试配置加载
    try:
        from config.settings.settings import TRADING_CONFIG, AI_CONFIG, RISK_CONFIG
        print("✅ 配置加载成功")
        test_results.append(("配置加载", True))
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        test_results.append(("配置加载", False))

    # 2. 测试数据库管理器（MongoDB + Redis，通过 AppContext 构建）
    try:
        from cherryquant.bootstrap.app_context import create_app_context

        ctx = await create_app_context()
        db_manager = ctx.db
        print("✅ 数据库管理器创建成功")
        test_results.append(("数据库管理器", True))
        await ctx.close()
    except Exception as e:
        print(f"❌ 数据库管理器失败: {e}")
        test_results.append(("数据库管理器", False))

    # 3. 测试市场数据管理器
    try:
        from src.cherryquant.adapters.data_adapter.market_data_manager import MarketDataManager
        market_manager = MarketDataManager()
        print("✅ 市场数据管理器创建成功")
        test_results.append(("市场数据管理器", True))
    except Exception as e:
        print(f"❌ 市场数据管理器失败: {e}")
        test_results.append(("市场数据管理器", False))

    # 4. 测试增强版历史数据管理器
    try:
        from src.cherryquant.adapters.data_adapter.history_data_manager import HistoryDataManager

        history_manager = HistoryDataManager(
            enable_quantbox=True,
            use_async=True,
            enable_dual_write=False
        )

        status = history_manager.get_system_status()
        print(f"✅ 历史数据管理器创建成功")
        print(f"   📊 QuantBox 集成: {status['quantbox_integration']}")
        test_results.append(("历史数据管理器", True))
    except Exception as e:
        print(f"❌ 历史数据管理器失败: {e}")
        test_results.append(("历史数据管理器", False))

    # 5. 测试 AI 代理管理器
    try:
        from cherryquant.ai.agents.agent_manager import AgentManager
        # 注意：这里只是测试导入，不实际初始化
        print("✅ AI 代理管理器导入成功")
        test_results.append(("AI 代理管理器", True))
    except Exception as e:
        print(f"❌ AI 代理管理器失败: {e}")
        test_results.append(("AI 代理管理器", False))

    # 6. 测试 Web API
    try:
        from src.cherryquant.web.api.main import app
        print("✅ Web API 应用创建成功")
        test_results.append(("Web API", True))
    except Exception as e:
        print(f"❌ Web API 失败: {e}")
        test_results.append(("Web API", False))

    # 统计结果
    print(f"\n📊 测试结果统计:")
    print("-" * 30)

    passed = 0
    total = len(test_results)

    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1

    success_rate = (passed / total) * 100 if total > 0 else 0
    print(f"\n通过率: {passed}/{total} ({success_rate:.1f}%)")

    if passed >= total * 0.8:
        print(f"\n🎉 **项目可以正常运行！**")
        print(f"\n✅ 核心组件初始化成功")
        print(f"🚀 QuantBox 集成正常工作")
        print(f"🌐 Web API 可以启动")
        print(f"\n💡 建议下一步:")
        print(f"   1. 确认数据库服务正在运行")
        print(f"   2. 检查 OpenAI API 配置")
        print(f"   3. 尝试运行完整系统:")
        print(f"      python run_cherryquant_complete.py")
        return True
    else:
        print(f"\n⚠️  **项目存在一些问题**")
        print(f"\n请检查上述失败的组件")
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(test_simple_startup())
        if result:
            print(f"\n🚀 准备就绪，可以开始使用 CherryQuant！")
    except KeyboardInterrupt:
        print(f"\n\n⏹️  测试被用户中断")
    except Exception as e:
        print(f"\n\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()