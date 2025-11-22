#!/usr/bin/env python3
"""
提示词工程示例

难度：⭐⭐⭐ 中级

学习要点：
1. System Prompt vs User Prompt
2. Few-shot Learning 示例
3. 提示词模板化
4. 板块特定策略

运行方式：
    uv run python examples/03_ai/prompt_engineering.py

前置要求：
    - 设置 OPENAI_API_KEY 环境变量
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cherryquant.ai.llm_client.openai_client import LLMClient


# ==================== 不同风格的提示词 ====================

PROMPT_STYLE_1_SIMPLE = """
你是交易助手。分析市场数据，给出交易建议。
"""

PROMPT_STYLE_2_STRUCTURED = """
你是专业的期货交易分析师。

你的职责：
1. 分析市场数据和技术指标
2. 评估交易机会的风险收益比
3. 给出明确的交易建议（BUY/SELL/HOLD）

分析框架：
- 趋势判断：主要趋势方向和强度
- 动量分析：价格动量和成交量配合
- 风险评估：当前风险水平
- 决策建议：交易方向、信心度、理由

输出格式：严格的JSON格式
{"action": "BUY/SELL/HOLD", "confidence": 0-1, "reasoning": "理由"}
"""

PROMPT_STYLE_3_WITH_EXAMPLES = """
你是专业的期货交易分析师。

任务：基于市场数据给出JSON格式的交易建议。

示例1（强势突破）:
输入: rb2501, 价格¥3600(+3%), RSI:70, MA5>MA20, 成交量放大
输出: {"action": "BUY", "confidence": 0.75, "reasoning": "突破关键均线，动量强劲，但RSI略高需警惕"}

示例2（弱势震荡）:
输入: hc2501, 价格¥3450(-0.5%), RSI:48, MACD死叉, 成交量萎缩
输出: {"action": "HOLD", "confidence": 0.5, "reasoning": "市场信号不明确，建议观望"}

示例3（超卖反弹）:
输入: i2501, 价格¥780(-5%), RSI:25, MACD底背离, 恐慌性抛售
输出: {"action": "BUY", "confidence": 0.65, "reasoning": "超卖严重，技术性反弹概率高"}

现在请分析以下数据并输出JSON格式决策：
"""


# ==================== 板块特定策略 ====================

PROMPT_BLACK_METALS = """
你是黑色金属（螺纹钢、热卷、铁矿石）专家。

黑色金属特点：
- 受房地产和基建政策影响大
- 季节性特征明显（春季需求旺盛）
- 供需关系直接影响价格
- 库存数据是关键指标

重点关注：
1. 钢厂开工率和产量
2. 社会库存变化
3. 下游需求（房地产、基建）
4. 铁矿石价格（成本支撑）

基于以上专业知识分析市场数据：
"""

PROMPT_COLORED_METALS = """
你是有色金属（铜、铝、锌）专家。

有色金属特点：
- 与全球经济周期高度相关
- 美元指数负相关
- 库存周期明显
- 受国际市场影响大

重点关注：
1. LME库存变化
2. 美元指数走势
3. 全球制造业PMI
4. 主要消费国需求

基于以上专业知识分析市场数据：
"""


async def example_1_compare_prompts():
    """示例1：对比不同风格的提示词"""
    print("\n" + "=" * 60)
    print("示例 1: 对比简单vs结构化vs带示例的提示词")
    print("=" * 60 + "\n")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-xxx"):
        print("❌ 请设置 OPENAI_API_KEY")
        return

    client = LLMClient(api_key=api_key, temperature=0.3)

    market_data = "rb2501: 价格¥3,520(+1.8%), RSI:68, MA5>MA20, 成交量正常"

    prompts = [
        ("简单提示词", PROMPT_STYLE_1_SIMPLE),
        ("结构化提示词", PROMPT_STYLE_2_STRUCTURED),
        ("带示例提示词", PROMPT_STYLE_3_WITH_EXAMPLES),
    ]

    print(f"💡 测试数据: {market_data}\n")

    for name, system_prompt in prompts:
        print(f"  [{name}]")

        try:
            decision = await client.get_trading_decision_async(
                system_prompt=system_prompt, user_prompt=f"分析: {market_data}"
            )

            if decision:
                action = decision.get("action", "N/A")
                confidence = decision.get("confidence", 0)
                reasoning = decision.get("reasoning", "N/A")[:80]
                print(f"    决策: {action} (置信度: {confidence:.0%})")
                print(f"    理由: {reasoning}...")
            else:
                print(f"    ❌ AI返回空")

        except Exception as e:
            print(f"    ❌ 错误: {e}")

        print()
        await asyncio.sleep(1)

    print("💡 观察: 结构化和带示例的提示词通常给出更一致、更合理的决策")
    print("✅ 示例1完成")


async def example_2_few_shot_learning():
    """示例2：Few-shot Learning效果"""
    print("\n" + "=" * 60)
    print("示例 2: Zero-shot vs Few-shot Learning")
    print("=" * 60 + "\n")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-xxx"):
        print("❌ 请设置 OPENAI_API_KEY")
        return

    client = LLMClient(api_key=api_key, temperature=0.2)

    # 边缘案例：RSI在中性区间，信号不明确
    edge_case = "ag2506: 价格¥5,200(-0.3%), RSI:52, MA5≈MA20, 成交量平稳"

    print(f"💡 测试边缘案例: {edge_case}\n")

    # Zero-shot
    print("  [Zero-shot - 无示例]")
    zero_shot_prompt = """你是交易分析师。给出JSON格式决策：
{"action": "BUY/SELL/HOLD", "confidence": 0-1, "reasoning": "理由"}"""

    try:
        decision = await client.get_trading_decision_async(
            system_prompt=zero_shot_prompt, user_prompt=f"分析: {edge_case}"
        )
        if decision:
            print(f"    决策: {decision.get('action')} (置信度: {decision.get('confidence', 0):.0%})")
    except Exception as e:
        print(f"    ❌ 错误: {e}")

    await asyncio.sleep(1)

    # Few-shot
    print("\n  [Few-shot - 带示例]")

    try:
        decision = await client.get_trading_decision_async(
            system_prompt=PROMPT_STYLE_3_WITH_EXAMPLES, user_prompt=edge_case
        )
        if decision:
            print(f"    决策: {decision.get('action')} (置信度: {decision.get('confidence', 0):.0%})")
            print(f"    理由: {decision.get('reasoning', 'N/A')[:100]}")
    except Exception as e:
        print(f"    ❌ 错误: {e}")

    print("\n💡 观察: Few-shot通常在边缘案例中表现更稳定")
    print("✅ 示例2完成")


async def example_3_sector_specific():
    """示例3：板块特定策略"""
    print("\n" + "=" * 60)
    print("示例 3: 通用策略 vs 板块特定策略")
    print("=" * 60 + "\n")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-xxx"):
        print("❌ 请设置 OPENAI_API_KEY")
        return

    client = LLMClient(api_key=api_key, temperature=0.2)

    # 黑色金属案例
    black_case = """
rb2501 (螺纹钢):
- 价格: ¥3,550 (+2%)
- 钢厂开工率: 78% (上升)
- 社会库存: 520万吨 (下降10%)
- 房地产政策: 近期利好
- RSI: 65
"""

    print("📊 测试黑色金属数据:\n")

    # 通用策略
    print("  [通用策略]")
    generic_prompt = "你是交易分析师。分析数据，输出JSON决策。"

    try:
        decision = await client.get_trading_decision_async(system_prompt=generic_prompt, user_prompt=black_case)
        if decision:
            print(f"    决策: {decision.get('action')} (置信度: {decision.get('confidence', 0):.0%})")
    except Exception as e:
        print(f"    ❌ 错误: {e}")

    await asyncio.sleep(1)

    # 板块特定策略
    print("\n  [黑色金属专家策略]")

    try:
        decision = await client.get_trading_decision_async(system_prompt=PROMPT_BLACK_METALS, user_prompt=black_case)
        if decision:
            print(f"    决策: {decision.get('action')} (置信度: {decision.get('confidence', 0):.0%})")
            print(f"    理由: {decision.get('reasoning', 'N/A')[:150]}")
    except Exception as e:
        print(f"    ❌ 错误: {e}")

    print("\n💡 观察: 板块专家策略能更好地理解行业特定指标")
    print("✅ 示例3完成")


async def example_4_temperature_impact():
    """示例4：Temperature对创造性的影响"""
    print("\n" + "=" * 60)
    print("示例 4: Temperature参数对决策风格的影响")
    print("=" * 60 + "\n")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-xxx"):
        print("❌ 请设置 OPENAI_API_KEY")
        return

    market_data = "cu2502: 价格¥68,500(+1%), RSI:58, 供需平衡"

    temperatures = [0.1, 0.7, 1.2]

    print(f"💡 测试数据: {market_data}\n")

    for temp in temperatures:
        print(f"  [Temperature = {temp}]")
        client = LLMClient(api_key=api_key, temperature=temp)

        try:
            decision = await client.get_trading_decision_async(
                system_prompt=PROMPT_STYLE_2_STRUCTURED, user_prompt=f"分析: {market_data}"
            )

            if decision:
                print(f"    决策: {decision.get('action')} (置信度: {decision.get('confidence', 0):.0%})")
        except Exception as e:
            print(f"    ❌ 错误: {e}")

        await asyncio.sleep(0.5)

    print("\n💡 建议:")
    print("  - Temperature 0.1-0.3: 一致性高，适合生产环境")
    print("  - Temperature 0.5-0.8: 平衡创造性，适合探索")
    print("  - Temperature 0.9+: 高随机性，不推荐用于交易")
    print("\n✅ 示例4完成")


async def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("📚 CherryQuant AI决策示例 - 提示词工程")
    print("=" * 70)

    try:
        await example_1_compare_prompts()
        await example_2_few_shot_learning()
        await example_3_sector_specific()
        await example_4_temperature_impact()

        print("\n" + "=" * 70)
        print("✅ 所有示例运行完成！")
        print("=" * 70)

        print("\n💡 提示词工程最佳实践:")
        print("  1. 使用结构化提示词（角色+任务+格式）")
        print("  2. 提供Few-shot示例提高稳定性")
        print("  3. 使用板块专业知识提升决策质量")
        print("  4. 设置合适的Temperature（推荐0.1-0.3）")
        print("  5. 要求严格的JSON输出格式")
        print()

        print("📚 延伸阅读:")
        print("  - docs/adr/0003-prompt-engineering-ai.md")
        print("  - docs/course/03_AI_Decision_Engine.md")
        print()

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n\n❌ 错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
