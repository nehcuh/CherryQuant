"""
CherryQuant AI品种选择演示版
展示AI如何分析全市场并自主选择最优交易品种
"""

import asyncio
import logging
import os
import sys
import random
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目路径到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from config.settings.settings import TRADING_CONFIG, LOGGING_CONFIG
from adapters.data_storage.database_manager import get_database_manager
from config.database_config import DATABASE_CONFIG

# 添加路径
sys.path.insert(0, str(project_root / "adapters"))
sys.path.insert(0, str(project_root / "ai"))

from data_adapter.multi_symbol_manager import multi_symbol_manager
from ai.decision_engine.ai_selection_engine import AISelectionEngine

def setup_logging():
    """配置日志"""
    log_dir = Path("./logs")
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / f"cherryquant_ai_selection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    return logging.getLogger(__name__)

async def test_ai_connection():
    """测试AI连接"""
    logger = logging.getLogger(__name__)

    # 检查API Key
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    logger.info(f"🔍 AI配置检查:")
    logger.info(f"   Base URL: {base_url}")
    logger.info(f"   API Key: {'已配置' if api_key else '未配置'}")

    if not api_key or "your_openai_api_key_here" in api_key:
        logger.info("⚠️  未检测到有效的API Key，将使用演示模式")
        return False

    # 测试真实连接
    try:
        tushare_token = os.getenv("TUSHARE_TOKEN")
        engine = AISelectionEngine(tushare_token=tushare_token)
        if await engine.test_connection():
            logger.info("✅ AI连接测试成功")
            return True
        else:
            logger.info("❌ AI连接测试失败，将使用演示模式")
            return False

    except Exception as e:
        logger.info(f"⚠️  AI连接测试异常: {e}，将使用演示模式")
        return False

def create_demo_ai_selection_decision() -> dict:
    """创建模拟AI选择决策"""
    # 模拟AI分析结果
    top_opportunities = [
        {
            "rank": 1,
            "symbol": "rb",
            "exchange": "SHFE",
            "score": 85,
            "technical_score": 25,
            "quality_score": 28,
            "risk_reward_score": 22,
            "timing_score": 10,
            "current_price": 3520.0,
            "volume_24h": 150000,
            "open_interest": 200000,
            "volatility": 2.5,
            "trend_direction": "bullish",
            "key_levels": {
                "support": 3480.0,
                "resistance": 3560.0,
                "breakout_level": 3530.0
            }
        },
        {
            "rank": 2,
            "symbol": "cu",
            "exchange": "SHFE",
            "score": 78,
            "technical_score": 22,
            "quality_score": 26,
            "risk_reward_score": 20,
            "timing_score": 10,
            "current_price": 68000.0,
            "volume_24h": 80000,
            "open_interest": 120000,
            "volatility": 1.8,
            "trend_direction": "bearish",
            "key_levels": {
                "support": 67500.0,
                "resistance": 68500.0,
                "breakout_level": 68200.0
            }
        },
        {
            "rank": 3,
            "symbol": "i",
            "exchange": "DCE",
            "score": 72,
            "technical_score": 20,
            "quality_score": 24,
            "risk_reward_score": 18,
            "timing_score": 10,
            "current_price": 780.0,
            "volume_24h": 120000,
            "open_interest": 180000,
            "volatility": 3.2,
            "trend_direction": "bullish",
            "key_levels": {
                "support": 765.0,
                "resistance": 795.0,
                "breakout_level": 775.0
            }
        }
    ]

    # 选择最优机会
    best_opportunity = top_opportunities[0]

    # 构造交易决策
    action = random.choice(["buy_to_enter", "sell_to_enter"])
    if best_opportunity["trend_direction"] == "bullish":
        action = "buy_to_enter"
    elif best_opportunity["trend_direction"] == "bearish":
        action = "sell_to_enter"

    decision = {
        "market_analysis": {
            "total_contracts_analyzed": 45,
            "high_opportunities": 3,
            "moderate_opportunities": 12,
            "market_regime": "trending"
        },
        "top_opportunities": top_opportunities,
        "selected_trade": {
            "action": action,
            "symbol": best_opportunity["symbol"],
            "exchange": best_opportunity["exchange"],
            "contract_details": {
                "full_symbol": f"{best_opportunity['symbol']}.{best_opportunity['exchange']}",
                "contract_size": 10 if best_opportunity["symbol"] in ["rb", "cu"] else 100,
                "tick_value": 10 if best_opportunity["symbol"] in ["rb", "cu"] else 1,
                "margin_rate": 0.1
            },
            "quantity": random.randint(1, 5),
            "leverage": random.randint(3, 8),
            "entry_price": best_opportunity["current_price"],
            "profit_target": best_opportunity["key_levels"]["resistance"] if action == "buy_to_enter" else best_opportunity["key_levels"]["support"],
            "stop_loss": best_opportunity["key_levels"]["support"] if action == "buy_to_enter" else best_opportunity["key_levels"]["resistance"],
            "confidence": round(best_opportunity["score"] / 100, 2),
            "risk_reward_ratio": 2.5,
            "position_size_risk": 0.02,
            "selection_rationale": f"AI分析显示{best_opportunity['symbol']}具有最高的综合评分({best_opportunity['score']}/100)，技术指标{'上涨' if best_opportunity['trend_direction'] == 'bullish' else '下跌'}趋势明确，流动性充足，风险回报比达到2.5:1",
            "technical_analysis": f"价格突破关键水平{best_opportunity['key_levels']['breakout_level']:.0f}，成交量放大，{'多头' if best_opportunity['trend_direction'] == 'bullish' else '空头'}动能增强",
            "risk_factors": f"市场波动性为{best_opportunity['volatility']:.1f}%，需关注整体市场情绪变化",
            "invalidation_condition": f"价格{'跌破' if action == 'buy_to_enter' else '突破'} {best_opportunity['key_levels']['support'] if action == 'buy_to_enter' else best_opportunity['key_levels']['resistance']:.0f}"
        },
        "portfolio_context": {
            "current_positions": 0,
            "total_exposure": 0.0,
            "correlation_risk": "low",
            "diversification_score": 1.0
        }
    }

    return decision

async def ai_selection_demo():
    """AI品种选择演示"""
    logger = logging.getLogger(__name__)

    logger.info("🎮 CherryQuant AI品种选择演示开始")
    logger.info("=" * 80)

    # 初始化AI选择引擎
    tushare_token = os.getenv("TUSHARE_TOKEN")
    engine = AISelectionEngine(tushare_token=tushare_token)

    # 模拟账户信息
    account_info = {
        "account_value": 100000.0,
        "cash_available": 100000.0,
        "total_exposure": 0.0,
        "daily_pnl": 0.0,
        "daily_pnl_pct": 0.0
    }

    current_positions = []

    cycle_count = 0
    max_cycles = 5

    while cycle_count < max_cycles:
        try:
            logger.info(f"🧠 AI分析周期 {cycle_count + 1}/{max_cycles}")
            logger.info(f"   当前时间: {datetime.now().strftime('%H:%M:%S')}")
            logger.info(f"   账户状态: 余额¥{account_info['account_value']:,.2f}, 可用¥{account_info['cash_available']:,.2f}")
            logger.info(f"   当前持仓: {len(current_positions)} 个合约")

            # 检查API连接
            api_available = await test_ai_connection()

            if api_available:
                # 使用真实AI
                logger.info("🤖 正在调用真实AI分析全市场...")
                decision = await engine.get_optimal_trade_decision(
                    account_info=account_info,
                    current_positions=current_positions,
                    market_scope=TRADING_CONFIG.get("market_scope", {})
                )
            else:
                # 使用模拟AI
                logger.info("🎭 使用模拟AI决策...")
                await asyncio.sleep(2)  # 模拟思考时间
                decision = create_demo_ai_selection_decision()

            if decision:
                # 展示AI分析结果
                # 持久化AI选择的交易到数据库
                try:
                    db_manager = await get_database_manager(DATABASE_CONFIG)
                    selected_trade = decision.get("selected_trade", {})
                    if selected_trade:
                        ai_db_record = {
                            "decision_time": datetime.now(),
                            "symbol": selected_trade.get("symbol", ""),
                            "exchange": selected_trade.get("exchange", ""),
                            "action": selected_trade.get("action", "hold"),
                            "quantity": int(selected_trade.get("quantity", 0) or 0),
                            "leverage": int(selected_trade.get("leverage", 1) or 1),
                            "entry_price": float(selected_trade.get("entry_price", 0) or 0),
                            "profit_target": float(selected_trade.get("profit_target", 0) or 0),
                            "stop_loss": float(selected_trade.get("stop_loss", 0) or 0),
                            "confidence": float(selected_trade.get("confidence", 0) or 0),
                            "opportunity_score": int(decision.get("market_analysis", {}).get("high_opportunities", 0) or 0),
                            "selection_rationale": selected_trade.get("selection_rationale", ""),
                            "technical_analysis": selected_trade.get("technical_analysis", ""),
                            "risk_factors": selected_trade.get("risk_factors", ""),
                            "market_regime": decision.get("market_analysis", {}).get("market_regime", ""),
                            "volatility_index": str(decision.get("market_analysis", {}).get("volatility", "")),
                            "status": "pending",
                        }
                        await db_manager.store_ai_decision(ai_db_record)
                except Exception as e:
                    logger.debug(f"保存AI选择决策失败: {e}")
                market_analysis = decision.get("market_analysis", {})
                top_opportunities = decision.get("top_opportunities", [])
                selected_trade = decision.get("selected_trade", {})

                logger.info("📊 AI市场分析结果:")
                logger.info(f"   分析合约总数: {market_analysis.get('total_contracts_analyzed', 'N/A')}")
                logger.info(f"   高机会数量: {market_analysis.get('high_opportunities', 'N/A')}")
                logger.info(f"   市场状态: {market_analysis.get('market_regime', 'unknown')}")

                logger.info("🏆 TOP 3 交易机会:")
                for i, opp in enumerate(top_opportunities[:3], 1):
                    logger.info(f"   {i}. {opp['name'] if 'name' in opp else opp['symbol'].upper()} ({opp['exchange']})")
                    logger.info(f"      综合评分: {opp['score']}/100")
                    logger.info(f"      当前价格: ¥{opp['current_price']:,.2f}")
                    logger.info(f"      成交量: {opp['volume_24h']:,}")
                    logger.info(f"      趋势方向: {opp['trend_direction']}")

                # 展示AI选择的交易
                action = selected_trade.get("action", "unknown")
                symbol = selected_trade.get("symbol", "unknown")
                exchange = selected_trade.get("exchange", "unknown")
                confidence = selected_trade.get("confidence", 0)
                quantity = selected_trade.get("quantity", 0)
                leverage = selected_trade.get("leverage", 1)
                entry_price = selected_trade.get("entry_price", 0)
                profit_target = selected_trade.get("profit_target", 0)
                stop_loss = selected_trade.get("stop_loss", 0)

                logger.info("🎯 AI最终选择:")
                logger.info(f"   交易品种: {symbol.upper()}.{exchange}")
                logger.info(f"   交易方向: {action}")
                logger.info(f"   交易数量: {quantity} 手")
                logger.info(f"   杠杆倍数: {leverage}x")
                logger.info(f"   置信度: {confidence:.2f}")
                logger.info(f"   入场价格: ¥{entry_price:.2f}")
                logger.info(f"   止盈目标: ¥{profit_target:.2f}")
                logger.info(f"   止损价格: ¥{stop_loss:.2f}")

                # 展示AI的决策理由
                rationale = selected_trade.get("selection_rationale", "")
                technical = selected_trade.get("technical_analysis", "")
                risk_factors = selected_trade.get("risk_factors", "")

                logger.info("💡 AI决策理由:")
                logger.info(f"   选择逻辑: {rationale}")
                logger.info(f"   技术分析: {technical}")
                logger.info(f"   风险提示: {risk_factors}")

                # 模拟执行交易
                if confidence > 0.4 and action in ["buy_to_enter", "sell_to_enter"]:
                    # 添加到持仓
                    current_positions.append({
                        "symbol": f"{symbol}.{exchange}",
                        "action": action,
                        "quantity": quantity,
                        "entry_price": entry_price,
                        "profit_target": profit_target,
                        "stop_loss": stop_loss,
                        "confidence": confidence,
                        "leverage": leverage,
                        "entry_time": datetime.now().isoformat()
                    })

                    # 更新账户
                    position_value = entry_price * quantity * 10  # 简化计算
                    margin_required = position_value * 0.1
                    account_info["cash_available"] -= margin_required
                    account_info["total_exposure"] += position_value

                    logger.info(f"✅ 已执行{action}订单，添加到持仓")
                    logger.info(f"   占用保证金: ¥{margin_required:.2f}")
                    logger.info(f"   风险敞口: ¥{account_info['total_exposure']:,.2f} ({account_info['total_exposure']/account_info['account_value']*100:.1f}%)")

                elif action == "close" and current_positions:
                    # 平仓逻辑
                    for i, pos in enumerate(current_positions):
                        if pos["confidence"] > 0.7:  # 平仓高置信度持仓
                            pnl = (entry_price - pos["entry_price"]) * pos["quantity"] * 10
                            if pos["action"] == "buy_to_enter":
                                pnl = -pnl

                            account_info["total_value"] += pnl
                            account_info["cash_available"] += pos["quantity"] * entry_price * 10 * 0.1
                            account_info["total_exposure"] -= pos["entry_price"] * pos["quantity"] * 10

                            logger.info(f"✅ 已平仓: {pos['symbol']} ({pos['quantity']}手 @ ¥{pos['entry_price']:.2f})")
                            logger.info(f"   实现盈亏: ¥{pnl:+.2f}")

                            current_positions.pop(i)
                            break

                else:
                    logger.info(f"⏳ AI建议{action}，但置信度不足({confidence:.2f})，暂不执行")

            else:
                logger.error("❌ AI决策获取失败")

            logger.info("-" * 80)

            # 等待下一个周期
            await asyncio.sleep(3)
            cycle_count += 1

        except Exception as e:
            logger.error(f"AI选择循环错误: {e}")
            cycle_count += 1

    # 最终统计
    logger.info("🎉 AI品种选择演示完成！")
    logger.info("=" * 80)
    logger.info("📊 最终统计:")
    logger.info(f"   总分析周期: {cycle_count}")
    logger.info(f"   最终持仓: {len(current_positions)} 个")
    logger.info(f"   最终余额: ¥{account_info.get('total_value', 100000):,.2f}")
    final_value = account_info.get('total_value', 100000)
    logger.info(f"   总收益率: {(final_value - 100000) / 100000 * 100:+.2f}%")
    logger.info(f"   风险敞口: {account_info['total_exposure']/final_value*100:.1f}%")

    if current_positions:
        logger.info("📋 当前持仓明细:")
        for i, pos in enumerate(current_positions, 1):
            unrealized_pnl = (entry_price - pos["entry_price"]) * pos["quantity"] * 10
            if pos["action"] == "buy_to_enter":
                unrealized_pnl = -unrealized_pnl

            logger.info(f"   {i}. {pos['symbol']} ({pos['action']})")
            logger.info(f"      数量: {pos['quantity']}手 @ ¥{pos['entry_price']:.2f}")
            logger.info(f"      未实现盈亏: ¥{unrealized_pnl:+.2f}")
            logger.info(f"      置信度: {pos['confidence']:.2f}")

def main():
    """主函数"""
    # 设置日志
    logger = setup_logging()
    logger.info("🍒 CherryQuant AI品种选择演示版启动")
    logger.info(f"📅 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        logger.info("🔍 系统检查...")

        # 检查AI连接
        api_available = asyncio.run(test_ai_connection())

        if api_available:
            logger.info("✅ 将使用真实AI进行市场分析和品种选择")
        else:
            logger.info("🎮 将使用模拟AI进行演示")

        logger.info("✅ 系统检查通过")

        # 启动AI品种选择演示
        asyncio.run(ai_selection_demo())

    except KeyboardInterrupt:
        logger.info("👋 用户中断，演示结束")
    except Exception as e:
        logger.error(f"❌ 系统错误: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()