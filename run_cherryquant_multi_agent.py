#!/usr/bin/env python3
"""
CherryQuant 多代理AI交易系统主程序
支持多个AI策略同时运行，包含策略隔离、风险管理和监控功能
"""

import asyncio
import logging
import signal
import sys

from typing import Optional
from datetime import datetime



from ai.agents.agent_manager import AgentManager, PortfolioRiskConfig
from adapters.data_storage.database_manager import get_database_manager
from adapters.data_adapter.market_data_manager import MarketDataManager
from config.settings.settings import TRADING_CONFIG, AI_CONFIG, RISK_CONFIG
from config.database_config import get_database_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/multi_agent_trading.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

class MultiAgentTradingSystem:
    """多代理AI交易系统"""

    def __init__(self):
        """初始化交易系统"""
        self.db_manager: Optional = None
        self.market_data_manager: Optional = None
        self.agent_manager: Optional = None
        self.is_running = False

    async def initialize(self) -> bool:
        """初始化系统组件"""
        try:
            logger.info("🚀 初始化CherryQuant多代理交易系统...")

            # 1. 初始化数据库管理器
            db_config = get_database_config()
            self.db_manager = await get_database_manager(db_config)
            logger.info("✅ 数据库管理器初始化完成")

            # 2. 初始化市场数据管理器
            self.market_data_manager = MarketDataManager(self.db_manager)
            await self.market_data_manager.initialize()
            logger.info("✅ 市场数据管理器初始化完成")

            # 3. 初始化代理管理器
            risk_config = PortfolioRiskConfig(
                max_total_capital_usage=RISK_CONFIG.get('max_drawdown', 0.8),
                max_correlation_threshold=TRADING_CONFIG['ai_config'].get('max_correlation_threshold', 0.7),
                max_sector_concentration=0.4,
                portfolio_stop_loss=RISK_CONFIG.get('max_drawdown', 0.15),
                daily_loss_limit=RISK_CONFIG.get('max_loss_per_day', 0.05),
                max_leverage_total=TRADING_CONFIG.get('default_leverage', 5.0)
            )

            self.agent_manager = AgentManager(
                db_manager=self.db_manager,
                market_data_manager=self.market_data_manager,
                risk_config=risk_config
            )
            logger.info("✅ 代理管理器初始化完成")

            # 4. 加载策略配置
            await self.agent_manager.load_strategies_from_config()
            logger.info("✅ 策略配置加载完成")

            return True

        except Exception as e:
            logger.error(f"❌ 系统初始化失败: {e}")
            return False

    async def start(self) -> None:
        """启动交易系统"""
        if not await self.initialize():
            return

        logger.info("🎯 启动多代理AI交易系统...")
        self.is_running = True

        try:
            # 显示系统状态
            self._print_system_status()

            # 启动所有策略
            await self.agent_manager.start_all()

        except KeyboardInterrupt:
            logger.info("🛑 收到停止信号，正在关闭系统...")
        except Exception as e:
            logger.error(f"❌ 系统运行出错: {e}")
        finally:
            await self.shutdown()

    async def stop(self) -> None:
        """停止交易系统"""
        logger.info("🛑 停止交易系统...")
        self.is_running = False

        if self.agent_manager:
            await self.agent_manager.stop_all()

    async def shutdown(self) -> None:
        """关闭系统"""
        logger.info("🔄 关闭系统组件...")

        try:
            if self.agent_manager:
                await self.agent_manager.stop_all()

            if self.market_data_manager:
                # 关闭市场数据管理器
                pass

            if self.db_manager:
                await self.db_manager.close()

            logger.info("✅ 系统已安全关闭")

        except Exception as e:
            logger.error(f"❌ 关闭系统时出错: {e}")

    def _print_system_status(self) -> None:
        """打印系统状态"""
        portfolio_status = self.agent_manager.get_portfolio_status()
        manager_status = portfolio_status['manager_status']

        print("\n" + "="*80)
        print("🤖 CherryQuant 多代理AI交易系统")
        print("="*80)
        print(f"📊 总策略数量: {manager_status['total_strategies']}")
        print(f"🟢 活跃策略: {manager_status['active_strategies']}")
        print(f"💰 总初始资金: ¥{manager_status['total_initial_capital']:,.2f}")
        print(f"⚡ 总杠杆限制: {manager_status.get('max_leverage_total', 'N/A')}")
        print(f"🛡️ 组合止损线: {self.agent_manager.risk_config.portfolio_stop_loss:.1%}")
        print(f"📈 每日亏损限制: {self.agent_manager.risk_config.daily_loss_limit:.1%}")
        print(f"🏭 板块集中度限制: {self.agent_manager.risk_config.max_sector_concentration:.1%}")
        print("="*80)

        # 显示每个策略的信息
        agents = portfolio_status['agents']
        if agents:
            print("\n策略详情:")
            print("-" * 80)
            for strategy_id, status in agents.items():
                config = status.get('config', {})
                print(f"📋 {config.get('strategy_name', strategy_id)} ({strategy_id})")
                print(f"   资金: ¥{config.get('initial_capital', 0):,.2f} | "
                      f"杠杆: {config.get('leverage', 1):.1f}x | "
                      f"品种: {', '.join(config.get('symbols', []))}")
                print(f"   状态: {'🟢 运行中' if status.get('status') == 'idle' else status.get('status', '未知')}")
                print("-" * 80)

        print("\n按 Ctrl+C 停止系统\n")

    async def show_status(self) -> None:
        """显示实时状态"""
        while self.is_running:
            try:
                portfolio_status = self.agent_manager.get_portfolio_status()
                manager_status = portfolio_status['manager_status']

                # 清屏并打印状态
                import os
                os.system('clear' if os.name == 'posix' else 'cls')

                print("\n" + "="*80)
                print("📈 CherryQuant 实时监控面板")
                print("="*80)
                print(f"🕐 运行时间: {(datetime.now() - self.agent_manager.start_time).total_seconds()/3600:.1f}小时")
                print(f"💼 组合价值: ¥{manager_status['portfolio_value']:,.2f}")
                print(f"💰 总盈亏: ¥{manager_status['total_pnl']:,.2f} ({manager_status['portfolio_return']:.2%})")
                print(f"🎯 活跃策略: {manager_status['active_strategies']}/{manager_status['total_strategies']}")
                print(f"📊 总交易次数: {manager_status['total_trades']}")
                print(f"💸 资金使用率: {manager_status['capital_usage']:.1%}")
                print(f"🏭 板块集中度: {manager_status['sector_concentration']:.1%}")
                print("="*80)

                # 显示每个策略的简短状态
                agents = portfolio_status['agents']
                for strategy_id, status in agents.items():
                    config = status.get('config', {})
                    print(f"{config.get('strategy_name', strategy_id)[:20]:20} | "
                          f"价值: ¥{status.get('account_value', 0):>10,.2f} | "
                          f"盈亏: {status.get('return_pct', 0):>7.2%} | "
                          f"持仓: {status.get('positions_count', 0):>2}")

                print("="*80)
                print("更新时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

                await asyncio.sleep(10)  # 每10秒更新一次

            except Exception as e:
                logger.error(f"显示状态时出错: {e}")
                await asyncio.sleep(10)

async def main():
    """主函数"""
    trading_system = MultiAgentTradingSystem()

    # 设置信号处理
    def signal_handler(signum, frame):
        logger.info(f"收到信号 {signum}，正在停止系统...")
        asyncio.create_task(trading_system.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 检查命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == '--status':
            # 只显示状态模式
            await trading_system.initialize()
            await trading_system.show_status()
        elif sys.argv[1] == '--help':
            print("用法: python run_cherryquant_multi_agent.py [选项]")
            print("选项:")
            print("  --status   只显示实时状态监控")
            print("  --help     显示帮助信息")
        else:
            print(f"未知参数: {sys.argv[1]}")
            print("使用 --help 查看帮助信息")
    else:
        # 正常启动模式
        await trading_system.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 再见！")
    except Exception as e:
        logger.error(f"程序退出: {e}")
