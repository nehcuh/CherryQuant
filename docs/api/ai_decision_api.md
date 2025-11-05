# AI决策引擎API文档

## 概述

CherryQuant AI决策引擎提供基于大语言模型的期货交易决策服务。该系统基于 nof1.ai 的设计理念，适配中国期货市场。

## 核心组件

### 1. FuturesDecisionEngine

期货AI决策引擎，负责整合市场数据和AI模型，生成交易决策。

#### 初始化

```python
from ai.decision_engine.futures_engine import FuturesDecisionEngine

engine = FuturesDecisionEngine()
```

#### 主要方法

##### get_decision()

获取AI交易决策。

```python
async def get_decision(
    self,
    symbol: str,
    account_info: Dict[str, Any],
    current_positions: List[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
```

**参数：**
- `symbol` (str): 期货合约代码，如 'rb2501'
- `account_info` (Dict): 账户信息字典
- `current_positions` (List[Dict]): 当前持仓列表，可选

**返回值：**
- `Dict[str, Any]`: 交易决策字典，包含以下字段：
  - `signal`: 交易信号（"buy_to_enter", "sell_to_enter", "hold", "close"）
  - `symbol`: 期货合约代码
  - `quantity`: 交易数量（手数）
  - `leverage`: 杠杆倍数（1-10）
  - `profit_target`: 止盈价格
  - `stop_loss`: 止损价格
  - `confidence`: 置信度（0-1）
  - `invalidation_condition`: 失效条件
  - `justification`: 决策理由

**示例：**
```python
decision = await engine.get_decision(
    symbol="rb2501",
    account_info={
        "return_pct": 2.5,
        "win_rate": 0.6,
        "cash_available": 50000.0,
        "account_value": 102500.0
    },
    current_positions=[{
        "symbol": "rb2501",
        "quantity": 2,
        "entry_price": 3450.0,
        "current_price": 3480.0,
        "unrealized_pnl": 60.0,
        "leverage": 5,
        "profit_target": 3550.0,
        "stop_loss": 3400.0,
        "invalidation_condition": "价格跌破3400"
    }]
)
```

### 2. OpenAIClient

OpenAI API客户端，用于调用GPT模型。

#### 初始化

```python
from ai.llm_client.openai_client import OpenAIClient

client = OpenAIClient()
```

#### 主要方法

##### get_trading_decision()

调用GPT模型获取交易决策。

```python
async def get_trading_decision(
    self,
    system_prompt: str,
    user_prompt: str,
    model: str = "gpt-4",
    temperature: float = 0.1,
    max_tokens: int = 1000
) -> Optional[Dict[str, Any]]:
```

**参数：**
- `system_prompt` (str): 系统提示词
- `user_prompt` (str): 用户提示词（包含市场数据）
- `model` (str): 使用的模型，默认"gpt-4"
- `temperature` (float): 温度参数，控制随机性，默认0.1
- `max_tokens` (int): 最大token数，默认1000

**返回值：**
- `Dict[str, Any]`: 解析后的JSON决策对象
- `None`: 调用失败时返回None

## 数据格式规范

### 账户信息格式

```python
account_info = {
    "return_pct": float,      # 总收益率（百分比）
    "win_rate": float,        # 胜率（0-1）
    "cash_available": float,  # 可用资金
    "account_value": float    # 账户总值
}
```

### 持仓信息格式

```python
position = {
    "symbol": str,                    # 合约代码
    "quantity": int,                  # 持仓手数
    "entry_price": float,             # 开仓价格
    "current_price": float,           # 当前价格
    "unrealized_pnl": float,          # 未实现盈亏
    "leverage": int,                  # 杠杆倍数
    "profit_target": float,           # 止盈价格
    "stop_loss": float,               # 止损价格
    "invalidation_condition": str     # 失效条件
}
```

### AI决策输出格式

```python
decision = {
    "signal": "buy_to_enter" | "sell_to_enter" | "hold" | "close",
    "symbol": str,                    # 期货合约代码
    "quantity": int,                  # 交易数量（手数）
    "leverage": int,                  # 杠杆倍数（1-10）
    "profit_target": float,           # 止盈价格
    "stop_loss": float,               # 止损价格
    "confidence": float,              # 置信度（0-1）
    "invalidation_condition": str,    # 失效条件
    "justification": str              # 决策理由（最多500字符）
}
```

## 提示词系统

### 系统提示词 (System Prompt)

系统提示词定义了AI交易员的角色、规则和约束。主要包含：

1. **角色定义**: AI期货交易代理
2. **市场环境**: 中国期货交易所和规则
3. **操作空间**: 四种交易动作定义
4. **仓位管理**: 仓位大小计算框架
5. **风险管理**: 强制性风控协议
6. **输出格式**: 标准JSON格式要求
7. **数据解读**: 技术指标使用指南
8. **交易哲学**: 核心原则和常见误区

### 用户提示词模板 (User Prompt Template)

用户提示词模板动态填充实时市场数据，包含：

1. **时间信息**: 交易开始时长
2. **市场快照**: 当前价格和技术指标
3. **历史数据**: 近期价格和指标序列
4. **账户信息**: 资金状况和性能指标
5. **持仓信息**: 当前持仓和退出计划

## 错误处理

### 常见错误类型

1. **API调用失败**
   ```python
   # 检查网络连接
   if not await client.test_connection():
       logger.error("OpenAI API连接失败")
   ```

2. **JSON解析失败**
   ```python
   # 验证AI回复格式
   try:
       decision = json.loads(content)
   except json.JSONDecodeError:
       logger.error("AI回复格式无效")
   ```

3. **数据获取失败**
   ```python
   # 检查市场数据
   if not market_data:
       logger.error("市场数据获取失败")
   ```

4. **字段验证失败**
   ```python
   # 验证必需字段
   if "signal" not in decision:
       raise ValueError("缺少signal字段")
   ```

### 重试机制

系统自动实现重试机制：
- 网络错误：最多重试3次
- API限流：自动延迟重试
- 数据错误：跳过当前周期

## 配置参数

### AI配置

```python
AI_CONFIG = {
    "model": "gpt-4",           # 使用的AI模型
    "temperature": 0.1,         # 温度参数
    "max_tokens": 1000,         # 最大token数
    "confidence_threshold": 0.3  # 最低置信度阈值
}
```

### 交易配置

```python
TRADING_CONFIG = {
    "decision_interval": 300,   # 决策间隔（秒）
    "max_position_size": 10,    # 最大持仓手数
    "default_leverage": 5,      # 默认杠杆
    "risk_per_trade": 0.02      # 每笔交易风险比例
}
```

## 使用示例

### 完整交易决策流程

```python
import asyncio
from ai.decision_engine.futures_engine import FuturesDecisionEngine

async def main():
    # 初始化决策引擎
    engine = FuturesDecisionEngine()

    # 构造账户信息
    account_info = {
        "return_pct": 0.0,
        "win_rate": 0.0,
        "cash_available": 100000.0,
        "account_value": 100000.0
    }

    # 获取交易决策
    decision = await engine.get_decision(
        symbol="rb2501",
        account_info=account_info,
        current_positions=[]
    )

    if decision:
        print(f"AI决策: {decision['signal']}")
        print(f"交易数量: {decision['quantity']} 手")
        print(f"置信度: {decision['confidence']:.2f}")
        print(f"决策理由: {decision['justification']}")
    else:
        print("AI决策获取失败")

# 运行示例
asyncio.run(main())
```

### 批量多合约决策

```python
async def multi_symbol_decisions():
    engine = FuturesDecisionEngine()
    symbols = ["rb2501", "i2501", "cu2501"]

    tasks = []
    for symbol in symbols:
        task = engine.get_decision(
            symbol=symbol,
            account_info=account_info,
            current_positions=[]
        )
        tasks.append(task)

    decisions = await asyncio.gather(*tasks, return_exceptions=True)

    for symbol, decision in zip(symbols, decisions):
        if isinstance(decision, Exception):
            print(f"{symbol}: 决策失败 - {decision}")
        elif decision:
            print(f"{symbol}: {decision['signal']} ({decision['confidence']:.2f})")
```

## 性能优化

### 异步并发

- 使用异步IO处理API调用
- 支持多合约并行分析
- 非阻塞数据获取

### 缓存机制

- 技术指标计算结果缓存
- AI决策结果临时缓存
- 市场数据本地缓存

### 资源管理

- 连接池管理
- 内存使用优化
- 请求频率控制

---

**文档版本**: v1.0
**创建日期**: 2025-10-29
**最后更新**: 2025-10-29