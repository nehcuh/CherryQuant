#!/usr/bin/env python3
"""
端到端完整系统示例

难度：⭐⭐⭐⭐ 高级

功能：演示完整的CherryQuant系统工作流程
- 数据采集 → AI决策 → 风险检查 → (模拟)交易执行

学习要点：
1. 完整数据管道集成
2. AI决策引擎使用
3. 风险管理系统
4. 系统各模块协同

运行方式：
    uv run python examples/complete_system/end_to_end_demo.py

前置要求：
    - OPENAI_API_KEY (用于AI决策)
    - TUSHARE_TOKEN (用于数据获取，可选)
    - MongoDB (可选，用于数据持久化)
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cherryquant.ai.llm_client.openai_client import LLMClient
from cherryquant.ai.decision_engine.futures_engine import FuturesDecisionEngine


# 模拟风险管理器
class SimpleRiskManager:
    """简化的风险管理器"""

    def __init__(self, initial_capital: float = 1_000_000):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions = {}
        self.max_position_ratio = 0.3  # 单品种最大仓位30%
        self.max_daily_loss_ratio = 0.05  # 单日最大亏损5%

    def check_risk(self, symbol: str, action: str, quantity: int, price: float) -> tuple[bool, str]:
        """风险检查"""

        if action == "HOLD":
            return True, "观望无风险"

        # 1. 仓位检查
        position_value = quantity * price * 10  # 假设合约乘数10
        max_position_value = self.current_capital * self.max_position_ratio

        if position_value > max_position_value:
            return False, f"超过最大仓位限制 (¥{max_position_value:,.0f})"

        # 2. 资金检查
        required_margin = position_value * 0.15  # 假设15%保证金
        if required_margin > self.current_capital * 0.8:
            return False, "可用资金不足"

        # 3. 亏损检查
        daily_loss = self.initial_capital - self.current_capital
        if daily_loss > self.initial_capital * self.max_daily_loss_ratio:
            return False, "达到单日最大亏损限制"

        return True, "风险检查通过"

    def execute_trade(self, symbol: str, action: str, quantity: int, price: float):
        """执行交易（模拟）"""
        if action == "BUY":
            self.positions[symbol] = self.positions.get(symbol, 0) + quantity
            cost = quantity * price * 10
            self.current_capital -= cost
            return f"✅ 买入 {symbol} {quantity}手 @ ¥{price:.2f}"

        elif action == "SELL":
            self.positions[symbol] = self.positions.get(symbol, 0) - quantity
            proceeds = quantity * price * 10
            self.current_capital += proceeds
            return f"✅ 卖出 {symbol} {quantity}手 @ ¥{price:.2f}"

        return f"➡️  观望 {symbol}"


async def run_trading_cycle(symbol: str, risk_manager: SimpleRiskManager):
    """运行一个完整的交易周期"""

    print(f"\n{'='*60}")
    print(f"🎯 交易品种: {symbol}")
    print(f"{'='*60}\n")

    # ==================== Step 1: 数据采集 ====================
    print("📊 [1/4] 数据采集...")

    # 模拟获取市场数据
    import random

    base_price = 3500.0
    price = base_price + random.uniform(-50, 50)
    change_pct = ((price - base_price) / base_price) * 100

    market_data = {
        "symbol": symbol,
        "price": price,
        "change_pct": change_pct,
        "volume": random.randint(50000, 150000),
        "ma5": price - 20,
        "ma20": price - 45,
        "rsi": random.uniform(40, 70),
    }

    print(f"  ✅ 获取行情: ¥{price:.2f} ({change_pct:+.2f}%)")
    print(f"     RSI: {market_data['rsi']:.1f}, MA5: {market_data['ma5']:.2f}\n")

    # ==================== Step 2: AI决策 ====================
    print("🤖 [2/4] AI决策...")

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key or api_key.startswith("sk-xxx"):
        print("  ⚠️  未配置OPENAI_API_KEY，使用模拟决策")

        # 模拟AI决策
        if market_data["rsi"] > 65:
            decision = {"action": "SELL", "confidence": 0.6, "reasoning": "RSI超买"}
        elif market_data["rsi"] < 35:
            decision = {"action": "BUY", "confidence": 0.7, "reasoning": "RSI超卖"}
        else:
            decision = {"action": "HOLD", "confidence": 0.5, "reasoning": "等待明确信号"}

        print(f"  ✅ 模拟决策: {decision['action']} (置信度: {decision['confidence']:.0%})")
        print(f"     理由: {decision['reasoning']}\n")

    else:
        # 真实AI决策
        try:
            client = LLMClient(api_key=api_key)
            ai_engine = FuturesDecisionEngine(
                ai_client=client, db_manager=None, market_data_manager=None
            )

            account_info = {
                "balance": risk_manager.current_capital,
                "available": risk_manager.current_capital * 0.8,
            }

            decision = await ai_engine.get_decision(
                symbol=symbol, account_info=account_info, current_positions=[]
            )

            if decision:
                print(f"  ✅ AI决策: {decision.get('action', 'HOLD')}")
                print(f"     置信度: {decision.get('confidence', 0):.0%}")
                print(f"     理由: {decision.get('reasoning', 'N/A')[:100]}...\n")
            else:
                print("  ⚠️  AI决策失败，使用HOLD\n")
                decision = {"action": "HOLD", "confidence": 0, "reasoning": "AI返回空"}

        except Exception as e:
            print(f"  ❌ AI调用错误: {e}")
            print("  ➡️  降级为HOLD\n")
            decision = {"action": "HOLD", "confidence": 0, "reasoning": "AI错误"}

    # ==================== Step 3: 风险检查 ====================
    print("🛡️  [3/4] 风险检查...")

    action = decision.get("action", "HOLD")
    quantity = 2  # 简化：固定2手

    risk_passed, risk_msg = risk_manager.check_risk(symbol, action, quantity, price)

    print(f"  风险检查: {'✅ 通过' if risk_passed else '❌ 拒绝'}")
    print(f"  原因: {risk_msg}\n")

    # ==================== Step 4: 交易执行 ====================
    print("💼 [4/4] 交易执行...")

    if risk_passed and action != "HOLD":
        result = risk_manager.execute_trade(symbol, action, quantity, price)
        print(f"  {result}")
    else:
        print(f"  ➡️  不执行交易 (动作: {action}, 风险: {risk_passed})")

    # 显示账户状态
    print(f"\n📈 账户状态:")
    print(f"  资金: ¥{risk_manager.current_capital:,.2f}")
    print(f"  盈亏: ¥{risk_manager.current_capital - risk_manager.initial_capital:+,.2f}")
    print(f"  持仓: {risk_manager.positions}")


async def main():
    """主函数"""

    print("\n" + "=" * 70)
    print("🍒 CherryQuant 端到端完整系统演示")
    print("=" * 70)

    print("\n💡 本示例演示完整的交易流程:")
    print("   数据采集 → AI决策 → 风险检查 → 交易执行\n")

    # 初始化风险管理器
    risk_manager = SimpleRiskManager(initial_capital=1_000_000)

    print(f"💰 初始资金: ¥{risk_manager.initial_capital:,.0f}")

    # 运行多个交易周期
    symbols = ["rb2501", "hc2501", "i2501"]

    try:
        for i, symbol in enumerate(symbols):
            await run_trading_cycle(symbol, risk_manager)

            if i < len(symbols) - 1:
                print("\n⏸️  等待3秒后继续...\n")
                await asyncio.sleep(3)

        # 最终总结
        print("\n" + "=" * 70)
        print("📊 交易总结")
        print("=" * 70)

        print(f"\n初始资金: ¥{risk_manager.initial_capital:,.2f}")
        print(f"当前资金: ¥{risk_manager.current_capital:,.2f}")
        print(f"盈亏: ¥{risk_manager.current_capital - risk_manager.initial_capital:+,.2f}")
        print(f"收益率: {(risk_manager.current_capital / risk_manager.initial_capital - 1) * 100:+.2f}%")
        print(f"\n持仓汇总: {risk_manager.positions}")

        print("\n" + "=" * 70)
        print("✅ 端到端演示完成！")
        print("=" * 70)

        print("\n💡 生产环境注意事项:")
        print("  1. 需要真实的数据库和数据源")
        print("  2. 需要配置完整的风险管理参数")
        print("  3. 需要连接真实的CTP接口（建议先用SimNow）")
        print("  4. 建议先进行充分的回测验证")
        print("  5. 小资金、低仓位开始实盘测试")
        print()

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n\n❌ 错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
