"""
CherryQuant 启动脚本
用于启动AI期货交易策略
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

# 使用包导入，无需修改 sys.path

# Optional vn.py imports (not required for headless simulation)
try:
    from vnpy_ctastrategy import CtaStrategyApp  # type: ignore
    from vnpy.event import EventEngine  # type: ignore
    from vnpy.trader.engine import MainEngine  # type: ignore
except Exception:  # vn.py not installed/available on macOS without CTP
    CtaStrategyApp = None  # type: ignore
    EventEngine = None  # type: ignore
    MainEngine = None  # type: ignore

from config.settings.settings import TRADING_CONFIG, LOGGING_CONFIG
from cherryquant.adapters.data_adapter.market_data_manager import (
    create_default_data_manager,
    create_simnow_data_manager,
    create_tushare_data_manager,
)
from cherryquant.adapters.data_adapter.history_data_manager import HistoryDataManager
from cherryquant.adapters.data_adapter.contract_resolver import ContractResolver
from cherryquant.bootstrap.app_context import create_app_context


def setup_logging():
    """配置日志"""
    log_dir = Path(LOGGING_CONFIG["log_dir"])
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / f"cherryquant_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=getattr(logging, LOGGING_CONFIG["level"]),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    return logging.getLogger(__name__)


async def create_strategy_settings(contract_resolver: Optional[ContractResolver] = None):
    """创建策略设置（动态解析主力合约）"""
    logger = logging.getLogger(__name__)

    # 从配置获取默认品种代码（不含月份），避免直接读取环境变量
    commodity = TRADING_CONFIG.get("default_symbol", "rb2601")
    # 如果包含数字，提取品种代码
    import re
    commodity_code = re.sub(r"\d+", "", commodity).lower()

    # 默认交易所优先从配置读取，配置缺失时退化为 SHFE
    exchange = TRADING_CONFIG.get("exchange", "SHFE")

    # 使用 ContractResolver 动态解析主力合约
    if contract_resolver:
        try:
            dominant_contract = await contract_resolver.get_dominant_contract(commodity_code)
            if dominant_contract:
                logger.info(f"✅ 动态解析主力合约: {commodity_code} -> {dominant_contract}")
                vt_symbol = f"{dominant_contract}.{exchange}"
            else:
                logger.warning(f"⚠️ 无法解析主力合约，使用默认: {commodity}")
                vt_symbol = f"{commodity}.{exchange}"
        except Exception as e:
            logger.warning(f"⚠️ 主力合约解析失败: {e}，使用默认: {commodity}")
            vt_symbol = f"{commodity}.{exchange}"
    else:
        vt_symbol = f"{commodity}.{exchange}"

    return {
        "vt_symbol": vt_symbol,
        "decision_interval": TRADING_CONFIG.get("decision_interval", 300),
        "max_position_size": TRADING_CONFIG.get("max_position_size", 10),
        "default_leverage": TRADING_CONFIG.get("default_leverage", 5),
        "risk_per_trade": TRADING_CONFIG.get("risk_per_trade", 0.02),
    }


async def setup_data_sources(db_manager=None, data_source_config=None):
    """设置数据源

    Args:
        db_manager: 可选的数据库管理器实例
        data_source_config: 数据源配置（CherryQuantConfig.data_source）。
            当前版本中这是必需参数，不再支持从环境变量读取。
    """
    logger = logging.getLogger(__name__)

    if data_source_config is None:
        raise ValueError(
            "data_source_config 不能为空；请从 CherryQuantConfig.data_source 传入配置"
        )

    data_mode = data_source_config.mode
    data_source = data_source_config.source
    simnow_userid = data_source_config.ctp_userid or ""
    simnow_password = data_source_config.ctp_password or ""
    tushare_token = data_source_config.tushare_token

    logger.info(f"数据模式: {data_mode}")
    logger.info(f"配置数据源: {data_source}")

    ds = data_source.lower()
    if ds == "simnow" and simnow_userid and simnow_password:
        logger.info("使用Simnow/CTP数据源")
        market_data_manager = create_simnow_data_manager(
            simnow_userid,
            simnow_password,
            tushare_token=tushare_token,
        )
        logger.info("正在测试Simnow连接...")
        # TODO: 实现Simnow连接测试
    elif ds == "tushare":
        logger.info("使用Tushare数据源")
        market_data_manager = create_tushare_data_manager()
    else:
        logger.info("使用默认数据管理器")
        market_data_manager = create_default_data_manager(
            db_manager=db_manager,
            data_mode=data_mode,
            tushare_token=tushare_token,
        )

    # 测试数据源
    status = market_data_manager.get_data_sources_status()
    logger.info(f"数据源状态: {len(status)} 个数据源")
    for s in status:
        status_icon = "✅" if s.available else "❌"
        logger.info(f"  {status_icon} {s.name}: {s.description}")

    if data_mode == "live":
        if not db_manager:
            logger.warning("⚠️ Live模式需要数据库管理器，但未提供")
        else:
            logger.info("✅ Live模式：将从数据库读取CTP实时数据")

    return market_data_manager


def setup_history_data():
    """设置历史数据管理器"""
    logger = logging.getLogger(__name__)

    history_manager = HistoryDataManager()

    # 获取缓存信息
    cache_info = history_manager.get_cache_info()
    logger.info(f"历史数据缓存信息: {cache_info}")

    return history_manager


async def update_history_data(history_manager: HistoryDataManager, symbol: str):
    """更新历史数据"""
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"正在更新 {symbol} 的历史数据...")
        await history_manager.update_cache(symbol, "SHFE", "5m", days=7)
        logger.info("✅ 历史数据更新完成")
    except Exception as e:
        logger.error(f"❌ 历史数据更新失败: {e}")


async def test_ai_connection(ai_client, model_name: str, base_url: str) -> bool:
    """测试AI连接（基于已注入的 LLM 客户端）"""
    logger = logging.getLogger(__name__)
    logger.info("正在测试AI连接...")
    logger.info(f"使用模型: {model_name}")
    logger.info(f"API地址: {base_url}")

    try:
        ok = await ai_client.test_connection()

        if ok:
            logger.info("✅ AI连接测试成功")
            logger.info(f"✅ 模型 {model_name} 可用")
            return True
        else:
            logger.error("❌ AI连接测试失败")
            logger.error(f"❌ 无法连接到模型 {model_name}")
            return False

    except Exception as e:
        logger.error(f"AI连接测试异常: {e}")
        logger.error("请检查 AI 配置（config.settings.base.AIConfig）")
        return False


def create_demo_account():
    """创建模拟账户信息"""
    return {
        "account_id": "demo_account",
        "balance": 100000.0,
        "available": 100000.0,
        "frozen": 0.0,
        "margin": 0.0,
        "close_profit": 0.0,
        "position_profit": 0.0,
    }


def run_backtest_mode():
    """运行回测模式"""
    logger = logging.getLogger(__name__)
    logger.info("🚀 启动CherryQuant回测模式")

    try:
        # 这里可以实现回测逻辑
        # 暂时输出提示信息
        logger.info("回测模块规划中：当前版本尚未提供完整回测功能。")
        logger.info("建议暂时使用“simulation”模式进行验证，或关注后续版本更新。")

    except Exception as e:
        logger.error(f"回测模式启动失败: {e}")


async def run_simulation_mode(market_data_manager, history_manager, db_manager, ai_client, contract_resolver):
    """运行模拟交易模式"""
    logger = logging.getLogger(__name__)
    logger.info("🚀 启动CherryQuant模拟交易模式")

    try:
        # 如可用则初始化 vn.py 引擎（可选）
        if EventEngine and MainEngine and CtaStrategyApp:
            event_engine = EventEngine()
            main_engine = MainEngine(event_engine)
            cta_engine = main_engine.add_app(CtaStrategyApp)
            logger.info("vn.py 引擎已就绪（模拟模式不使用真实网关）")
        else:
            logger.info("未检测到 vn.py，使用无依赖的模拟交易循环")

        # 创建策略设置（动态解析主力合约）
        strategy_settings = await create_strategy_settings(contract_resolver)

        logger.info(f"策略设置: {strategy_settings}")
        logger.info(f"交易合约: {strategy_settings['vt_symbol']}")
        logger.info("⚠️  注意: 当前为模拟模式，不会进行真实交易")

        # 更新历史数据
        symbol = strategy_settings["vt_symbol"].split(".")[0]
        asyncio.create_task(update_history_data(history_manager, symbol))

        # 模拟AI决策循环
        asyncio.create_task(
            simulate_ai_trading_loop(
                strategy_settings,
                market_data_manager,
                db_manager,
                ai_client,
            )
        )

        logger.info("✅ CherryQuant模拟交易已启动")
        logger.info("按 Ctrl+C 停止策略")

        # 保持程序运行
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("收到停止信号，正在关闭策略...")

    except Exception as e:
        logger.error(f"模拟模式启动失败: {e}")


async def simulate_ai_trading_loop(strategy_settings, market_data_manager, db_manager, ai_client):
    """模拟AI交易循环（5m 收盘对齐，限价+下一根5m失效）"""
    logger = logging.getLogger(__name__)

    def next_5m_boundary(now: datetime) -> datetime:
        mins = (now.minute // 5 + 1) * 5
        return now.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=mins)

    # 模拟账户和持仓
    account = create_demo_account()
    current_position = 0
    avg_price = 0
    trades = []
    last_trade_id: int | None = None
    pending_orders: List[dict] = []

    logger.info("开始模拟AI交易循环（5m 对齐）...")

    try:
        from cherryquant.ai.decision_engine.futures_engine import FuturesDecisionEngine

        ai_engine = FuturesDecisionEngine(
            ai_client=ai_client,
            db_manager=db_manager,
            market_data_manager=market_data_manager,
        )

        while True:
            try:
                # 对齐到下一根 5m 收盘
                now = datetime.now()
                boundary = next_5m_boundary(now)
                await asyncio.sleep(max((boundary - now).total_seconds(), 0))
                current_time = datetime.now()

                # 获取实时价格（支持多数据源降级）
                symbol = strategy_settings["vt_symbol"].split(".")[0]
                current_price = await market_data_manager.get_realtime_price(symbol)

                # 降级到模拟价格（仅当所有数据源都失败时）
                if current_price is None:
                    current_price = 3500 + (hash(current_time.isoformat()) % 200) - 100
                    logger.warning(f"⚠️ 所有数据源失败，使用模拟价格: {current_price}")

                # 先检查挂单是否成交或过期
                still_pending = []
                for od in pending_orders:
                    # 过期
                    if current_time >= od["expire_at"]:
                        logger.info(
                            f"⌛ 限价单到期未成交，撤单: {od['side']} {od['qty']} @ {od['price']}"
                        )
                        # 更新DB状态
                        try:
                            if od.get("ai_id"):
                                await db_manager.update_ai_decision_status(
                                    od["ai_id"], "expired", current_time, None
                                )
                        except Exception:
                            pass
                        continue
                    # 成交判断（简化）
                    if od["side"] == "buy" and current_price <= od["price"]:
                        logger.info(f"✅ 限价买入成交: {od['qty']} @ {od['price']}")
                        # 建仓
                        total_cost = od["price"] * od["qty"]
                        if account["available"] >= total_cost * 0.1:
                            prev_pos = current_position
                            current_position += od["qty"]
                            avg_price = (
                                (avg_price * prev_pos) + od["price"] * od["qty"]
                            ) / max(current_position, 1)
                            try:
                                if od.get("ai_id"):
                                    await db_manager.update_ai_decision_status(
                                        od["ai_id"],
                                        "executed",
                                        current_time,
                                        od["price"],
                                    )
                                entry = {
                                    "symbol": strategy_settings["vt_symbol"].split(".")[
                                        0
                                    ],
                                    "exchange": strategy_settings["vt_symbol"].split(
                                        "."
                                    )[-1],
                                    "direction": "long",
                                    "quantity": od["qty"],
                                    "entry_price": od["price"],
                                    "entry_time": current_time,
                                    "entry_fee": 0.0,
                                    "ai_decision_id": od.get("ai_id"),
                                }
                                last_trade_id = await db_manager.create_trade_entry(
                                    entry
                                )
                            except Exception:
                                pass
                        continue
                    if od["side"] == "sell" and current_price >= od["price"]:
                        logger.info(f"✅ 限价卖出成交: {od['qty']} @ {od['price']}")
                        prev_pos = abs(current_position)
                        current_position -= od["qty"]
                        avg_price = (
                            (avg_price * prev_pos) + od["price"] * od["qty"]
                        ) / max(abs(current_position), 1)
                        try:
                            if od.get("ai_id"):
                                await db_manager.update_ai_decision_status(
                                    od["ai_id"], "executed", current_time, od["price"]
                                )
                            entry = {
                                "symbol": strategy_settings["vt_symbol"].split(".")[0],
                                "exchange": strategy_settings["vt_symbol"].split(".")[
                                    -1
                                ],
                                "direction": "short",
                                "quantity": od["qty"],
                                "entry_price": od["price"],
                                "entry_time": current_time,
                                "entry_fee": 0.0,
                                "ai_decision_id": od.get("ai_id"),
                            }
                            last_trade_id = await db_manager.create_trade_entry(entry)
                        except Exception:
                            pass
                        continue
                    # 继续等待
                    still_pending.append(od)
                pending_orders = still_pending

                # 构造账户信息
                account_info = {
                    "return_pct": 0.0,
                    "win_rate": 0.0,
                    "cash_available": account["available"],
                    "account_value": account["balance"],
                }

                # 构造持仓信息
                positions_info = []
                if current_position != 0:
                    unrealized_pnl = (current_price - avg_price) * current_position
                    positions_info.append(
                        {
                            "symbol": strategy_settings["vt_symbol"].split(".")[0],
                            "quantity": abs(current_position),
                            "entry_price": avg_price,
                            "current_price": current_price,
                            "unrealized_pnl": unrealized_pnl,
                            "leverage": strategy_settings["default_leverage"],
                        }
                    )

                # 获取AI决策
                decision = await ai_engine.get_decision(
                    symbol=strategy_settings["vt_symbol"].split(".")[0],
                    account_info=account_info,
                    current_positions=positions_info,
                    exchange=strategy_settings["vt_symbol"].split(".")[-1],
                )

                if decision:
                    signal = decision.get("signal")
                    quantity = int(decision.get("quantity", 0) or 0)
                    confidence = float(decision.get("confidence", 0) or 0)
                    justification = decision.get("justification", "")
                    limit_price = float(
                        decision.get("entry_price", current_price) or current_price
                    )

                    logger.info(
                        f"🤖 AI决策: {signal} 数量:{quantity} 置信度:{confidence:.2f} 限价:{limit_price}"
                    )

                    # 持久化AI决策
                    ai_id = None
                    try:
                        ai_db_record = {
                            "decision_time": current_time,
                            "symbol": strategy_settings["vt_symbol"].split(".")[0],
                            "exchange": strategy_settings["vt_symbol"].split(".")[-1],
                            "action": signal,
                            "quantity": quantity,
                            "leverage": int(
                                decision.get(
                                    "leverage", strategy_settings["default_leverage"]
                                )
                            ),
                            "entry_price": float(limit_price),
                            "profit_target": float(
                                decision.get("profit_target", 0) or 0
                            ),
                            "stop_loss": float(decision.get("stop_loss", 0) or 0),
                            "confidence": float(confidence),
                            "opportunity_score": 0,
                            "selection_rationale": justification,
                            "technical_analysis": "",
                            "risk_factors": "",
                            "market_regime": "",
                            "volatility_index": "",
                            "status": "pending",
                        }
                        await db_manager.store_ai_decision(ai_db_record)
                        ai_id = ai_db_record.get("id")
                    except Exception as e:
                        logger.debug(f"保存AI决策失败: {e}")

                    # 仅在有意义时挂单；默认下一根 5m 失效
                    if (
                        confidence > 0.3
                        and quantity > 0
                        and signal in ("buy_to_enter", "sell_to_enter")
                    ):
                        side = "buy" if signal == "buy_to_enter" else "sell"
                        expire_at = next_5m_boundary(current_time)
                        od = {
                            "side": side,
                            "price": limit_price,
                            "qty": min(quantity, 5),
                            "expire_at": expire_at,
                            "ai_id": ai_id,
                        }
                        pending_orders.append(od)
                        logger.info(
                            f"📥 已挂限价单: {side} {od['qty']} @ {limit_price}，到期: {expire_at.strftime('%H:%M:%S')}"
                        )

                    elif signal == "close" and current_position != 0:
                        trade_quantity = abs(current_position)
                        pnl = (current_price - avg_price) * current_position
                        account["balance"] += pnl
                        account["available"] = account["balance"]
                        try:
                            if last_trade_id:
                                await db_manager.close_trade(
                                    trade_id=last_trade_id,
                                    exit_price=current_price,
                                    exit_time=current_time,
                                    exit_fee=0.0,
                                    gross_pnl=pnl,
                                    net_pnl=pnl,
                                    pnl_percentage=None,
                                )
                            last_trade_id = None
                        except Exception:
                            pass
                        logger.info(
                            f"✅ 模拟平仓: {trade_quantity}手 @ {current_price}, 盈亏: {pnl:.2f}"
                        )
                        current_position = 0
                        avg_price = 0
                else:
                    logger.info("⏳ AI决策获取失败或无信号")

            except Exception as e:
                logger.error(f"AI交易循环错误: {e}")
                await asyncio.sleep(60)  # 出错时等待1分钟再重试

    except Exception as e:
        logger.error(f"AI交易循环启动失败: {e}")


async def async_main() -> None:
    """异步主函数，用于启动 CherryQuant 模拟/回测/实盘流程。"""
    logger = setup_logging()
    logger.info("🍒 CherryQuant AI期货交易系统启动")
    logger.info(f"📅 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 运行模式选择
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    else:
        mode = "simulation"  # 默认模拟模式

    logger.info("🔍 检查系统状态...")

    # 1. 构建应用上下文（配置 + MongoDB + Redis + AI 客户端）
    ctx = await create_app_context()
    logger.info("✅ 数据库管理器初始化完成")

    try:
        # 2. 测试AI连接
        ai_cfg = ctx.config.ai
        ai_ok = await test_ai_connection(
            ai_client=ctx.ai_client,
            model_name=ai_cfg.model,
            base_url=ai_cfg.base_url,
        )
        if not ai_ok:
            logger.warning("⚠️ AI连接失败，将继续以占位/无AI方式运行模拟循环")

        # 3. 设置数据源（传递 db_manager 和集中配置以支持 Live/Dev 模式）
        market_data_manager = await setup_data_sources(
            db_manager=ctx.db,
            data_source_config=ctx.config.data_source,
        )
        if not market_data_manager:
            logger.error("❌ 数据源设置失败")
            return

        # 4. 设置历史数据
        history_manager = setup_history_data()

        # 5. 初始化合约解析器（用于动态获取主力合约）
        tushare_token = ctx.config.data_source.tushare_token
        contract_resolver = ContractResolver(tushare_token)
        logger.info("✅ 合约解析器初始化完成")

        logger.info("✅ 系统检查通过")

        # 6. 启动对应模式
        if mode == "backtest":
            run_backtest_mode()
        elif mode == "simulation":
            await run_simulation_mode(
                market_data_manager,
                history_manager,
                ctx.db,
                ctx.ai_client,
                contract_resolver,
            )
        elif mode == "live":
            logger.warning("⚠️  实盘模式尚未完全实现")
            logger.info("请使用模拟模式进行测试")
            await run_simulation_mode(
                market_data_manager,
                history_manager,
                ctx.db,
                ctx.ai_client,
                contract_resolver,
            )
        else:
            logger.error(f"❌ 未知模式: {mode}")
            logger.info("可用模式: simulation, backtest, live")

    except Exception as e:  # noqa: BLE001
        logger.error(f"❌ 系统启动失败: {e}")
        import traceback

        logger.error(traceback.format_exc())
    finally:
        # 确保关闭数据库和连接资源
        await ctx.close()


def main() -> None:
    """同步入口，封装异步主函数。"""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
