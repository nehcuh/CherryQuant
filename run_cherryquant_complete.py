#!/usr/bin/env python3
"""
CherryQuant 完整多代理AI交易系统启动脚本
集成所有组件：多代理管理、风险管理、警报系统、监控界面
"""

import asyncio
import logging
import signal
import sys
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from ai.agents.agent_manager import AgentManager, PortfolioRiskConfig
from adapters.data_storage.database_manager import get_database_manager
from adapters.data_adapter.market_data_manager import MarketDataManager
from src.risk.portfolio_risk_manager import PortfolioRiskManager
from src.alerts.alert_manager import AlertManager
from utils.ai_logger import get_ai_logger
from web.api.main import create_app, run_server
from config.settings.settings import TRADING_CONFIG, AI_CONFIG, RISK_CONFIG
from config.database_config import get_database_config
from config.alert_config import get_alert_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/cherryquant_complete.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

class CherryQuantSystem:
    """CherryQuant完整交易系统"""

    def __init__(self):
        """初始化系统"""
        self.db_manager: Optional = None
        self.market_data_manager: Optional = None
        self.agent_manager: Optional = None
        self.risk_manager: Optional = None
        self.alert_manager: Optional = None
        self.ai_logger: Optional = None
        self.web_app: Optional = None
        self.vnpy_gateway: Optional = None
        self.realtime_recorder: Optional = None

        self.is_running = False
        self.startup_tasks = []
        self.data_mode = os.getenv('DATA_MODE', 'dev').lower()

    async def initialize(self) -> bool:
        """初始化所有系统组件"""
        try:
            logger.info("🚀 初始化CherryQuant完整交易系统...")

            # 1. 初始化数据库管理器
            db_config = get_database_config()
            self.db_manager = await get_database_manager(db_config)
            logger.info("✅ 数据库管理器初始化完成")

            # 2. 初始化市场数据管理器
            from adapters.data_adapter.market_data_manager import create_default_data_manager
            self.market_data_manager = create_default_data_manager(db_manager=self.db_manager)
            logger.info("✅ 市场数据管理器初始化完成")

            # 2.1 初始化 RealtimeRecorder（仅 Live 模式）
            if self.data_mode == "live":
                try:
                    from src.trading.vnpy_gateway import VNPyGateway
                    from adapters.vnpy_recorder.realtime_recorder import RealtimeRecorder

                    # 获取CTP配置
                    ctp_userid = os.getenv('CTP_USERID') or os.getenv('SIMNOW_USERID')
                    ctp_password = os.getenv('CTP_PASSWORD') or os.getenv('SIMNOW_PASSWORD')
                    ctp_broker_id = os.getenv('CTP_BROKER_ID', '9999')
                    ctp_md_address = os.getenv('CTP_MD_ADDRESS', 'tcp://180.168.146.187:10131')
                    ctp_td_address = os.getenv('CTP_TD_ADDRESS', 'tcp://180.168.146.187:10130')

                    if ctp_userid and ctp_password:
                        ctp_setting = {
                            '用户名': ctp_userid,
                            '密码': ctp_password,
                            '经纪商代码': ctp_broker_id,
                            '交易服务器': ctp_td_address,
                            '行情服务器': ctp_md_address,
                            '产品名称': 'simnow_client_test',
                            '授权编码': '0000000000000000',
                        }

                        # 创建VNPy网关
                        self.vnpy_gateway = VNPyGateway(gateway_name="CTP", setting=ctp_setting)

                        # 初始化网关（添加到主引擎）
                        if not self.vnpy_gateway.initialize():
                            logger.error("❌ VNPy网关初始化失败")
                            self.vnpy_gateway = None
                        else:
                            # 连接CTP
                            if not self.vnpy_gateway.connect():
                                logger.error("❌ CTP连接失败")
                                self.vnpy_gateway = None
                            else:
                                # 等待连接成功（最多30秒）
                                connected = await self.vnpy_gateway.wait_for_connection(timeout=30)
                                if not connected:
                                    logger.error("❌ CTP连接超时")
                                    self.vnpy_gateway.disconnect()
                                    self.vnpy_gateway = None
                                else:
                                    # 连接成功，创建RealtimeRecorder
                                    self.realtime_recorder = RealtimeRecorder(self.vnpy_gateway)
                                    await self.realtime_recorder.initialize()
                                    logger.info("✅ Live模式：CTP实时记录器初始化完成")
                    else:
                        logger.warning("⚠️ Live模式缺少CTP配置（CTP_USERID或CTP_PASSWORD未设置）")
                        logger.warning("⚠️ 实时数据录制功能不可用，将使用备用数据源")
                except Exception as e:
                    logger.warning(f"⚠️ RealtimeRecorder 初始化失败（可能是macOS不支持CTP）: {e}")
                    logger.warning("⚠️ 将使用备用数据源")

            # 3. 初始化AI日志系统
            alert_config = get_alert_config()
            self.ai_logger = await get_ai_logger(
                enable_file_logging=True,
                enable_database_logging=True,
                db_manager=self.db_manager
            )
            logger.info("✅ AI日志系统初始化完成")

            # 4. 初始化风险管理器
            self.risk_manager = PortfolioRiskManager(
                max_capital_usage=RISK_CONFIG.get('max_capital_usage', 0.8),
                max_daily_loss=RISK_CONFIG.get('max_loss_per_day', 0.05),
                max_drawdown=RISK_CONFIG.get('max_drawdown', 0.15),
                max_correlation=0.7,  # 最大相关性阈值
                max_sector_concentration=0.4
            )
            await self.risk_manager.start_monitoring()
            logger.info("✅ 组合风险管理器初始化完成")

            # 5. 初始化警报管理器
            self.alert_manager = AlertManager(
                email_config=alert_config.get('email'),
                wechat_config=alert_config.get('wechat'),
                dingtalk_config=alert_config.get('dingtalk'),
                webhook_config=alert_config.get('webhook')
            )
            await self.alert_manager.start()
            logger.info("✅ 实时警报系统初始化完成")

            # 6. 初始化代理管理器
            risk_config = PortfolioRiskConfig(
                max_total_capital_usage=0.8,
                max_correlation_threshold=0.7,  # 最大相关性阈值
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

            # 加载策略配置
            await self.agent_manager.load_strategies_from_config()
            logger.info("✅ 多代理管理器初始化完成")

            # 7. 设置组件间集成
            await self._setup_integrations()

            # 8. 初始化Web API
            self.web_app = create_app(
                am=self.agent_manager,
                dm=self.db_manager,
                al=self.ai_logger
            )
            logger.info("✅ Web API初始化完成")

            return True

        except Exception as e:
            logger.error(f"❌ 系统初始化失败: {e}")
            return False

    async def _setup_integrations(self) -> None:
        """设置组件间集成"""
        try:
            # 风险管理器集成到警报管理器
            self.risk_manager.register_risk_callback(self.alert_manager.handle_risk_event)

            # 代理管理器的风险事件转发
            self.agent_manager.risk_manager = self.risk_manager

            logger.info("✅ 组件集成设置完成")

        except Exception as e:
            logger.error(f"组件集成失败: {e}")

    async def start(self, include_web: bool = True) -> None:
        """启动完整系统"""
        if not await self.initialize():
            return

        logger.info("🎯 启动CherryQuant完整交易系统...")
        self.is_running = True

        try:
            # 显示系统状态
            self._print_system_status()

            # 启动 RealtimeRecorder（如果在 Live 模式）
            if self.realtime_recorder:
                try:
                    # 获取要订阅的合约列表（从策略配置中）
                    vt_symbols = await self._get_subscription_symbols()
                    await self.realtime_recorder.start(vt_symbols)
                    logger.info(f"✅ RealtimeRecorder 已启动，订阅: {vt_symbols}")
                except Exception as e:
                    logger.error(f"❌ RealtimeRecorder 启动失败: {e}")

            # 启动交易系统
            trading_task = asyncio.create_task(self.agent_manager.start_all())

            # 启动Web服务（如果启用）
            web_task = None
            if include_web:
                web_task = asyncio.create_task(self._start_web_server())

            # 启动监控任务
            monitor_task = asyncio.create_task(self._monitoring_loop())

            # 等待任务完成
            tasks = [trading_task, monitor_task]
            if web_task:
                tasks.append(web_task)

            await asyncio.gather(*tasks, return_exceptions=True)

        except KeyboardInterrupt:
            logger.info("🛑 收到停止信号，正在关闭系统...")
        except Exception as e:
            logger.error(f"❌ 系统运行出错: {e}")
        finally:
            await self.shutdown()

    async def start_trading_only(self) -> None:
        """只启动交易系统，不启动Web服务"""
        await self.start(include_web=False)

    async def _start_web_server(self) -> None:
        """启动Web服务器"""
        try:
            logger.info("🌐 启动Web API服务器...")
            # 这里可以集成uvicorn来运行FastAPI
            # 简化实现，直接运行
            import uvicorn
            config = uvicorn.Config(
                app=self.web_app,
                host="0.0.0.0",
                port=8000,
                log_level="info"
            )
            server = uvicorn.Server(config)
            await server.serve()
        except Exception as e:
            logger.error(f"Web服务器启动失败: {e}")

    async def _monitoring_loop(self) -> None:
        """系统监控循环"""
        while self.is_running:
            try:
                # 更新系统状态
                await self._update_system_health()

                # 定期清理和报告
                if datetime.now().minute % 30 == 0:  # 每30分钟
                    await self._generate_system_report()

                await asyncio.sleep(60)  # 每分钟检查一次

            except Exception as e:
                logger.error(f"监控循环出错: {e}")
                await asyncio.sleep(30)

    async def _update_system_health(self) -> None:
        """更新系统健康状态"""
        try:
            from datetime import datetime
            # 检查各组件状态
            health_status = {
                "timestamp": datetime.now().isoformat(),
                "agent_manager": {
                    "running": self.agent_manager.is_running if self.agent_manager else False,
                    "active_strategies": len(self.agent_manager.active_agents) if self.agent_manager else 0
                },
                "risk_manager": {
                    "monitoring": self.risk_manager.is_monitoring if self.risk_manager else False,
                    "total_events": len(self.risk_manager.risk_events) if self.risk_manager else 0
                },
                "alert_manager": {
                    "active_alerts": len(self.alert_manager.active_alerts) if self.alert_manager else 0
                },
                "database": self.db_manager is not None,
                "ai_logger": self.ai_logger is not None
            }

            # 记录健康状态
            logger.debug(f"系统健康状态: {health_status}")

        except Exception as e:
            logger.error(f"更新系统健康状态失败: {e}")

    async def _generate_system_report(self) -> None:
        """生成系统报告"""
        try:
            if self.agent_manager:
                portfolio_status = self.agent_manager.get_portfolio_status()
                manager_status = portfolio_status['manager_status']

                logger.info(f"📊 系统报告 - 组合价值: ¥{manager_status['portfolio_value']:,.2f}, "
                           f"总盈亏: ¥{manager_status['total_pnl']:,.2f}, "
                           f"活跃策略: {manager_status['active_strategies']}/{manager_status['total_strategies']}")

            if self.risk_manager:
                risk_summary = self.risk_manager.get_risk_summary()
                logger.info(f"🛡️ 风险报告 - 总事件: {risk_summary['total_events']}, "
                           f"活跃警报: {len(self.alert_manager.active_alerts) if self.alert_manager else 0}")

        except Exception as e:
            logger.error(f"生成系统报告失败: {e}")

    async def _get_subscription_symbols(self) -> List[str]:
        """获取需要订阅的合约列表（支持品种池配置）"""
        vt_symbols = []
        try:
            if self.agent_manager and self.agent_manager.agents:
                # 导入合约解析器
                try:
                    from adapters.data_adapter.contract_resolver import get_contract_resolver
                    resolver = get_contract_resolver(self.tushare_token)
                except Exception as e:
                    logger.warning(f"合约解析器初始化失败: {e}")
                    resolver = None

                # 收集所有需要的品种
                all_commodities = set()

                for agent_id, agent in self.agent_manager.agents.items():
                    if not hasattr(agent, 'config'):
                        continue

                    config = agent.config

                    # 优先使用 commodities（品种代码列表）
                    if hasattr(config, 'commodities') and config.commodities:
                        all_commodities.update(config.commodities)
                        logger.debug(f"策略 {agent_id} 使用品种池: {config.commodities}")

                    # 向后兼容：支持直接指定的symbols
                    elif hasattr(config, 'symbols') and config.symbols:
                        # 直接使用symbols作为合约代码
                        for symbol in config.symbols:
                            # 假设symbols已经是完整合约代码，需要解析交易所
                            if '.' in symbol:
                                vt_symbols.append(symbol)
                            else:
                                # 推断交易所
                                from adapters.data_adapter.contract_resolver import COMMODITY_EXCHANGE_MAP
                                commodity = symbol[:2].lower() if len(symbol) > 2 else symbol.lower()
                                exchange = COMMODITY_EXCHANGE_MAP.get(commodity, 'SHFE')
                                vt_symbols.append(f"{symbol}.{exchange}")

                # 解析品种为主力合约
                if all_commodities and resolver:
                    logger.info(f"📦 解析 {len(all_commodities)} 个品种的主力合约...")
                    contracts_map = await resolver.batch_resolve_contracts(list(all_commodities))

                    # 构造vt_symbols
                    for commodity, contract in contracts_map.items():
                        if contract:
                            vt_symbol = await resolver.resolve_vt_symbol(commodity)
                            if vt_symbol and vt_symbol not in vt_symbols:
                                vt_symbols.append(vt_symbol)
                                logger.debug(f"订阅品种 {commodity} 主力合约: {vt_symbol}")

                if not vt_symbols:
                    logger.warning("⚠️ 未找到任何可订阅的合约，使用默认合约")
                    vt_symbols = ['rb2501.SHFE']

        except Exception as e:
            logger.error(f"获取订阅合约列表失败: {e}", exc_info=True)
            # 使用默认合约
            vt_symbols = ['rb2501.SHFE']

        logger.info(f"✅ 将订阅 {len(vt_symbols)} 个合约: {vt_symbols}")
        return vt_symbols

    async def stop(self) -> None:
        """停止系统"""
        logger.info("🛑 停止交易系统...")
        self.is_running = False

        if self.realtime_recorder:
            try:
                await self.realtime_recorder.stop()
                logger.info("✅ RealtimeRecorder 已停止")
            except Exception as e:
                logger.error(f"停止 RealtimeRecorder 失败: {e}")

        if self.agent_manager:
            await self.agent_manager.stop_all()

        if self.risk_manager:
            await self.risk_manager.stop_monitoring()

        if self.alert_manager:
            await self.alert_manager.stop()

    async def shutdown(self) -> None:
        """关闭系统"""
        logger.info("🔄 关闭所有系统组件...")

        try:
            await self.stop()

            # 断开VNPy网关连接
            if self.vnpy_gateway:
                try:
                    self.vnpy_gateway.disconnect()
                    logger.info("✅ VNPy网关已断开")
                except Exception as e:
                    logger.error(f"断开VNPy网关失败: {e}")

            if self.market_data_manager:
                # 关闭市场数据管理器
                pass

            if self.db_manager:
                await self.db_manager.close()

            if self.ai_logger:
                await self.ai_logger.stop()

            logger.info("✅ CherryQuant系统已安全关闭")

        except Exception as e:
            logger.error(f"❌ 关闭系统时出错: {e}")

    def _print_system_status(self) -> None:
        """打印系统状态"""
        if not self.agent_manager:
            return

        portfolio_status = self.agent_manager.get_portfolio_status()
        manager_status = portfolio_status['manager_status']

        print("\n" + "="*100)
        print("🚀 CherryQuant 多代理AI交易系统 - 完整版")
        print("="*100)
        print(f"📊 总策略数量: {manager_status['total_strategies']}")
        print(f"🟢 活跃策略: {manager_status['active_strategies']}")
        print(f"💰 总初始资金: ¥{manager_status['total_initial_capital']:,.2f}")
        print(f"💼 组合价值: ¥{manager_status['portfolio_value']:,.2f}")
        print(f"💸 总盈亏: ¥{manager_status['total_pnl']:,.2f} ({manager_status['portfolio_return']:.2%})")
        print(f"⚡ 资金使用率: {manager_status['capital_usage']:.1%}")
        print(f"🏭 板块集中度: {manager_status['sector_concentration']:.1%}")
        print(f"🛡️ 风险管理: 启用")
        print(f"🚨 警报系统: 启用")
        print(f"📊 监控界面: 启用 (http://localhost:8000)")
        print(f"📈 Grafana面板: 启用 (http://localhost:3000)")
        print("="*100)

        # 显示策略信息
        agents = portfolio_status['agents']
        if agents:
            print("\n策略状态:")
            print("-" * 100)
            for strategy_id, status in agents.items():
                config = status.get('config', {})
                print(f"📋 {config.get('strategy_name', strategy_id)[:30]:30} | "
                      f"资金: ¥{status.get('account_value', 0):>12,.2f} | "
                      f"盈亏: {status.get('return_pct', 0):>7.2%} | "
                      f"交易: {status.get('total_trades', 0):>4} | "
                      f"状态: {status.get('status', 'unknown')}")
            print("-" * 100)

        print("\n🎯 系统组件:")
        print("   🤖 多代理管理器  ✅ 运行中")
        print("   🛡️ 风险管理系统  ✅ 监控中")
        print("   🚨 实时警报系统  ✅ 就绪")
        print("   📊 Web监控界面  ✅ 服务中")
        print("   📈 Grafana可视化 ✅ 可用")
        print("   💾 数据库存储   ✅ 连接")
        print("   📝 AI决策日志   ✅ 记录")

        print("\n按 Ctrl+C 停止系统\n")

async def main():
    """主函数"""
    trading_system = CherryQuantSystem()

    # 设置信号处理
    def signal_handler(signum, frame):
        logger.info(f"收到信号 {signum}，正在停止系统...")
        asyncio.create_task(trading_system.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 检查命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == '--trading-only':
            # 只启动交易系统
            await trading_system.start_trading_only()
        elif sys.argv[1] == '--help':
            print("用法: python run_cherryquant_complete.py [选项]")
            print("选项:")
            print("  --trading-only  只启动交易系统，不启动Web服务")
            print("  --help          显示帮助信息")
        else:
            print(f"未知参数: {sys.argv[1]}")
            print("使用 --help 查看帮助信息")
    else:
        # 启动完整系统
        await trading_system.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 感谢使用CherryQuant！")
    except Exception as e:
        logger.error(f"程序异常退出: {e}")