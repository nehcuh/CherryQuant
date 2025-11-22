"""
CherryQuant Web API
提供RESTful API接口用于监控和管理多代理AI交易系统
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
from pathlib import Path

# 项目导入
from cherryquant.ai.agents.agent_manager import AgentManager
from cherryquant.adapters.data_storage.database_manager import DatabaseManager
from cherryquant.utils.ai_logger import AITradingLogger

logger = logging.getLogger(__name__)

# 全局变量
app = FastAPI(
    title="CherryQuant API",
    description="多代理AI交易系统监控和管理API",
    version="1.0.0"
)

# 挂载静态文件
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# CORS设置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局实例
agent_manager: AgentManager | None = None
db_manager: DatabaseManager | None = None
ai_logger: AITradingLogger | None = None
websocket_connections: list[WebSocket] = []

# Pydantic模型
class StrategyConfig(BaseModel):
    strategy_id: str
    strategy_name: str
    symbols: list[str | None] = None
    commodity_pool: str | None = None
    commodities: list[str | None] = None
    max_symbols: int = 3
    selection_mode: str = "ai_driven"
    initial_capital: float
    max_position_size: int
    max_positions: int
    leverage: float
    risk_per_trade: float
    decision_interval: int
    confidence_threshold: float
    ai_model: str = "gpt-4"
    ai_temperature: float = 0.1
    is_active: bool = True
    manual_override: bool = False

class OrderRequest(BaseModel):
    strategy_id: str
    symbol: str
    direction: str
    order_type: str
    volume: int
    price: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None

class RiskConfig(BaseModel):
    max_total_capital_usage: float = 0.8
    max_correlation_threshold: float = 0.7
    max_sector_concentration: float = 0.4
    portfolio_stop_loss: float = 0.1
    daily_loss_limit: float = 0.05
    max_leverage_total: float = 3.0

def initialize_services(
    am: AgentManager,
    dm: DatabaseManager,
    al: AITradingLogger
) -> None:
    """初始化服务"""
    global agent_manager, db_manager, ai_logger
    agent_manager = am
    db_manager = dm
    ai_logger = al


def _parse_timestamp(value: Any) -> datetime | None:
    """尽量从字符串/日期对象解析为 datetime，用于 PnL 计算。"""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _compute_simulated_pnl(recent_trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """根据 recent_trades 计算模拟账户的累计盈亏曲线。"""
    if not recent_trades:
        return []

    items = []
    for trade in recent_trades:
        ts = _parse_timestamp(trade.get("timestamp") or trade.get("entry_time"))
        pnl = trade.get("pnl")
        if ts is None or pnl is None:
            continue
        try:
            pnl_f = float(pnl)
        except (TypeError, ValueError):
            continue
        items.append((ts, pnl_f))

    if not items:
        return []

    items.sort(key=lambda x: x[0])
    cum = 0.0
    series: list[dict[str, Any]] = []
    for ts, pnl_value in items:
        cum += pnl_value
        series.append({"timestamp": ts.isoformat(), "cum_pnl": cum})
    return series


def _compute_live_pnl(strategy_id: str) -> list[dict[str, Any]]:
    """根据 live_executions 近似计算实盘执行的累计已实现盈亏曲线。"""
    if not agent_manager or not hasattr(agent_manager, "live_executions"):
        return []

    executions = agent_manager.live_executions.get(strategy_id, []) or []
    if not executions:
        return []

    events = []
    for e in executions:
        ts = _parse_timestamp(e.get("timestamp"))
        if ts is None:
            continue
        direction = str(e.get("direction") or "").lower()
        volume = e.get("volume")
        price = e.get("price")
        symbol = e.get("symbol") or ""
        if volume is None or price is None:
            continue
        try:
            vol_f = float(volume)
            price_f = float(price)
        except (TypeError, ValueError):
            continue
        events.append({
            "timestamp": ts,
            "direction": direction,
            "volume": vol_f,
            "price": price_f,
            "symbol": symbol,
        })

    if not events:
        return []

    events.sort(key=lambda x: x["timestamp"])

    # 按 symbol 维护头寸与均价
    state: dict[str, dict[str, Any]] = {}
    series: list[dict[str, Any]] = []

    for ev in events:
        symbol = ev["symbol"]
        direction = ev["direction"]
        qty = ev["volume"]
        price = ev["price"]
        ts = ev["timestamp"]

        if direction in ("long", "buy"):
            sign = 1
        elif direction in ("short", "sell"):
            sign = -1
        else:
            continue

        sym_state = state.setdefault(symbol, {"pos": 0.0, "avg_price": 0.0, "realized": 0.0})
        pos = sym_state["pos"]
        avg_price = sym_state["avg_price"]
        realized = sym_state["realized"]
        remaining = qty

        # 1) 反向成交先平仓
        if pos != 0 and pos * sign < 0:
            closing_qty = min(abs(pos), remaining)
            if closing_qty > 0:
                if pos > 0 and sign == -1:
                    # 多头平仓
                    realized += (price - avg_price) * closing_qty
                elif pos < 0 and sign == 1:
                    # 空头平仓
                    realized += (avg_price - price) * closing_qty
                pos += sign * closing_qty
                remaining -= closing_qty
                if pos == 0:
                    avg_price = 0.0

        # 2) 剩余部分按当前方向开仓/加仓
        if remaining > 0:
            if pos == 0 or pos * sign > 0:
                total_qty = abs(pos) + remaining
                if total_qty > 0:
                    if pos == 0:
                        avg_price = price
                    else:
                        avg_price = (avg_price * abs(pos) + price * remaining) / total_qty
                pos += sign * remaining

        sym_state["pos"] = pos
        sym_state["avg_price"] = avg_price
        sym_state["realized"] = realized

        # 计算策略级累计 PnL（按所有 symbol 的 realized 之和）
        total_realized = sum(s["realized"] for s in state.values())
        series.append({"timestamp": ts.isoformat(), "cum_pnl": total_realized})

    return series

# ==================== 根路径 ====================

@app.get("/", response_class=HTMLResponse)
async def root():
    """主页 - Web监控界面"""
    index_file = Path(__file__).parent.parent / "static" / "index.html"
    if index_file.exists():
        with open(index_file, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        # 如果HTML文件不存在，返回API信息
        return """
        <html>
            <head><title>CherryQuant API</title></head>
            <body>
                <h1>🍒 CherryQuant API</h1>
                <p>多代理AI交易系统监控和管理API</p>
                <ul>
                    <li><a href="/docs">API文档</a></li>
                    <li><a href="/api/v1/status">系统状态</a></li>
                    <li><a href="/api/v1/health">健康检查</a></li>
                </ul>
            </body>
        </html>
        """

@app.get("/api", response_class=HTMLResponse)
async def api_info():
    """API信息页面"""
    return {
        "name": "CherryQuant API",
        "version": "1.0.0",
        "description": "多代理AI交易系统监控和管理API",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "status": "/api/v1/status",
            "health": "/api/v1/health",
            "strategies": "/api/v1/strategies",
            "trades": "/api/v1/trades",
            "positions": "/api/v1/positions",
            "risk": "/api/v1/risk/status",
            "performance": "/api/v1/performance/portfolio",
            "docs": "/docs",
            "websocket": "/ws"
        },
        "documentation": "/docs"
    }

# ==================== 系统状态接口 ====================

@app.get("/api/v1/status")
async def get_system_status():
    """获取系统状态"""
    try:
        if not agent_manager:
            raise HTTPException(status_code=503, detail="服务未初始化")

        portfolio_status = agent_manager.get_portfolio_status()
        manager_status = portfolio_status['manager_status']

        return {
            "status": "running" if agent_manager.is_running else "stopped",
            "timestamp": datetime.now().isoformat(),
            "system": {
                "total_strategies": manager_status['total_strategies'],
                "active_strategies": manager_status['active_strategies'],
                "portfolio_value": manager_status['portfolio_value'],
                "total_pnl": manager_status['total_pnl'],
                "daily_pnl": manager_status['daily_pnl'],
                "total_trades": manager_status['total_trades'],
                "capital_usage": manager_status['capital_usage'],
                "sector_concentration": manager_status['sector_concentration'],
                "portfolio_return": manager_status['portfolio_return']
            }
        }
    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/health")
async def health_check():
    """健康检查"""
    try:
        health = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "agent_manager": agent_manager.is_running if agent_manager else False,
                "database": db_manager is not None,
                "ai_logger": ai_logger is not None
            }
        }
        return health
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )

# ==================== 策略管理接口 ====================

@app.get("/api/v1/strategies")
async def get_strategies():
    """获取所有策略"""
    try:
        if not agent_manager:
            raise HTTPException(status_code=503, detail="服务未初始化")

        portfolio_status = agent_manager.get_portfolio_status()
        agents = portfolio_status['agents']

        strategies = []
        for strategy_id, status in agents.items():
            config = status.get('config', {})
            strategies.append({
                "strategy_id": strategy_id,
                "name": config.get('strategy_name', strategy_id),
                "status": status.get('status', 'unknown'),
                "is_active": config.get('is_active', False),
                "symbols": config.get('symbols', []),
                "account_value": status.get('account_value', 0),
                "cash_available": status.get('cash_available', 0),
                "total_trades": status.get('total_trades', 0),
                "win_rate": status.get('win_rate', 0),
                "total_pnl": status.get('total_pnl', 0),
                "return_pct": status.get('return_pct', 0),
                "positions_count": status.get('positions_count', 0),
                "max_drawdown": status.get('max_drawdown', 0),
                "last_decision_time": status.get('last_decision_time')
            })

        return {"strategies": strategies}
    except Exception as e:
        logger.error(f"获取策略列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/strategies/{strategy_id}")
async def get_strategy_details(strategy_id: str):
    """获取策略详细信息"""
    try:
        if not agent_manager:
            raise HTTPException(status_code=503, detail="服务未初始化")

        details = agent_manager.get_strategy_details(strategy_id)
        if not details:
            raise HTTPException(status_code=404, detail="策略不存在")

        return details
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取策略详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/strategies/{strategy_id}/executions")
async def get_strategy_executions(strategy_id: str):
    """获取单个策略的模拟交易与实盘执行对比视图。

    返回字段：
    - recent_trades: StrategyAgent 内部记录的最近模拟交易（教学/回测视角）
    - live_executions: 来自 KLineOrderManager 的实盘订单执行记录（网关/交易所视角）
    - sim_pnl: 基于 recent_trades 计算的累计 PnL 时间序列
    - live_pnl: 基于 live_executions 计算的累计 PnL 时间序列（近似）
    """
    try:
        if not agent_manager:
            raise HTTPException(status_code=503, detail="服务未初始化")

        details = agent_manager.get_strategy_details(strategy_id)
        if not details:
            raise HTTPException(status_code=404, detail="策略不存在")

        sim_pnl = _compute_simulated_pnl(details.get("recent_trades", []))
        live_pnl = _compute_live_pnl(strategy_id)

        sim_last = sim_pnl[-1]["cum_pnl"] if sim_pnl else None
        live_last = live_pnl[-1]["cum_pnl"] if live_pnl else None
        pnl_diff = None
        if sim_last is not None and live_last is not None:
            pnl_diff = live_last - sim_last

        return {
            "strategy_id": strategy_id,
            "recent_trades": details.get("recent_trades", []),
            "live_executions": details.get("live_executions", []),
            "sim_pnl": sim_pnl,
            "live_pnl": live_pnl,
            "sim_pnl_last": sim_last,
            "live_pnl_last": live_last,
            "pnl_diff": pnl_diff,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取策略执行详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/strategies")
async def create_strategy(config: StrategyConfig):
    """创建新策略"""
    try:
        if not agent_manager:
            raise HTTPException(status_code=503, detail="服务未初始化")

        from cherryquant.ai.agents.strategy_agent import StrategyConfig as AgentStrategyConfig

        payload = config.dict()
        strategy_config = AgentStrategyConfig(
            strategy_id=payload["strategy_id"],
            strategy_name=payload["strategy_name"],
            initial_capital=payload["initial_capital"],
            max_position_size=payload["max_position_size"],
            max_positions=payload["max_positions"],
            leverage=payload["leverage"],
            risk_per_trade=payload["risk_per_trade"],
            decision_interval=payload["decision_interval"],
            confidence_threshold=payload["confidence_threshold"],
            ai_model=payload.get("ai_model", "gpt-4"),
            ai_temperature=payload.get("ai_temperature", 0.1),
            is_active=payload.get("is_active", True),
            manual_override=payload.get("manual_override", False),
            # pool-related fields
            commodity_pool=payload.get("commodity_pool"),
            commodities=payload.get("commodities"),
            symbols=payload.get("symbols"),
            max_symbols=payload.get("max_symbols", 3),
            selection_mode=payload.get("selection_mode", "ai_driven"),
        )
        success = await agent_manager.add_strategy(strategy_config)

        if success:
            return {"message": "策略创建成功", "strategy_id": config.strategy_id}
        else:
            raise HTTPException(status_code=400, detail="策略创建失败")

    except Exception as e:
        logger.error(f"创建策略失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/v1/strategies/{strategy_id}/start")
async def start_strategy(strategy_id: str):
    """启动策略"""
    try:
        if not agent_manager:
            raise HTTPException(status_code=503, detail="服务未初始化")

        success = await agent_manager.start_strategy(strategy_id)
        if success:
            return {"message": "策略启动成功"}
        else:
            raise HTTPException(status_code=400, detail="策略启动失败")

    except Exception as e:
        logger.error(f"启动策略失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/v1/strategies/{strategy_id}/stop")
async def stop_strategy(strategy_id: str):
    """停止策略"""
    try:
        if not agent_manager:
            raise HTTPException(status_code=503, detail="服务未初始化")

        success = await agent_manager.stop_strategy(strategy_id)
        if success:
            return {"message": "策略停止成功"}
        else:
            raise HTTPException(status_code=400, detail="策略停止失败")

    except Exception as e:
        logger.error(f"停止策略失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/v1/strategies/{strategy_id}/pause")
async def pause_strategy(strategy_id: str):
    """暂停策略"""
    try:
        if not agent_manager:
            raise HTTPException(status_code=503, detail="服务未初始化")

        success = await agent_manager.pause_strategy(strategy_id)
        if success:
            return {"message": "策略暂停成功"}
        else:
            raise HTTPException(status_code=400, detail="策略暂停失败")

    except Exception as e:
        logger.error(f"暂停策略失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/v1/strategies/{strategy_id}/resume")
async def resume_strategy(strategy_id: str):
    """恢复策略"""
    try:
        if not agent_manager:
            raise HTTPException(status_code=503, detail="服务未初始化")

        success = await agent_manager.resume_strategy(strategy_id)
        if success:
            return {"message": "策略恢复成功"}
        else:
            raise HTTPException(status_code=400, detail="策略恢复失败")

    except Exception as e:
        logger.error(f"恢复策略失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/strategies/{strategy_id}")
async def delete_strategy(strategy_id: str):
    """删除策略"""
    try:
        if not agent_manager:
            raise HTTPException(status_code=503, detail="服务未初始化")

        success = await agent_manager.remove_strategy(strategy_id)
        if success:
            return {"message": "策略删除成功"}
        else:
            raise HTTPException(status_code=400, detail="策略删除失败")

    except Exception as e:
        logger.error(f"删除策略失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 交易管理接口 ====================

@app.get("/api/v1/trades")
async def get_trades(
    strategy_id: str | None = None,
    symbol: str | None = None,
    limit: int = 100
):
    """获取交易记录"""
    try:
        if not db_manager:
            raise HTTPException(status_code=503, detail="数据库服务未初始化")

        trades = await db_manager.get_trade_history(strategy_id, symbol, limit)
        return {"trades": trades}
    except Exception as e:
        logger.error(f"获取交易记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/positions")
async def get_positions(strategy_id: str | None = None):
    """获取当前持仓"""
    try:
        if not agent_manager:
            raise HTTPException(status_code=503, detail="服务未初始化")

        portfolio_status = agent_manager.get_portfolio_status()
        agents = portfolio_status['agents']
        positions = []

        for sid, status in agents.items():
            if strategy_id and sid != strategy_id:
                continue

            agent = agent_manager.agents.get(sid)
            if agent and agent.positions:
                for symbol, position in agent.positions.items():
                    positions.append({
                        "strategy_id": sid,
                        "symbol": symbol,
                        "quantity": position.quantity,
                        "entry_price": position.entry_price,
                        "current_price": position.current_price,
                        "unrealized_pnl": position.unrealized_pnl,
                        "leverage": position.leverage,
                        "stop_loss": position.stop_loss,
                        "take_profit": position.take_profit,
                        "entry_time": position.entry_time.isoformat()
                    })

        return {"positions": positions}
    except Exception as e:
        logger.error(f"获取持仓信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 风险管理接口 ====================

@app.get("/api/v1/risk/status")
async def get_risk_status():
    """获取风险状态"""
    try:
        if not agent_manager:
            raise HTTPException(status_code=503, detail="服务未初始化")

        portfolio_status = agent_manager.get_portfolio_status()
        manager_status = portfolio_status['manager_status']
        risk_config = portfolio_status['risk_config']

        return {
            "risk_metrics": {
                "capital_usage": manager_status['capital_usage'],
                "sector_concentration": manager_status['sector_concentration'],
                "portfolio_drawdown": manager_status.get('max_drawdown', 0),
                "daily_pnl": manager_status['daily_pnl'],
                "active_strategies": manager_status['active_strategies']
            },
            "risk_limits": risk_config
        }
    except Exception as e:
        logger.error(f"获取风险状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/v1/risk/config")
async def update_risk_config(config: RiskConfig):
    """更新风险配置"""
    try:
        if not agent_manager:
            raise HTTPException(status_code=503, detail="服务未初始化")

        from cherryquant.ai.agents.agent_manager import PortfolioRiskConfig

        risk_config = PortfolioRiskConfig(**config.dict())
        agent_manager.risk_config = risk_config

        return {"message": "风险配置更新成功"}
    except Exception as e:
        logger.error(f"更新风险配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 性能统计接口 ====================

@app.get("/api/v1/performance/portfolio")
async def get_portfolio_performance(days: int = 30):
    """获取组合性能"""
    try:
        if not db_manager:
            raise HTTPException(status_code=503, detail="数据库服务未初始化")

        history = await db_manager.get_portfolio_history(days)
        return {"performance_history": history}
    except Exception as e:
        logger.error(f"获取组合性能失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/performance/strategy/{strategy_id}")
async def get_strategy_performance(strategy_id: str, days: int = 7):
    """获取策略性能"""
    try:
        if not db_manager:
            raise HTTPException(status_code=503, detail="数据库服务未初始化")

        performance = await db_manager.get_strategy_performance(strategy_id, days)
        return {"performance_history": performance}
    except Exception as e:
        logger.error(f"获取策略性能失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/performance/daily-summary")
async def get_daily_summary(date: str | None = None):
    """获取每日总结"""
    try:
        if not ai_logger:
            raise HTTPException(status_code=503, detail="日志服务未初始化")

        target_date = None
        if date:
            target_date = datetime.strptime(date, "%Y-%m-%d")

        summary = await ai_logger.get_daily_summary(target_date)
        return summary
    except Exception as e:
        logger.error(f"获取每日总结失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 日志查询接口 ====================

@app.get("/api/v1/logs/decisions")
async def get_decision_logs(
    strategy_id: str | None = None,
    symbol: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100
):
    """获取AI决策日志"""
    try:
        if not ai_logger:
            raise HTTPException(status_code=503, detail="日志服务未初始化")

        start_time = None
        end_time = None

        if start_date:
            start_time = datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            end_time = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

        logs = await ai_logger.get_decision_logs(
            strategy_id, symbol, start_time, end_time, limit
        )
        return {"logs": logs}
    except Exception as e:
        logger.error(f"获取决策日志失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== WebSocket实时数据 ====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket实时数据推送"""
    await websocket.accept()
    websocket_connections.append(websocket)

    try:
        while True:
            # 发送实时数据
            if agent_manager:
                status = await get_system_status()
                await websocket.send_text(json.dumps(status))

            await asyncio.sleep(5)  # 每5秒发送一次

    except WebSocketDisconnect:
        websocket_connections.remove(websocket)
    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)

async def broadcast_to_websockets(message: dict):
    """向所有WebSocket连接广播消息"""
    if websocket_connections:
        for websocket in websocket_connections.copy():
            try:
                await websocket.send_text(json.dumps(message))
            except:
                websocket_connections.remove(websocket)

# ==================== 启动函数 ====================

def create_app(
    am: AgentManager = None,
    dm: DatabaseManager = None,
    al: AITradingLogger = None
) -> FastAPI:
    """创建FastAPI应用"""
    if am and dm and al:
        initialize_services(am, dm, al)
    return app

def run_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False
):
    """运行API服务器"""
    uvicorn.run(
        "web.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )

if __name__ == "__main__":
    run_server(reload=True)
