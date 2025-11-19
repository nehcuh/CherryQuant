# CherryQuant 课程讲义 - 第3章：AI 决策引擎

## 3.1 AI 在量化中的角色
传统的量化交易依赖于数学模型和统计套利。CherryQuant 探索了一种新的范式：**基于大语言模型 (LLM) 的语义化交易**。

AI 不仅仅是预测价格，它还能：
- **理解市场情绪**: 分析新闻、公告等非结构化数据。
- **综合多维信息**: 将技术指标 (RSI, MACD) 与宏观环境结合。
- **解释决策逻辑**: 给出"为什么要买入"的自然语言理由，便于人类复盘。

## 3.2 核心组件：AI Selection Engine

`AISelectionEngine` (`src/cherryquant/ai/decision_engine/ai_selection_engine.py`) 是实现这一愿景的核心。

### 工作流程
1.  **数据准备**: 收集全市场（或指定板块）的行情数据、技术指标、持仓状态。
2.  **Prompt 构造**: 将上述数据填入精心设计的 Prompt 模板。
3.  **LLM 推理**: 调用 GPT-4 API，获取 JSON 格式的交易建议。
4.  **结果校验**: 验证 JSON 格式、字段完整性以及业务逻辑合理性。

## 3.3 Prompt Engineering (提示词工程)

Prompt 是 AI 的"指令集"。CherryQuant 使用结构化的 Prompt 来引导 AI。

### System Prompt (系统设定)
```text
你是一个专业的期货量化交易员。你的目标是最大化收益并控制风险。
你需要分析提供的市场数据，并输出 JSON 格式的交易决策。
...
```

### User Prompt (上下文注入)
```text
当前时间: 14:30:00
账户资金: ¥100,000
持仓: 无

市场数据:
### SHFE
**螺纹钢 (RB2501)**
- 价格: ¥3600 (+1.2%)
- 趋势: 强上涨
- RSI: 65 (正常)
...
```

## 3.4 鲁棒性设计 (Robustness)

LLM 有时会产生"幻觉" (Hallucination) 或输出错误的格式。我们在 `AISelectionEngine` 中实现了多重防护：

1.  **JSON 清洗**: 自动去除 Markdown 代码块标记 (```json)。
2.  **重试机制**: 如果解析失败或网络超时，自动重试 (Max Retries = 2)。
3.  **业务校验**: 
    - 检查 `confidence` 是否在 0-1 之间。
    - 检查推荐的 `symbol` 是否在当前市场数据中（防止 AI 编造不存在的合约）。

## 3.5 思考题
1.  为什么我们将 Prompt 分为 System Prompt 和 User Prompt？
2.  如果 AI 建议全仓买入一个波动率极高的品种，我们的系统应该如何拦截？(提示：风险控制层)
3.  如何优化 Prompt 以减少 Token 消耗并提高 AI 的注意力？
