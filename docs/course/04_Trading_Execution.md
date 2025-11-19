# CherryQuant 课程讲义 - 第4章：交易执行

## 4.1 为什么选择 vn.py？
在 Python 量化领域，vn.py 是最成熟的开源框架之一。它提供了：
- **全市场覆盖**: 支持 CTP (期货)、IB (外盘)、Binance (加密货币) 等多种接口。
- **事件驱动引擎**: 高效处理 Tick 数据和订单回报。
- **实盘经过验证**: 拥有庞大的社区和多年的实盘稳定性验证。

CherryQuant 并不重新发明轮子，而是**站在巨人的肩膀上**。我们将 vn.py 封装为底层的执行层，而将策略逻辑上移到 AI 层。

## 4.2 核心组件：VNPy Gateway

`VNPyGateway` (`src/trading/vnpy_gateway.py`) 是 CherryQuant 与 vn.py 交互的桥梁。它隐藏了 vn.py 复杂的事件循环，向外暴露简单的异步 API。

### 关键功能
- **行情订阅**: `subscribe_market_data(symbol)`
- **下单撤单**: `send_order(...)`, `cancel_order(...)`
- **仓位查询**: `get_position(symbol)`
- **资金查询**: `get_account()`

### 异步适配
vn.py 是基于回调 (Callback) 的，而 CherryQuant 的 AI 引擎是基于 `asyncio` 的。`VNPyGateway` 使用 `asyncio.Future` 或 `Queue` 将回调转换为协程，实现了同步与异步的完美融合。

## 4.3 策略实现：CherryQuantStrategy

`CherryQuantStrategy` (`src/cherryquant/cherry_quant_strategy.py`) 继承自 vn.py 的 `CtaTemplate`。

### 职责
1.  **信号接收**: 接收 AI Engine 发出的 JSON 指令。
2.  **风险风控**: 在下单前进行二次风控（如检查资金是否充足、是否超过最大持仓）。
3.  **算法执行**: 将 AI 的"买入 10 手"指令拆解为具体的订单（如 TWAP 算法或简单的限价单）。

### 代码片段
```python
def on_ai_signal(self, signal: dict):
    """处理AI信号"""
    action = signal.get("action")
    symbol = signal.get("symbol")
    volume = signal.get("quantity")
    
    if action == "buy":
        price = self.get_latest_price(symbol)
        self.buy(price, volume)
        logger.info(f"执行AI买入信号: {symbol} {volume}手 @ {price}")
```

## 4.4 完整交易闭环

1.  **感知 (Sense)**: `MarketDataManager` 收集数据。
2.  **思考 (Think)**: `AISelectionEngine` 分析数据并生成决策。
3.  **行动 (Act)**: `CherryQuantStrategy` 接收决策并调用 `VNPyGateway` 下单。
4.  **反馈 (Feedback)**: 订单成交回报通过 `on_trade` 回调更新账户状态，作为下一轮决策的输入。

## 4.5 思考题
1.  为什么我们不直接在 `AISelectionEngine` 中调用 CTP API 下单？
2.  如果 AI 发出"买入"指令，但此时交易所已经收盘，`VNPyGateway` 会如何反应？
3.  如何实现一个简单的"滑点控制"逻辑，防止在大幅波动时高位接盘？
