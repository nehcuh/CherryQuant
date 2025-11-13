#!/usr/bin/env python3
"""
CherryQuant 完整多代理AI交易系统启动脚本
集成所有组件：多代理管理、风险管理、警报系统、监控界面
"""

import asyncio
import logging
import signal
import os
import argparse
from typing import Optional, List
from datetime import datetime


from cherryquant.ai.agents.agent_manager import AgentManager, PortfolioRiskConfig
from cherryquant.adapters.data_storage.database_manager import get_database_manager
from cherryquant.adapters.data_adapter.market_data_manager import MarketDataManager
from src.risk.portfolio_risk_manager import PortfolioRiskManager
from src.alerts.alert_manager import AlertManager
from utils.ai_logger import get_ai_logger
from cherryquant.web.api.main import create_app, run_server
from config.settings.settings import TRADING_CONFIG, AI_CONFIG, RISK_CONFIG
from config.database_config import get_database_config
from config.alert_config import get_alert_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/cherryquant_complete.log", encoding="utf-8"),
    ],
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
        self.running_tasks: List[asyncio.Task] = []  # 跟踪运行中的任务
        self.ai_logger: Optional = None
        self.web_app: Optional = None
        self.vnpy_gateway: Optional = None
        self.realtime_recorder: Optional = None

        self.is_running = False
        self.startup_tasks = []
        self.data_mode = os.getenv("DATA_MODE", "dev").lower()
        self.skip_data_check = False  # 是否跳过数据检查
        self.tushare_token = os.getenv("TUSHARE_TOKEN")

    async def _check_and_init_historical_data(self) -> None:
        """检查数据库并询问是否初始化历史数据"""
        if self.skip_data_check:
            return

        try:
            # 检查数据库中的数据量 (MongoDB)
            collection = self.db_manager.mongodb_manager.get_collection("market_data")
            count = await collection.count_documents({})

            if count == 0:
                logger.warning("⚠️  数据库中没有历史数据")
                print("\n" + "=" * 70)
                print("⚠️  检测到数据库为空")
                print("=" * 70)
                print("\n建议下载历史数据以获得更好的AI决策效果")
                print("\n可选方案:")
                print("  1. 现在下载 (推荐，需要5-10分钟)")
                print("  2. 稍后手动下载")
                print("  3. 跳过 (系统将使用实时数据)")
                print("\n" + "=" * 70)

                # 询问用户
                try:
                    choice = input("\n请选择 (1/2/3, 默认3): ").strip() or "3"

                    if choice == "1":
                        # 执行数据初始化
                        logger.info("开始下载历史数据...")
                        await self._run_data_initialization()
                    elif choice == "2":
                        print("\n📝 稍后可运行以下命令初始化数据:")
                        print("   uv run python scripts/init_historical_data.py")
                        print("")
                    else:
                        logger.info("跳过历史数据下载，将使用实时数据")

                except (EOFError, KeyboardInterrupt):
                    logger.info("\n跳过历史数据下载")

            elif count < 1000:
                logger.info(f"ℹ️  数据库中有 {count} 条历史数据（数据较少）")
            else:
                logger.info(f"✅ 数据库中有 {count:,} 条历史数据")

        except Exception as e:
            logger.warning(f"检查历史数据失败: {e}")

    async def _run_data_initialization(self) -> None:
        """运行数据初始化（快速模式）"""
        try:
            # 导入初始化器
            from scripts.init_historical_data import HistoricalDataInitializer

            initializer = HistoricalDataInitializer(self.tushare_token)

            # 快速初始化：主流品种 + 日线/小时线
            symbols = {
                "SHFE": ["rb", "hc", "cu", "al"],
                "DCE": ["i", "j", "jm", "m"],
                "CZCE": ["SR", "CF"],
                "CFFEX": ["IF", "IC"],
            }
            timeframes = ["1d", "1h"]

            print("\n⏬ 正在下载历史数据（主流品种，日线+小时线）...")
            print("   这可能需要几分钟，请稍候...\n")

            results = await initializer.initialize_data(symbols, timeframes)

            logger.info("✅ 历史数据初始化完成")

        except Exception as e:
            logger.error(f"数据初始化失败: {e}")
            print("\n❌ 自动初始化失败，请稍后手动运行:")
            print("   uv run python scripts/init_historical_data.py")
            print("")

    async def initialize(self) -> bool:
        """初始化所有系统组件"""
        try:
            logger.info("🚀 初始化CherryQuant完整交易系统...")

            # 1. 初始化数据库管理器（自动从配置读取）
            self.db_manager = await get_database_manager()
            logger.info("✅ 数据库管理器初始化完成")

            # 1.1 检查数据库是否有历史数据
            await self._check_and_init_historical_data()

            # 2. 初始化市场数据管理器
            from cherryquant.adapters.data_adapter.market_data_manager import (
                create_default_data_manager,
            )

            self.market_data_manager = create_default_data_manager(
                db_manager=self.db_manager
            )
            logger.info("✅ 市场数据管理器初始化完成")

            # 2.1 初始化 RealtimeRecorder（仅 Live 模式）
            if self.data_mode == "live":
                try:
                    from src.trading.vnpy_gateway import VNPyGateway
                    from cherryquant.adapters.vnpy_recorder.realtime_recorder import (
                        RealtimeRecorder,
                    )

                    # 获取CTP配置
                    ctp_userid = os.getenv("CTP_USERID") or os.getenv("SIMNOW_USERID")
                    ctp_password = os.getenv("CTP_PASSWORD") or os.getenv(
                        "SIMNOW_PASSWORD"
                    )
                    ctp_broker_id = os.getenv("CTP_BROKER_ID", "9999")
                    ctp_md_address = os.getenv(
                        "CTP_MD_ADDRESS", "tcp://180.168.146.187:10131"
                    )
                    ctp_td_address = os.getenv(
                        "CTP_TD_ADDRESS", "tcp://180.168.146.187:10130"
                    )

                    if ctp_userid and ctp_password:
                        ctp_setting = {
                            "用户名": ctp_userid,
                            "密码": ctp_password,
                            "经纪商代码": ctp_broker_id,
                            "交易服务器": ctp_td_address,
                            "行情服务器": ctp_md_address,
                            "产品名称": "simnow_client_test",
                            "授权编码": "0000000000000000",
                        }

                        # 创建VNPy网关
                        self.vnpy_gateway = VNPyGateway(
                            gateway_name="CTP", setting=ctp_setting
                        )

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
                                connected = await self.vnpy_gateway.wait_for_connection(
                                    timeout=30
                                )
                                if not connected:
                                    logger.error("❌ CTP连接超时")
                                    self.vnpy_gateway.disconnect()
                                    self.vnpy_gateway = None
                                else:
                                    # 连接成功，创建RealtimeRecorder
                                    self.realtime_recorder = RealtimeRecorder(
                                        self.vnpy_gateway
                                    )
                                    await self.realtime_recorder.initialize()
                                    logger.info("✅ Live模式：CTP实时记录器初始化完成")
                    else:
                        logger.warning(
                            "⚠️ Live模式缺少CTP配置（CTP_USERID或CTP_PASSWORD未设置）"
                        )
                        logger.warning("⚠️ 实时数据录制功能不可用，将使用备用数据源")
                except Exception as e:
                    logger.warning(
                        f"⚠️ RealtimeRecorder 初始化失败（可能是macOS不支持CTP）: {e}"
                    )
                    logger.warning("⚠️ 将使用备用数据源")

            # 3. 初始化AI日志系统
            alert_config = get_alert_config()
            self.ai_logger = await get_ai_logger(
                enable_file_logging=True,
                enable_database_logging=True,
                db_manager=self.db_manager,
            )
            logger.info("✅ AI日志系统初始化完成")

            # 4. 初始化风险管理器
            self.risk_manager = PortfolioRiskManager(
                max_capital_usage=RISK_CONFIG.get("max_capital_usage", 0.8),
                max_daily_loss=RISK_CONFIG.get("max_loss_per_day", 0.05),
                max_drawdown=RISK_CONFIG.get("max_drawdown", 0.15),
                max_correlation=0.7,  # 最大相关性阈值
                max_sector_concentration=0.4,
            )
            await self.risk_manager.start_monitoring()
            logger.info("✅ 组合风险管理器初始化完成")

            # 5. 初始化警报管理器
            self.alert_manager = AlertManager(
                email_config=alert_config.get("email"),
                wechat_config=alert_config.get("wechat"),
                dingtalk_config=alert_config.get("dingtalk"),
                webhook_config=alert_config.get("webhook"),
            )
            await self.alert_manager.start()
            logger.info("✅ 实时警报系统初始化完成")

            # 6. 初始化代理管理器
            risk_config = PortfolioRiskConfig(
                max_total_capital_usage=0.8,
                max_correlation_threshold=0.7,  # 最大相关性阈值
                max_sector_concentration=0.4,
                portfolio_stop_loss=RISK_CONFIG.get("max_drawdown", 0.15),
                daily_loss_limit=RISK_CONFIG.get("max_loss_per_day", 0.05),
                max_leverage_total=TRADING_CONFIG.get("default_leverage", 5.0),
            )

            self.agent_manager = AgentManager(
                db_manager=self.db_manager,
                market_data_manager=self.market_data_manager,
                risk_config=risk_config,
            )

            # 加载策略配置
            await self.agent_manager.load_strategies_from_config()
            logger.info("✅ 多代理管理器初始化完成")

            # 7. 设置组件间集成
            await self._setup_integrations()

            # 8. 初始化Web API
            self.web_app = create_app(
                am=self.agent_manager, dm=self.db_manager, al=self.ai_logger
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
            self.risk_manager.register_risk_callback(
                self.alert_manager.handle_risk_event
            )

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
            self.running_tasks.append(trading_task)

            # 启动Web服务（如果启用）
            web_task = None
            if include_web:
                web_task = asyncio.create_task(self._start_web_server())
                self.running_tasks.append(web_task)

            # 启动监控任务
            monitor_task = asyncio.create_task(self._monitoring_loop())
            self.running_tasks.append(monitor_task)

            # 等待任务完成
            await asyncio.gather(*self.running_tasks, return_exceptions=True)

        except KeyboardInterrupt:
            logger.info("🛑 收到停止信号，正在关闭系统...")
        except asyncio.CancelledError:
            logger.info("🛑 任务被取消，正在关闭系统...")
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
                app=self.web_app, host="0.0.0.0", port=8000, log_level="info"
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
                    "running": (
                        self.agent_manager.is_running if self.agent_manager else False
                    ),
                    "active_strategies": (
                        len(self.agent_manager.active_agents)
                        if self.agent_manager
                        else 0
                    ),
                },
                "risk_manager": {
                    "monitoring": (
                        self.risk_manager.is_monitoring if self.risk_manager else False
                    ),
                    "total_events": (
                        len(self.risk_manager.risk_events) if self.risk_manager else 0
                    ),
                },
                "alert_manager": {
                    "active_alerts": (
                        len(self.alert_manager.active_alerts)
                        if self.alert_manager
                        else 0
                    )
                },
                "database": self.db_manager is not None,
                "ai_logger": self.ai_logger is not None,
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
                manager_status = portfolio_status["manager_status"]

                logger.info(
                    f"📊 系统报告 - 组合价值: ¥{manager_status['portfolio_value']:,.2f}, "
                    f"总盈亏: ¥{manager_status['total_pnl']:,.2f}, "
                    f"活跃策略: {manager_status['active_strategies']}/{manager_status['total_strategies']}"
                )

            if self.risk_manager:
                risk_summary = self.risk_manager.get_risk_summary()
                logger.info(
                    f"🛡️ 风险报告 - 总事件: {risk_summary['total_events']}, "
                    f"活跃警报: {len(self.alert_manager.active_alerts) if self.alert_manager else 0}"
                )

        except Exception as e:
            logger.error(f"生成系统报告失败: {e}")

    async def _get_subscription_symbols(self) -> List[str]:
        """获取需要订阅的合约列表（支持品种池配置）"""
        vt_symbols = []
        try:
            if self.agent_manager and self.agent_manager.agents:
                # 导入合约解析器
                try:
                    from cherryquant.adapters.data_adapter.contract_resolver import (
                        get_contract_resolver,
                    )

                    resolver = get_contract_resolver(self.tushare_token)
                except Exception as e:
                    logger.warning(f"合约解析器初始化失败: {e}")
                    resolver = None

                # 收集所有需要的品种
                all_commodities = set()

                for agent_id, agent in self.agent_manager.agents.items():
                    if not hasattr(agent, "config"):
                        continue

                    config = agent.config

                    # 优先使用 commodities（品种代码列表）
                    if hasattr(config, "commodities") and config.commodities:
                        all_commodities.update(config.commodities)
                        logger.debug(
                            f"策略 {agent_id} 使用品种池: {config.commodities}"
                        )

                    # 向后兼容：支持直接指定的symbols
                    elif hasattr(config, "symbols") and config.symbols:
                        # 直接使用symbols作为合约代码
                        for symbol in config.symbols:
                            # 假设symbols已经是完整合约代码，需要解析交易所
                            if "." in symbol:
                                vt_symbols.append(symbol)
                            else:
                                # 推断交易所
                                from cherryquant.adapters.data_adapter.contract_resolver import (
                                    COMMODITY_EXCHANGE_MAP,
                                )

                                commodity = (
                                    symbol[:2].lower()
                                    if len(symbol) > 2
                                    else symbol.lower()
                                )
                                exchange = COMMODITY_EXCHANGE_MAP.get(commodity, "SHFE")
                                vt_symbols.append(f"{symbol}.{exchange}")

                # 解析品种为主力合约
                if all_commodities and resolver:
                    logger.info(f"📦 解析 {len(all_commodities)} 个品种的主力合约...")
                    contracts_map = await resolver.batch_resolve_contracts(
                        list(all_commodities)
                    )

                    # 构造vt_symbols
                    for commodity, contract in contracts_map.items():
                        if contract:
                            vt_symbol = await resolver.resolve_vt_symbol(commodity)
                            if vt_symbol and vt_symbol not in vt_symbols:
                                vt_symbols.append(vt_symbol)
                                logger.debug(
                                    f"订阅品种 {commodity} 主力合约: {vt_symbol}"
                                )

                if not vt_symbols:
                    logger.warning("⚠️ 未找到任何可订阅的合约，使用默认合约")
                    vt_symbols = ["rb2501.SHFE"]

        except Exception as e:
            logger.error(f"获取订阅合约列表失败: {e}", exc_info=True)
            # 使用默认合约
            vt_symbols = ["rb2501.SHFE"]

        logger.info(f"✅ 将订阅 {len(vt_symbols)} 个合约: {vt_symbols}")
        return vt_symbols

    async def stop(self) -> None:
        """停止系统"""
        logger.info("🛑 停止交易系统...")
        self.is_running = False

        # 取消所有运行中的任务
        logger.info(f"正在取消 {len(self.running_tasks)} 个运行中的任务...")
        for task in self.running_tasks:
            if not task.done():
                task.cancel()

        # 等待任务完成取消
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks, return_exceptions=True)
            self.running_tasks.clear()
            logger.info("✅ 所有任务已取消")

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
        manager_status = portfolio_status["manager_status"]

        print("\n" + "=" * 100)
        print("🚀 CherryQuant 多代理AI交易系统 - 完整版")
        print("=" * 100)
        print(f"📊 总策略数量: {manager_status['total_strategies']}")
        print(f"🟢 活跃策略: {manager_status['active_strategies']}")
        print(f"💰 总初始资金: ¥{manager_status['total_initial_capital']:,.2f}")
        print(f"💼 组合价值: ¥{manager_status['portfolio_value']:,.2f}")
        print(
            f"💸 总盈亏: ¥{manager_status['total_pnl']:,.2f} ({manager_status['portfolio_return']:.2%})"
        )
        print(f"⚡ 资金使用率: {manager_status['capital_usage']:.1%}")
        print(f"🏭 板块集中度: {manager_status['sector_concentration']:.1%}")
        print(f"🛡️ 风险管理: 启用")
        print(f"🚨 警报系统: 启用")
        print(f"📊 监控界面: 启用 (http://localhost:8000)")
        print(f"📈 Grafana面板: 启用 (http://localhost:3000)")
        print("=" * 100)

        # 显示策略信息
        agents = portfolio_status["agents"]
        if agents:
            print("\n策略状态:")
            print("-" * 100)
            for strategy_id, status in agents.items():
                config = status.get("config", {})
                print(
                    f"📋 {config.get('strategy_name', strategy_id)[:30]:30} | "
                    f"资金: ¥{status.get('account_value', 0):>12,.2f} | "
                    f"盈亏: {status.get('return_pct', 0):>7.2%} | "
                    f"交易: {status.get('total_trades', 0):>4} | "
                    f"状态: {status.get('status', 'unknown')}"
                )
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


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="CherryQuant 完整多代理AI交易系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 启动完整系统
  uv run run_cherryquant_complete.py

  # 只下载历史数据（日线）
  uv run run_cherryquant_complete.py --download-data

  # 下载日线和小时线数据
  uv run run_cherryquant_complete.py --download-data --timeframes 1d 1h

  # 跳过数据检查直接启动
  uv run run_cherryquant_complete.py --skip-data-check

  # 只启动交易系统（不启动Web服务）
  uv run run_cherryquant_complete.py --trading-only
        """,
    )

    _ = parser.add_argument(
        "--download-data",
        action="store_true",
        help="仅下载历史数据然后退出（不启动交易系统）",
    )

    _ = parser.add_argument(
        "--skip-data-check", action="store_true", help="跳过启动时的数据检查"
    )

    _ = parser.add_argument(
        "--trading-only", action="store_true", help="只启动交易系统，不启动Web监控界面"
    )

    _ = parser.add_argument(
        "--timeframes",
        nargs="+",
        default=["1d"],
        choices=["1m", "5m", "10m", "30m", "1h", "1d"],
        help="指定要下载的时间周期（配合 --download-data 使用），默认只下载日线数据",
    )

    _ = parser.add_argument(
        "--symbols",
        nargs="+",
        help="指定要下载的品种（配合 --download-data 使用），默认下载主流品种",
    )

    return parser.parse_args()


async def download_data_only(
    timeframes: List[str], symbols: Optional[List[str]] = None
):
    """仅下载数据模式"""
    from scripts.init_historical_data import HistoricalDataInitializer

    logger.info("=" * 70)
    logger.info("📥 CherryQuant 历史数据下载工具")
    logger.info("=" * 70)

    # 获取 Tushare Token
    tushare_token = os.getenv("TUSHARE_TOKEN")
    if not tushare_token or tushare_token == "your_tushare_pro_token_here":
        logger.error("❌ 错误: TUSHARE_TOKEN 未配置")
        logger.error("请在 .env 文件中配置 TUSHARE_TOKEN")
        return

    # 初始化器
    initializer = HistoricalDataInitializer(tushare_token)

    # 确定要下载的品种
    if symbols:
        # 用户指定了品种
        symbol_dict = {}
        from cherryquant.adapters.data_adapter.contract_resolver import (
            COMMODITY_EXCHANGE_MAP,
        )

        for symbol in symbols:
            exchange = COMMODITY_EXCHANGE_MAP.get(symbol.lower())
            if exchange:
                if exchange not in symbol_dict:
                    symbol_dict[exchange] = []
                symbol_dict[exchange].append(symbol)
            else:
                logger.warning(f"未知品种: {symbol}")
    else:
        # 使用默认的主流品种
        symbol_dict = {
            "SHFE": ["rb", "hc", "cu", "al"],
            "DCE": ["i", "j", "jm", "m"],
            "CZCE": ["SR", "CF", "TA"],
            "CFFEX": ["IF", "IC"],
        }

    logger.info(f"\n将下载以下时间周期: {', '.join(timeframes)}")
    logger.info(f"将下载以下品种: {symbol_dict}\n")

    # 检查是否包含分钟线数据
    has_minute_data = any(tf in ["1m", "5m", "10m", "30m", "1h"] for tf in timeframes)
    if has_minute_data:
        logger.warning("⚠️  警告: 分钟线数据有严格的API限流（每分钟2次）")
        logger.warning("    下载会非常慢，请耐心等待\n")

    # 开始下载
    await initializer.initialize_data(symbol_dict, timeframes)

    logger.info("\n" + "=" * 70)
    logger.info("✅ 数据下载完成！")
    logger.info("=" * 70)


async def main():
    """主函数"""
    # 解析命令行参数
    args = parse_args()

    # 如果是仅下载数据模式
    if args.download_data:
        await download_data_only(args.timeframes, args.symbols)
        return

    # 正常启动交易系统
    trading_system = CherryQuantSystem()
    trading_system.skip_data_check = args.skip_data_check
    shutdown_event = asyncio.Event()

    # 设置信号处理
    def signal_handler(signum, frame):
        logger.info(f"收到信号 {signum}，正在停止系统...")
        shutdown_event.set()  # 设置停止事件

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        if args.trading_only:
            # 只启动交易系统
            await trading_system.start_trading_only()
        else:
            # 启动完整系统
            start_task = asyncio.create_task(trading_system.start())

            # 等待启动完成或停止信号
            done, pending = await asyncio.wait(
                [start_task, asyncio.create_task(shutdown_event.wait())],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # 如果收到停止信号，取消启动任务
            if shutdown_event.is_set():
                logger.info("收到停止信号，取消所有任务...")
                for task in pending:
                    task.cancel()
                for task in done:
                    if not task.cancelled():
                        try:
                            await task
                        except Exception as e:
                            logger.error(f"任务异常: {e}")
    finally:
        # 确保清理
        await trading_system.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 感谢使用CherryQuant！")
    except Exception as e:
        logger.error(f"程序异常退出: {e}")
