# Lab 03: 提示词工程实验

## 实验信息

- **难度**: ⭐⭐⭐ 中级
- **预计时间**: 4 小时
- **相关模块**: Module 3 (AI 决策引擎), ADR-0003
- **截止日期**: Week 5 结束

## 学习目标

完成本实验后，你将能够：

1. ✅ 理解提示词工程（Prompt Engineering）的原理和最佳实践
2. ✅ 设计有效的系统提示词（System Prompt）
3. ✅ 构建动态用户提示词（User Prompt）
4. ✅ 使用 Few-shot Learning 提高决策质量
5. ✅ 评估和优化 AI 决策结果
6. ✅ 理解 CherryQuant 的 AI 策略设计

## 实验前准备

### 前置实验

- [x] Lab 01: 环境搭建与首次运行
- [x] Lab 02: 追踪数据流

### 必备知识

- [ ] 理解大语言模型（LLM）的基本概念
- [ ] 了解 JSON 格式
- [ ] 理解期货交易的基本概念（做多/做空/观望）

### 需要的 API 密钥

- [ ] OpenAI API Key (或兼容的 API 服务)

### 参考资料

- 📖 `docs/course/03_AI_Decision_Engine.md`
- 📖 `docs/adr/0003-prompt-engineering-ai.md`
- 📖 `examples/03_ai/README.md`
- 📖 [OpenAI Prompt Engineering Guide](https://platform.openai.com/docs/guides/prompt-engineering)

## 实验背景

CherryQuant 采用**提示工程**而非模型微调的 AI 策略：

### 为什么选择提示工程？

**优势**:
- ✅ 快速迭代：修改提示词即可调整策略
- ✅ 低成本：无需大量标注数据和 GPU 资源
- ✅ 灵活性：可以快速测试不同分析框架
- ✅ 利用 GPT 的通用推理能力

**挑战**:
- ⚠️ 输出不确定性
- ⚠️ API 调用成本
- ⚠️ 需要精心设计提示词

本实验将教你如何设计高质量的提示词。

---

## 实验任务

### 任务 1: 配置 OpenAI API (15 分钟)

#### 1.1 获取 API Key

**选项 A: 使用 OpenAI 官方** (推荐)
1. 访问 https://platform.openai.com
2. 注册/登录账号
3. 进入 "API Keys" 页面
4. 创建新的 API Key
5. 复制 Key (sk-proj-xxx...)

**选项 B: 使用国内中转服务** (备选)
- 如果无法访问 OpenAI，可使用兼容的 API 服务
- 配置 `OPENAI_BASE_URL` 环境变量

#### 1.2 配置到 .env

编辑 `.env` 文件:

```bash
# OpenAI API 配置
OPENAI_API_KEY=sk-proj-your-key-here
OPENAI_BASE_URL=https://api.openai.com/v1  # 可选
OPENAI_MODEL=gpt-4-turbo-preview            # 推荐模型

# AI 决策参数
AI_TEMPERATURE=0.2        # 低温度提高一致性
AI_MAX_TOKENS=1000       # 最大输出 token 数
AI_TIMEOUT=30            # 请求超时（秒）
```

#### 1.3 测试 API 连接

创建 `test_openai.py`:

```python
"""测试 OpenAI API 连接"""
import asyncio
from cherryquant.ai.llm_client.openai_client import AsyncOpenAIClient
from config.settings.settings import get_settings

async def main():
    settings = get_settings()

    # 创建客户端
    client = AsyncOpenAIClient(settings.ai)

    # 测试简单调用
    response = await client.chat_completion(
        messages=[
            {"role": "user", "content": "请用一句话介绍量化交易"}
        ],
        temperature=0.7,
        max_tokens=100
    )

    print("✅ OpenAI API 连接成功！")
    print(f"回复: {response['choices'][0]['message']['content']}")

    await client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
```

运行:
```bash
uv run python test_openai.py
```

**✅ 检查点**: 成功获取 AI 回复

**常见错误**:

**错误 1**: `AuthenticationError`
- 检查 API Key 是否正确
- 确认账户有余额

**错误 2**: `RateLimitError`
- 免费用户有频率限制
- 降低调用频率或升级账户

---

### 任务 2: 设计系统提示词 (45 分钟)

#### 2.1 理解系统提示词的作用

**系统提示词**定义了 AI 的：
- 🎭 **角色**: 你是谁（专业交易分析师）
- 🎯 **任务**: 你要做什么（分析市场并给出交易建议）
- 📋 **框架**: 你如何分析（趋势、动量、风险）
- 📤 **输出**: 你如何输出（JSON 格式）

#### 2.2 基础版本

创建 `prompts/system_v1.txt`:

```
你是一个专业的期货交易分析师。

请根据提供的市场数据，给出交易建议。

输出格式（JSON）：
{
  "action": "BUY/SELL/HOLD",
  "confidence": 0.0-1.0,
  "reasoning": "分析理由"
}
```

#### 2.3 改进版本

创建 `prompts/system_v2.txt`:

```
你是一个专业的期货交易分析师，专注于中国期货市场。

你的任务是基于提供的技术指标和市场数据，做出理性的交易决策。

分析框架：
1. **趋势分析**: 识别主要趋势方向（上涨/下跌/震荡）和趋势强度
2. **动量分析**: 评估价格动量和成交量配合情况
3. **风险评估**: 当前风险水平和潜在风险点
4. **决策建议**: 综合以上分析，给出明确的交易方向和信心度

输出格式（严格 JSON）：
{
  "action": "BUY/SELL/HOLD",
  "confidence": 0.0-1.0,
  "reasoning": "详细的分析理由（至少50字）",
  "risk_level": "LOW/MEDIUM/HIGH",
  "stop_loss": 建议止损价（可选，数字），
  "take_profit": 建议止盈价（可选，数字）
}

**重要原则**:
- 只基于提供的数据分析，不做主观臆测
- 信心度应反映信号的明确程度
- 风险水平应考虑当前市场波动性
- 如果信号不明确，选择 HOLD
```

#### 2.4 对比测试

创建 `lab03_test_prompts.py`:

```python
"""对比不同系统提示词的效果"""
import asyncio
import json
from pathlib import Path

from cherryquant.ai.llm_client.openai_client import AsyncOpenAIClient
from config.settings.settings import get_settings


async def test_prompt(client: AsyncOpenAIClient, system_prompt: str, user_prompt: str, version: str):
    """测试单个提示词"""
    print(f"\n{'='*60}")
    print(f"测试 {version}")
    print(f"{'='*60}")

    response = await client.chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2,
        max_tokens=500
    )

    content = response['choices'][0]['message']['content']
    print(f"\n回复:\n{content}")

    # 尝试解析 JSON
    try:
        data = json.loads(content)
        print(f"\n✅ JSON 解析成功")
        print(f"  • 动作: {data['action']}")
        print(f"  • 信心度: {data['confidence']}")
        print(f"  • 理由: {data['reasoning'][:50]}...")
        return data
    except json.JSONDecodeError as e:
        print(f"\n❌ JSON 解析失败: {e}")
        return None


async def main():
    settings = get_settings()
    client = AsyncOpenAIClient(settings.ai)

    # 读取系统提示词
    system_v1 = Path("prompts/system_v1.txt").read_text()
    system_v2 = Path("prompts/system_v2.txt").read_text()

    # 用户提示词（模拟市场数据）
    user_prompt = """
品种: 螺纹钢 (rb2501)
当前价格: 3520
24小时涨跌幅: +1.5%

技术指标:
- MA5: 3500
- MA20: 3450
- RSI: 68
- MACD: 金叉，柱状图转正
- 成交量: 较前一日放大 30%

请分析并给出交易建议。
"""

    # 测试两个版本
    result_v1 = await test_prompt(client, system_v1, user_prompt, "系统提示词 V1")
    await asyncio.sleep(2)  # 避免频率限制
    result_v2 = await test_prompt(client, system_v2, user_prompt, "系统提示词 V2")

    # 对比结果
    print(f"\n{'='*60}")
    print("对比总结")
    print(f"{'='*60}")
    print(f"V1 结果: {result_v1}")
    print(f"V2 结果: {result_v2}")

    await client.aclose()


if __name__ == "__main__":
    # 创建 prompts 目录
    Path("prompts").mkdir(exist_ok=True)
    asyncio.run(main())
```

运行:
```bash
uv run python lab03_test_prompts.py
```

**✅ 检查点**:
- 两个版本都能生成决策
- 对比输出质量差异
- V2 应该更详细和结构化

**在实验报告中回答**:
1. 两个版本的主要区别是什么？
2. 哪个版本的输出更有用？为什么？
3. 你会如何进一步改进系统提示词？

---

### 任务 3: 构建动态用户提示词 (30 分钟)

#### 3.1 设计提示词模板

创建 `prompts/user_template.py`:

```python
"""用户提示词模板"""
from typing import Dict, Any


def build_basic_prompt(symbol: str, data: Dict[str, Any]) -> str:
    """基础版本：仅包含价格和技术指标"""
    return f"""
品种: {data.get('name', symbol)} ({symbol})
当前价格: {data['close']}
涨跌幅: {data['change_pct']}%

技术指标:
- MA5: {data['ma5']}
- MA20: {data['ma20']}
- RSI: {data['rsi']}
- MACD: {data['macd']}

请分析并给出交易建议。
"""


def build_enhanced_prompt(symbol: str, data: Dict[str, Any]) -> str:
    """增强版本：包含上下文和历史"""
    return f"""
品种: {data.get('name', symbol)} ({symbol})
板块: {data.get('sector', '未知')}

**当前行情**:
- 最新价: {data['close']}
- 涨跌幅: {data['change_pct']}% {'📈' if data['change_pct'] > 0 else '📉'}
- 成交量: {data['volume']:,}
- 持仓量: {data.get('open_interest', 'N/A')}

**技术指标**:
- 均线系统:
  - MA5: {data['ma5']}（当前价 {'在上方' if data['close'] > data['ma5'] else '在下方'}）
  - MA20: {data['ma20']}（当前价 {'在上方' if data['close'] > data['ma20'] else '在下方'}）
  - 均线排列: {'多头排列' if data['ma5'] > data['ma20'] else '空头排列'}

- 动量指标:
  - RSI(14): {data['rsi']} ({'超买' if data['rsi'] > 70 else '超卖' if data['rsi'] < 30 else '正常'})
  - MACD: {data['macd']}

- 成交量: {'放量' if data.get('volume_ratio', 1) > 1.2 else '缩量' if data.get('volume_ratio', 1) < 0.8 else '正常'}

**市场环境**:
- 近5日走势: {data.get('trend_5d', '震荡')}
- 波动率: {data.get('volatility', 'N/A')}

请基于以上信息，进行综合分析并给出交易建议。
"""


def build_sector_specific_prompt(symbol: str, data: Dict[str, Any], sector: str) -> str:
    """板块定制版本：根据板块特性调整提示词"""
    base = build_enhanced_prompt(symbol, data)

    sector_context = {
        "黑色系": "\n**板块特征**: 黑色金属受宏观经济和房地产政策影响大，关注基建和房地产数据。",
        "有色金属": "\n**板块特征**: 有色金属受全球供需和美元走势影响，关注国际局势。",
        "能源化工": "\n**板块特征**: 能源化工品与原油价格高度相关，关注炼厂利润和库存。",
        "农产品": "\n**板块特征**: 农产品受季节性和天气影响大，关注供需平衡表。",
    }

    context = sector_context.get(sector, "")
    return base + context
```

#### 3.2 测试不同模板

修改 `lab03_test_prompts.py`，添加:

```python
from prompts.user_template import (
    build_basic_prompt,
    build_enhanced_prompt,
    build_sector_specific_prompt
)

# 模拟数据
market_data = {
    "name": "螺纹钢",
    "sector": "黑色系",
    "close": 3520,
    "change_pct": 1.5,
    "volume": 123456,
    "open_interest": 543210,
    "ma5": 3500,
    "ma20": 3450,
    "rsi": 68,
    "macd": "金叉",
    "volume_ratio": 1.3,
    "trend_5d": "上涨",
    "volatility": "中等"
}

# 生成三种提示词
basic = build_basic_prompt("rb2501", market_data)
enhanced = build_enhanced_prompt("rb2501", market_data)
sector = build_sector_specific_prompt("rb2501", market_data, "黑色系")

print("基础版本:\n", basic)
print("\n增强版本:\n", enhanced)
print("\n板块定制版本:\n", sector)
```

**✅ 检查点**: 理解三种模板的区别和适用场景

---

### 任务 4: Few-shot Learning (45 分钟)

#### 4.1 理解 Few-shot Learning

**Zero-shot**: 仅凭指令，无示例
**Few-shot**: 提供 2-3 个示例，让 AI 学习模式

#### 4.2 添加示例到系统提示词

创建 `prompts/system_v3_fewshot.txt`:

```
你是一个专业的期货交易分析师，专注于中国期货市场。

[分析框架和输出格式同 V2...]

**学习示例**：

示例 1: 明确的买入信号
输入: rb2501, 价格 3500, MA5 > MA20 (多头排列), RSI 65, 成交量放大, MACD 金叉
输出:
{
  "action": "BUY",
  "confidence": 0.8,
  "reasoning": "多头排列确立，MACD 金叉伴随成交量放大，技术形态良好，RSI 未进入超买区域，具备上涨动能",
  "risk_level": "MEDIUM",
  "stop_loss": 3450,
  "take_profit": 3600
}

示例 2: 信号不明确，观望
输入: hc2501, 价格 3200, MA5 < MA20 (空头排列), 但RSI 30 (超卖), MACD 死叉, 成交量萎缩
输出:
{
  "action": "HOLD",
  "confidence": 0.5,
  "reasoning": "虽然处于空头排列，但 RSI 超卖可能引发反弹，成交量萎缩显示抛压减弱，信号矛盾，建议观望等待更明确信号",
  "risk_level": "HIGH"
}

示例 3: 明确的卖出信号
输入: i2501, 价格 900, MA5 < MA20 (空头排列), RSI 75 (超买), MACD 死叉, 成交量骤减
输出:
{
  "action": "SELL",
  "confidence": 0.75,
  "reasoning": "空头排列下 RSI 超买，MACD 死叉确认趋势转弱，成交量骤减显示买盘不足，技术面转空",
  "risk_level": "MEDIUM",
  "stop_loss": 920,
  "take_profit": 850
}

现在，请基于以上示例的分析风格，对新的输入进行分析。
```

#### 4.3 对比 Zero-shot vs Few-shot

扩展 `lab03_test_prompts.py`:

```python
# 读取 Few-shot 版本
system_v3_fewshot = Path("prompts/system_v3_fewshot.txt").read_text()

# 对比测试
result_zero_shot = await test_prompt(client, system_v2, user_prompt, "Zero-shot (V2)")
await asyncio.sleep(2)
result_few_shot = await test_prompt(client, system_v3_fewshot, user_prompt, "Few-shot (V3)")

# 比较输出质量
print("\n对比分析:")
print("Zero-shot 信心度:", result_zero_shot.get('confidence'))
print("Few-shot 信心度:", result_few_shot.get('confidence'))
print("理由长度对比:", len(result_zero_shot.get('reasoning', '')), "vs", len(result_few_shot.get('reasoning', '')))
```

**✅ 检查点**: Few-shot 应该产生更一致、更详细的输出

**在实验报告中回答**:
1. Few-shot 示例如何影响 AI 的输出？
2. 什么样的示例最有效？
3. 示例太多会有什么问题？（提示：token 成本）

---

### 任务 5: 评估和优化决策质量 (60 分钟)

#### 5.1 设计评估指标

创建 `evaluate_prompts.py`:

```python
"""评估提示词质量"""
import asyncio
import json
from typing import List, Dict
from pathlib import Path

from cherryquant.ai.llm_client.openai_client import AsyncOpenAIClient
from config.settings.settings import get_settings


class PromptEvaluator:
    """提示词评估器"""

    def __init__(self, client: AsyncOpenAIClient):
        self.client = client

    async def evaluate_consistency(
        self,
        system_prompt: str,
        user_prompt: str,
        n_runs: int = 5
    ) -> Dict:
        """评估一致性：相同输入多次运行结果是否稳定"""
        results = []

        for i in range(n_runs):
            response = await self.client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,  # 低温度提高一致性
                max_tokens=500
            )

            content = response['choices'][0]['message']['content']
            try:
                data = json.loads(content)
                results.append(data)
            except json.JSONDecodeError:
                results.append(None)

            await asyncio.sleep(1)  # 避免频率限制

        # 分析一致性
        actions = [r['action'] for r in results if r]
        confidences = [r['confidence'] for r in results if r]

        consistency = {
            "total_runs": n_runs,
            "successful_parses": len([r for r in results if r]),
            "action_consistency": len(set(actions)) / len(actions) if actions else 0,
            "avg_confidence": sum(confidences) / len(confidences) if confidences else 0,
            "confidence_std": self._std(confidences) if len(confidences) > 1 else 0,
        }

        return consistency

    def _std(self, values: List[float]) -> float:
        """计算标准差"""
        avg = sum(values) / len(values)
        return (sum((x - avg) ** 2 for x in values) / len(values)) ** 0.5

    async def evaluate_coverage(self, system_prompt: str, test_cases: List[Dict]) -> Dict:
        """评估覆盖率：能否处理各种市场情况"""
        results = {
            "BUY": 0,
            "SELL": 0,
            "HOLD": 0,
            "errors": 0
        }

        for case in test_cases:
            try:
                response = await self.client.chat_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": case['user_prompt']}
                    ],
                    temperature=0.2,
                    max_tokens=500
                )

                content = response['choices'][0]['message']['content']
                data = json.loads(content)
                results[data['action']] += 1
            except Exception:
                results["errors"] += 1

            await asyncio.sleep(1)

        return results


async def main():
    settings = get_settings()
    client = AsyncOpenAIClient(settings.ai)
    evaluator = PromptEvaluator(client)

    system_prompt = Path("prompts/system_v3_fewshot.txt").read_text()
    user_prompt = Path("prompts/test_case_1.txt").read_text()

    # 评估一致性
    print("📊 评估一致性 (运行 5 次)...")
    consistency = await evaluator.evaluate_consistency(system_prompt, user_prompt, n_runs=5)

    print(f"\n一致性结果:")
    print(f"  • 成功解析率: {consistency['successful_parses']}/5")
    print(f"  • 动作一致性: {consistency['action_consistency']:.2f}")
    print(f"  • 平均信心度: {consistency['avg_confidence']:.2f}")
    print(f"  • 信心度波动: {consistency['confidence_std']:.2f}")

    # 评估覆盖率
    test_cases = [
        {"name": "强烈多头", "user_prompt": "..."},
        {"name": "强烈空头", "user_prompt": "..."},
        {"name": "震荡市", "user_prompt": "..."},
        # 添加更多测试用例
    ]

    print(f"\n📊 评估覆盖率 ({len(test_cases)} 个测试用例)...")
    coverage = await evaluator.evaluate_coverage(system_prompt, test_cases)
    print(f"\n覆盖率结果:")
    print(f"  • BUY: {coverage['BUY']}")
    print(f"  • SELL: {coverage['SELL']}")
    print(f"  • HOLD: {coverage['HOLD']}")
    print(f"  • 错误: {coverage['errors']}")

    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
```

#### 5.2 创建测试用例集

创建 `prompts/test_cases/`:

```bash
mkdir -p prompts/test_cases
```

创建多个测试用例文件，覆盖不同市场情况：

**`prompts/test_cases/bullish_strong.txt`**:
```
品种: rb2501
价格: 3550 (突破前高)
MA5: 3520 > MA20: 3480 (多头排列)
RSI: 72 (接近超买)
MACD: 金叉，柱状图连续放大
成交量: 放量 50%
```

**`prompts/test_cases/bearish_strong.txt`**:
```
品种: rb2501
价格: 3400 (跌破支撑)
MA5: 3420 < MA20: 3460 (空头排列)
RSI: 28 (超卖)
MACD: 死叉，柱状图扩大
成交量: 放量 40%
```

**`prompts/test_cases/neutral_choppy.txt`**:
```
品种: rb2501
价格: 3480 (横盘震荡)
MA5: 3475 ≈ MA20: 3472 (粘合)
RSI: 50 (中性)
MACD: 接近零轴，柱状图微弱
成交量: 萎缩 30%
```

#### 5.3 运行完整评估

```bash
uv run python evaluate_prompts.py
```

**✅ 检查点**:
- 一致性评分 > 0.8 (80% 以上相同决策)
- 覆盖率平衡 (不全是 BUY 或 SELL)
- 无解析错误

---

### 任务 6: 综合实验 - 完整决策流程 (45 分钟)

#### 6.1 整合所有组件

创建 `lab03_complete_decision.py`:

```python
"""
Lab 03 综合实验: 完整的 AI 决策流程

数据 → 提示词构建 → LLM 调用 → 解析决策 → 风险检查
"""

import asyncio
import json
from datetime import datetime
import structlog

from cherryquant.bootstrap.app_context import create_app_context
from cherryquant.ai.llm_client.openai_client import AsyncOpenAIClient
from prompts.user_template import build_sector_specific_prompt

logger = structlog.get_logger()


async def main():
    logger.info("🚀 Lab 03 综合实验: 完整决策流程")

    app = await create_app_context()

    try:
        # 步骤 1: 获取市场数据 (模拟)
        logger.info("步骤 1: 获取市场数据")
        market_data = {
            "name": "螺纹钢",
            "sector": "黑色系",
            "close": 3520,
            "change_pct": 1.5,
            "volume": 123456,
            "ma5": 3500,
            "ma20": 3450,
            "rsi": 68,
            "macd": "金叉",
            "volume_ratio": 1.3,
            "trend_5d": "上涨",
        }

        # 步骤 2: 构建提示词
        logger.info("步骤 2: 构建提示词")
        system_prompt = Path("prompts/system_v3_fewshot.txt").read_text()
        user_prompt = build_sector_specific_prompt("rb2501", market_data, "黑色系")

        logger.info("用户提示词", content=user_prompt[:100] + "...")

        # 步骤 3: 调用 LLM
        logger.info("步骤 3: 调用 OpenAI API")
        response = await app.ai_client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=800
        )

        # 步骤 4: 解析决策
        logger.info("步骤 4: 解析 AI 决策")
        content = response['choices'][0]['message']['content']
        decision = json.loads(content)

        logger.info(
            "✅ AI 决策完成",
            action=decision['action'],
            confidence=decision['confidence'],
            risk_level=decision.get('risk_level', 'N/A')
        )

        print(f"\n{'='*60}")
        print("AI 决策结果")
        print(f"{'='*60}")
        print(f"动作: {decision['action']}")
        print(f"信心度: {decision['confidence']}")
        print(f"风险等级: {decision.get('risk_level', 'N/A')}")
        print(f"\n分析理由:\n{decision['reasoning']}")

        if 'stop_loss' in decision:
            print(f"\n止损价: {decision['stop_loss']}")
        if 'take_profit' in decision:
            print(f"止盈价: {decision['take_profit']}")

        # 步骤 5: 风险检查 (模拟)
        logger.info("步骤 5: 风险检查")

        if decision['confidence'] < 0.6:
            logger.warning("⚠️  信心度低于阈值，建议不执行交易")

        if decision.get('risk_level') == 'HIGH':
            logger.warning("⚠️  风险等级高，建议降低仓位")

        # 步骤 6: 记录决策日志 (保存到文件)
        logger.info("步骤 6: 记录决策日志")

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "symbol": "rb2501",
            "market_data": market_data,
            "decision": decision,
            "prompt_version": "v3_fewshot"
        }

        with open(f"decision_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "w") as f:
            json.dump(log_entry, f, indent=2, ensure_ascii=False)

        logger.info("✅ 决策日志已保存")

    finally:
        await app.close()

    logger.info("🎉 Lab 03 综合实验完成！")


if __name__ == "__main__":
    asyncio.run(main())
```

运行:
```bash
uv run python lab03_complete_decision.py
```

**✅ 检查点**:
- 成功获取 AI 决策
- 决策包含所有必需字段
- 生成决策日志文件

---

## 实验提交

### 提交内容

1. **提示词文件** (必须)
   - `prompts/system_v1.txt`
   - `prompts/system_v2.txt`
   - `prompts/system_v3_fewshot.txt`
   - `prompts/user_template.py`

2. **测试脚本** (必须)
   - `lab03_test_prompts.py`
   - `evaluate_prompts.py`
   - `lab03_complete_decision.py`

3. **测试用例** (必须)
   - 至少 5 个不同的测试用例文件

4. **评估报告** (必须)
   - 一致性评估结果截图
   - 覆盖率评估结果
   - 提示词版本对比表格

5. **决策日志** (必须)
   - 至少 3 条不同情况的决策日志文件

6. **实验报告** (必须)
   - 回答所有问题
   - 提示词设计思路
   - 优化过程记录
   - 至少 1000 字的学习收获

### 提交方式

- 打包为 `学号_姓名_Lab03.zip`
- 提交到课程平台

### 提交截止日期

- Week 5 结束前

---

## 评分标准 (20 分)

| 评分项 | 分值 | 要求 |
|--------|------|------|
| **提示词设计** | 6 分 | V1-V3 逐步改进，Few-shot 有效 |
| **评估实验** | 5 分 | 一致性和覆盖率评估完整 |
| **综合决策** | 4 分 | 完整流程运行成功 |
| **问题回答** | 3 分 | 回答深入，理解准确 |
| **实验报告** | 2 分 | 报告质量和创新性 |

---

## 常见问题 FAQ

### Q1: OpenAI API 太贵怎么办？

A:
- 使用 GPT-3.5-Turbo (成本降低 10x)
- 限制 `max_tokens` 减少输出长度
- 使用国内兼容 API 服务

### Q2: 如何提高决策一致性？

A:
- 降低 `temperature` (推荐 0.1-0.3)
- 提供更明确的输出格式要求
- 使用 Few-shot 示例

### Q3: AI 总是输出 BUY 或 HOLD，不输出 SELL？

A:
- 检查提示词是否有偏向性
- 增加 SELL 的 Few-shot 示例
- 扩大测试用例覆盖范围

---

## 学习资源

- **ADR-0003**: `docs/adr/0003-prompt-engineering-ai.md`
- **OpenAI Guide**: https://platform.openai.com/docs/guides/prompt-engineering
- **LangChain Prompts**: https://python.langchain.com/docs/modules/prompts/
- **Awesome Prompts**: https://github.com/f/awesome-chatgpt-prompts

---

**恭喜完成 Lab 03！提示工程是 AI 时代的核心技能，继续探索和实践！🚀**
