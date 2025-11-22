#!/usr/bin/env python3
"""
简单AI决策示例

难度：⭐⭐ 初级

学习要点：
1. OpenAI API 调用
2. 基本提示词设计
3. JSON 输出解析
4. 错误处理

运行方式：
    uv run python examples/03_ai/simple_ai_decision.py

前置要求：
    - 设置 OPENAI_API_KEY 环境变量
    - 设置 OPENAI_BASE_URL（可选，用于自定义端点）
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cherryquant.ai.llm_client.openai_client import LLMClient


async def example_1_basic_decision():
    """示例1：基础AI决策"""
    print("\n" + "=" * 60)
    print("示例 1: 基础AI交易决策")
    print("=" * 60 + "\n")

    # 1. 检查API配置
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-xxx"):
        print("❌ 错误: 请设置 OPENAI_API_KEY 环境变量")
        print("   获取方式: https://platform.openai.com")
        return

    # 2. 初始化LLM客户端
    print("🤖 初始化 AI 客户端...")
    client = LLMClient(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL"),
        model=os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview"),
    )
    print(f"✅ 使用模型: {client.model}\n")

    # 3. 构造市场数据
    market_context = """
品种: 螺纹钢 (rb2501)
板块: 黑色金属

当前行情:
- 最新价: ¥3,520
- 涨跌幅: +1.8%
- 成交量: 较昨日放大30%

技术指标:
- MA5: 3,480 (价格在MA5之上)
- MA20: 3,450 (价格突破MA20)
- RSI: 68 (略微超买，但未达极值)
- MACD: 金叉形成，柱状图转正

市场情绪:
- 钢厂开工率稳定
- 下游需求季节性回暖
- 库存水平处于中等偏低
"""

    # 4. 定义提示词
    system_prompt = """你是一个专业的期货交易分析师。

你的任务是基于提供的市场数据和技术指标，给出明确的交易建议。

输出格式（严格JSON）:
{
    "action": "BUY" | "SELL" | "HOLD",
    "confidence": 0.0-1.0,
    "reasoning": "详细的分析理由",
    "risk_level": "LOW" | "MEDIUM" | "HIGH"
}"""

    user_prompt = f"""请分析以下市场数据并给出交易建议：

{market_context}

请输出JSON格式的决策。"""

    # 5. 调用AI
    print("🧠 正在请求AI决策...\n")

    try:
        decision = await client.get_trading_decision_async(
            system_prompt=system_prompt, user_prompt=user_prompt
        )

        if decision:
            print("✅ AI决策结果:")
            print(f"   动作: {decision.get('action', 'N/A')}")
            print(f"   置信度: {decision.get('confidence', 0):.1%}")
            print(f"   风险等级: {decision.get('risk_level', 'N/A')}")
            print(f"   理由: {decision.get('reasoning', 'N/A')[:200]}...")
        else:
            print("⚠️  AI返回空决策")

    except Exception as e:
        print(f"❌ AI调用失败: {e}")

    print("\n✅ 示例1完成")


async def example_2_multi_scenarios():
    """示例2：多场景决策对比"""
    print("\n" + "=" * 60)
    print("示例 2: 多场景决策对比")
    print("=" * 60 + "\n")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-xxx"):
        print("❌ 请设置 OPENAI_API_KEY")
        return

    client = LLMClient(api_key=api_key)

    # 定义3个不同的市场场景
    scenarios = [
        {
            "name": "强势上涨",
            "context": "价格: ¥3,600 (+3.5%), RSI: 75, MACD强金叉, 成交量暴增",
        },
        {
            "name": "弱势震荡",
            "context": "价格: ¥3,480 (-0.5%), RSI: 48, MACD死叉, 成交量萎缩",
        },
        {
            "name": "暴跌反弹",
            "context": "价格: ¥3,350 (-5%), RSI: 28, MACD底背离, 恐慌性抛售后企稳",
        },
    ]

    system_prompt = """你是期货分析师。基于市场数据给出JSON格式的交易建议：
{"action": "BUY/SELL/HOLD", "confidence": 0-1, "reasoning": "理由"}"""

    print("🧠 测试3个不同场景的AI决策...\n")

    for scenario in scenarios:
        print(f"  场景: {scenario['name']}")
        print(f"  数据: {scenario['context']}")

        try:
            decision = await client.get_trading_decision_async(
                system_prompt=system_prompt,
                user_prompt=f"分析: {scenario['context']}",
            )

            if decision:
                print(
                    f"  → 决策: {decision.get('action')} "
                    f"(置信度: {decision.get('confidence', 0):.0%})"
                )
            print()

        except Exception as e:
            print(f"  → 错误: {e}\n")

        await asyncio.sleep(1)  # 避免API限流

    print("✅ 示例2完成")


async def example_3_temperature_comparison():
    """示例3：温度参数对比"""
    print("\n" + "=" * 60)
    print("示例 3: Temperature参数对决策一致性的影响")
    print("=" * 60 + "\n")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-xxx"):
        print("❌ 请设置 OPENAI_API_KEY")
        return

    print("💡 相同输入，测试不同temperature参数（3次采样）\n")

    market_data = "rb2501: 价格¥3,500 (+1%), RSI:65, MA5>MA20, 成交量正常"

    temperatures = [0.1, 0.7, 1.5]

    for temp in temperatures:
        print(f"  Temperature = {temp}:")

        client = LLMClient(api_key=api_key, temperature=temp)

        for i in range(3):
            try:
                decision = await client.get_trading_decision_async(
                    system_prompt="你是期货分析师，输出JSON: {\"action\": \"BUY/SELL/HOLD\"}",
                    user_prompt=f"分析: {market_data}",
                )

                action = decision.get("action", "N/A") if decision else "ERROR"
                print(f"    第{i+1}次: {action}")

            except Exception as e:
                print(f"    第{i+1}次: 错误 - {e}")

            await asyncio.sleep(0.5)

        print()

    print("💡 观察: Temperature越低，决策越一致；越高，决策越随机")
    print("✅ 示例3完成")


async def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("📚 CherryQuant AI决策示例 - 简单AI决策")
    print("=" * 70)

    try:
        await example_1_basic_decision()
        await example_2_multi_scenarios()
        await example_3_temperature_comparison()

        print("\n" + "=" * 70)
        print("✅ 所有示例运行完成！")
        print("=" * 70)
        print("\n💡 下一步:")
        print("  1. 运行 examples/03_ai/prompt_engineering.py 学习提示词优化")
        print("  2. 阅读 docs/adr/0003-prompt-engineering-ai.md")
        print("  3. 完成 Lab 03 实验任务")
        print()

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n\n❌ 错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
