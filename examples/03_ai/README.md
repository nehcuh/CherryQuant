# 03 AI 决策引擎

## 概述

本目录包含 AI 决策引擎的示例，演示如何使用大语言模型（LLM）进行交易决策，是 CherryQuant 项目的核心特色。

## 学习目标

- 🤖 理解 LLM 在量化交易中的应用
- 📝 掌握提示工程（Prompt Engineering）技巧
- 🧠 学习 AI 决策流程设计
- ⚖️ 了解 AI 输出解析和风险控制

## 示例列表

### `simple_ai_decision.py` (即将添加)
**难度**: ⭐⭐ 初级

**描述**: 最简单的 AI 决策示例，给定市场数据，获取 AI 交易建议。

**学习要点**:
- OpenAI API 调用
- 基本提示词设计
- JSON 输出解析
- 错误处理

**运行方式**:
```bash
uv run python examples/03_ai/simple_ai_decision.py
```

**预期输出**:
```json
{
  "action": "BUY",
  "confidence": 0.75,
  "reasoning": "螺纹钢价格突破 MA20，成交量放大...",
  "risk_level": "MEDIUM"
}
```

---

### `prompt_engineering.py` (即将添加)
**难度**: ⭐⭐⭐ 中级

**描述**: 演示不同提示词策略对决策质量的影响。

**学习要点**:
- System Prompt vs User Prompt
- Few-shot Learning 示例
- 提示词模板化
- 板块特定策略

**对比实验**:
- 简单提示词 vs 结构化提示词
- 零样本 vs 少样本学习
- 通用策略 vs 板块定制策略

---

### `ai_decision_pipeline.py` (即将添加)
**难度**: ⭐⭐⭐ 中级

**描述**: 完整的 AI 决策流程，包括数据准备、AI 调用、结果验证。

**学习要点**:
- 决策流水线设计
- 数据预处理
- AI 输出验证
- 决策日志记录

**流程图**:
```
市场数据 → 技术指标计算 → 提示词构建 → LLM 调用 →
输出解析 → 置信度过滤 → 风险检查 → 最终决策
```

---

### `multi_agent_decision.py` (即将添加)
**难度**: ⭐⭐⭐⭐ 高级

**描述**: 多 Agent 协同决策示例（趋势 Agent + 风险 Agent + 执行 Agent）。

**学习要点**:
- 多 Agent 架构
- Agent 协作机制
- 决策投票和仲裁
- 冲突解决策略

**Agent 分工**:
- **策略 Agent**: 分析趋势，给出交易方向
- **风险 Agent**: 评估风险，设置止损止盈
- **执行 Agent**: 综合决策，生成交易指令

---

## 架构说明

### AI 决策引擎组件

```
AIDecisionEngine
    ├── PromptBuilder (提示词构建器)
    ├── LLMClient (LLM 客户端)
    ├── OutputParser (输出解析器)
    └── DecisionValidator (决策验证器)
```

### 决策流程

```
输入: 市场数据 + 技术指标
  ↓
System Prompt (系统角色定义)
  ↓
User Prompt (具体分析任务)
  ↓
LLM 推理
  ↓
JSON 输出
  ↓
解析验证
  ↓
输出: 交易决策
```

## 前置要求

### 环境变量配置

在 `.env` 文件中配置 OpenAI API：

```bash
# OpenAI API 配置
OPENAI_API_KEY=sk-your-key-here
OPENAI_BASE_URL=https://api.openai.com/v1  # 可选：自定义端点
OPENAI_MODEL=gpt-4-turbo-preview           # 推荐模型

# AI 决策配置
AI_TEMPERATURE=0.2        # 低温度提高一致性
AI_MAX_TOKENS=1000        # 最大输出 token 数
AI_TIMEOUT=30             # 请求超时（秒）
```

### API 密钥获取

1. 访问 https://platform.openai.com
2. 注册并获取 API Key
3. 配置到 `.env` 文件
4. （可选）配置国内中转 API

### 成本估算

使用 GPT-4-Turbo:
- 单次决策 Token 数: ~800 tokens (input) + ~200 tokens (output)
- 成本: ~$0.01 - $0.02 / 次
- 每日 100 次决策: ~$1 - $2

## 提示工程最佳实践

### 1. 系统提示词设计

```python
SYSTEM_PROMPT = """
你是一个专业的期货交易分析师，专注于中国期货市场。

你的职责：
1. 基于提供的技术指标，分析市场趋势
2. 评估交易机会的风险收益比
3. 给出明确的交易建议（BUY/SELL/HOLD）

分析框架：
- 趋势判断: 主要趋势方向和强度
- 动量分析: 价格动量和成交量配合
- 风险评估: 当前风险水平和关键风险点
- 决策建议: 交易方向、信心度、理由

输出格式: 严格的 JSON 格式
"""
```

### 2. 用户提示词构建

```python
def build_user_prompt(symbol: str, data: dict) -> str:
    return f"""
品种: {symbol} ({data['name']})
板块: {data['sector']}

当前行情:
- 最新价: {data['close']}
- 涨跌幅: {data['change_pct']}%
- 成交量: {data['volume']}

技术指标:
- MA5: {data['ma5']}  MA20: {data['ma20']}
- RSI: {data['rsi']}
- MACD: {data['macd']}

请分析并给出交易建议。
"""
```

### 3. Few-shot 示例

```python
FEW_SHOT_EXAMPLES = """
示例 1:
输入: rb2501, 价格突破 MA20, RSI=65, 成交量放大
输出: {{"action": "BUY", "confidence": 0.7, "reasoning": "突破关键均线，动量强劲"}}

示例 2:
输入: hc2501, 价格跌破 MA5, RSI=35, 成交量萎缩
输出: {{"action": "HOLD", "confidence": 0.5, "reasoning": "市场信号不明确，建议观望"}}
"""
```

## 相关课程模块

- **Module 3**: AI 决策引擎设计
- **ADR-0003**: AI 策略 - 提示工程而非模型微调
- **Lab 03**: 提示词工程实验

## 常见问题

**Q: OpenAI API 调用失败?**

A: 检查以下几点：
- API Key 是否正确
- 网络连接是否正常
- 账户余额是否充足
- Base URL 是否正确（国内可能需要中转）

**Q: AI 决策不稳定，同样输入给出不同结果?**

A: 这是 LLM 的固有特性，缓解方法：
- 降低 `temperature` 参数（推荐 0.1-0.3）
- 使用更详细的提示词
- 多次采样取平均（critical decisions）
- 设置置信度阈值，过滤低信心决策

**Q: 如何提高 AI 决策质量?**

A: 提示词优化策略：
1. 提供更多上下文信息
2. 使用 Few-shot 示例
3. 明确输出格式要求
4. 添加板块特定知识
5. 收集决策日志，迭代改进

**Q: AI 成本太高怎么办?**

A: 成本优化方案：
- 使用 GPT-3.5-Turbo (成本降低 10x)
- 启用决策缓存（相同输入返回缓存）
- 批量处理，减少调用次数
- 设置决策频率限制

**Q: 能否使用其他 LLM（Claude, Gemini）?**

A: 可以！参考 `src/cherryquant/ai/llm_client/` 扩展其他 LLM 客户端。

## 决策输出规范

### 标准 JSON 格式

```python
{
    "action": "BUY" | "SELL" | "HOLD",     # 交易动作
    "confidence": 0.0 - 1.0,                # 信心度 (0-1)
    "reasoning": "详细的分析理由...",        # 推理过程
    "risk_level": "LOW" | "MEDIUM" | "HIGH", # 风险等级
    "stop_loss": 3450.0,                    # 建议止损价（可选）
    "take_profit": 3600.0                   # 建议止盈价（可选）
}
```

### 置信度阈值

- `confidence >= 0.7`: 高信心，可执行交易
- `0.5 <= confidence < 0.7`: 中等信心，谨慎执行
- `confidence < 0.5`: 低信心，建议观望

## 进阶主题

### 1. 提示词版本管理

建议使用 Git 管理提示词版本，便于 A/B 测试和回滚。

### 2. 决策日志分析

收集所有 AI 决策，分析：
- 决策准确率
- 置信度分布
- 常见错误模式

### 3. 提示词自动优化

未来可探索：
- 基于历史表现自动调整提示词
- 使用强化学习优化决策策略

## 下一步

完成本目录示例后，继续学习：
- **04_trading**: 交易执行与风险控制
- **complete_system**: 完整系统集成
- **docs/adr/0003-prompt-engineering-ai.md**: 深入理解 AI 策略设计

---

💡 **学习提示**: AI 决策是 CherryQuant 的核心创新，建议花足够时间理解提示工程的原理和最佳实践。

⚠️ **风险提示**: AI 决策存在不确定性，**务必**配合风险管理系统使用，不可盲目执行 AI 建议。
